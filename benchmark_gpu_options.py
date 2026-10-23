"""Measure isolated AQ and sharpening changes on the current GPU."""
import copy
import json
import statistics
import time
import ctypes
from ctypes import wintypes
import subprocess
from benchmark_profiles import run
import video_compressor as v


def timed_run(cmd):
    start = time.perf_counter()
    proc = subprocess.Popen([str(a) for a in cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=v.CREATE_NO_WINDOW)
    try:
        _, stderr = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise
    wall = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(stderr.decode("utf-8", "replace")[-3000:])
    times = [wintypes.FILETIME() for _ in range(4)]
    fn = ctypes.WinDLL("kernel32", use_last_error=True).GetProcessTimes
    fn.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    fn.restype = wintypes.BOOL
    if not fn(int(proc._handle), *(ctypes.byref(t) for t in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    cpu = sum((t.dwHighDateTime << 32) + t.dwLowDateTime for t in times[2:]) / 10_000_000
    return wall, cpu


def main():
    root = v.HERE / "benchmark-results"
    root.mkdir(exist_ok=True)
    source = root / "source-720p60.mp4"
    if not source.exists():
        raise RuntimeError("Run benchmark_profiles.py first")
    v.probe_gpu_sharpen()
    app = object.__new__(v.App)
    info = dict(v.probe(source), path=source, target=4000000)
    base = dict(enc="hevc_nvenc", preset="p5", depth="8 bit", proc="both", audio="none",
                adv=dict(v.ADV_DEFAULTS), adv_a=dict(v.ADV_A_DEFAULTS), container="mp4",
                web_optimized=True, pass_metadata=True)
    cases = [("AQ off", False, False, 0, False), ("Spatial AQ", True, False, 0, False),
             ("Temporal AQ", False, True, 0, False), ("Both AQ", True, True, 0, False),
             ("CPU sharpen 0.6", True, True, .6, False),
             ("GPU sharpen 0.6", True, True, .6, True)]
    rows = []
    # Warm up NVENC before timing. Alternate order to reduce clock/thermal bias.
    run(app._build_cmd(info, root / "gpu-warmup.mp4", base))
    for label, spatial, temporal, sharpen, gpu in cases:
        cfg = copy.deepcopy(base)
        cfg["adv"].update(spatial_aq=spatial, temporal_aq=temporal, sharpen=sharpen, sharpen_gpu=gpu)
        output = root / f"gpu-option-{len(rows)}.mp4"
        times, cpu_times = [], []
        key_times = []
        for _ in range(3):
            wall, cpu = timed_run(app._build_cmd(info, output, cfg))
            times.append(wall)
            cpu_times.append(cpu)
        app._validate_output(output, info, cfg)
        packets = json.loads(run([v.FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_packets",
                                  "-show_entries", "packet=pts_time,flags", "-of", "json", output]).stdout)["packets"]
        key_times = sorted(float(p["pts_time"]) for p in packets if "K" in p["flags"])
        elapsed = statistics.median(times)
        rows.append(dict(label=label, seconds=round(elapsed, 4), fps=round(480 / elapsed, 1),
                         bytes=output.stat().st_size, times=times, keyframe_times=key_times,
                         max_keyframe_gap=round(max(b-a for a,b in zip(key_times,key_times[1:])), 4),
                         cpu_seconds=round(statistics.median(cpu_times), 4),
                         gpu_sharpen_available=v._GPU_SHARPEN_OK))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    baseline = rows[0]["seconds"]
    for row in rows:
        row["time_change_percent"] = round((row["seconds"] / baseline - 1) * 100, 1)
    (root / "gpu-options.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
