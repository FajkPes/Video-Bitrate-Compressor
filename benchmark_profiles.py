"""Compare application profiles on one reproducible clip; results stay in benchmark-results/."""
import json
import statistics
import time
import threading
from pathlib import Path
import video_compressor as v


def run(cmd):
    result = v.run_hidden([str(a) for a in cmd], timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-3000:])
    return result


def main():
    root = v.HERE / "benchmark-results"
    root.mkdir(exist_ok=True)
    source = root / "source-720p60.mp4"
    if not source.exists():
        run([v.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
             "testsrc2=size=1280x720:rate=60:duration=8", "-c:v", "libx264",
             "-preset", "ultrafast", "-crf", "18", "-metadata", "title=Benchmark source", source])
    app = object.__new__(v.App)
    app.stop_flag = threading.Event()
    info = dict(v.probe(source), path=source, target=4000000)
    results = []
    for enc in ("hevc_nvenc", "h264_nvenc", "libx264", "libx265"):
        for profile in v.PROFILE_ADV:
            cfg = dict(enc=enc, adv=dict(v.ADV_DEFAULTS, **v.PROFILE_ADV[profile]),
                       adv_a=dict(v.ADV_A_DEFAULTS), audio="none", proc="both",
                       container="mp4", depth="8 bit", preset=v.PROFILE_SPEED[profile][v.enc_family(enc)],
                       web_optimized=True, pass_metadata=True)
            # CPU encoders do not need a hardware decoder for this comparison.
            cfg["adv"]["hwaccel"] = enc.endswith("_nvenc")
            output = root / f"{enc}-{profile}.mp4"
            cmd = app._build_cmd(info, output, cfg)
            times = []
            try:
                for _ in range(2):
                    start = time.perf_counter()
                    run(cmd)
                    times.append(time.perf_counter() - start)
                app._validate_output(output, info, cfg)
                elapsed = statistics.median(times)
                row = dict(encoder=enc, profile=profile, preset=cfg["preset"], seconds=round(elapsed, 3),
                           fps=round(480 / elapsed, 1), realtime=round(8 / elapsed, 2),
                           bytes=output.stat().st_size, runs=times)
            except Exception as exc:
                row = dict(encoder=enc, profile=profile, error=str(exc))
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            (root / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
