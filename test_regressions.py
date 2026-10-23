import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import video_compressor as v
from project_state import atomic_json, fingerprint, is_complete, read_project, settings_key


def run(*args):
    result = v.run_hidden([str(a) for a in args], timeout=90)
    if result.returncode:
        raise AssertionError(result.stderr.decode("utf-8", "replace"))
    return result.stdout


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="vbc-tests-", dir=v.HERE)
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source.mp4"
        run(v.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
            "testsrc2=size=160x90:rate=25:duration=8", "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=44100:duration=8", "-f", "lavfi", "-i",
            "sine=frequency=880:sample_rate=48000:duration=8", "-map", "0:v", "-map", "1:a",
            "-map", "2:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            "-b:a", "192k", "-metadata:s:a:0", "language=ces", "-metadata:s:a:1", "language=eng", cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.app = object.__new__(v.App)
        self.app.stop_flag = threading.Event()
        self.app.pause_flag = threading.Event()
        self.app.cur_proc = None
        self.app.msgq = queue.Queue()
        self.app.project_path = None
        self.app.project_settings = None
        self.app.project_lock = threading.Lock()
        self.app.job_lock = threading.RLock()

    def config(self, codec="aac", normalize="r128_2pass"):
        return dict(audio="192", audio_custom="128", proc="audio", container="mp4",
                    adv_a=dict(v.ADV_A_DEFAULTS, codec=codec, normalize=normalize),
                    adv=dict(v.ADV_DEFAULTS, hwaccel=False), enc="libx264", preset="ultrafast", depth="8 bit")

    def info(self):
        return dict(v.probe(self.source), path=self.source, rel=Path("source.mp4"), error=None, target=250000)

    def audio_packets(self, path, track):
        return json.loads(run(v.FFPROBE, "-v", "error", "-select_streams", f"a:{track}",
                              "-show_packets", "-show_entries", "packet=pts_time,duration_time", "-of", "json", path))["packets"]

    def test_real_conversions_and_timing(self):
        original_video = run(v.FFMPEG, "-v", "error", "-i", self.source, "-map", "0:v:0", "-c", "copy", "-f", "hash", "-")
        for codec, normalization in [("aac", "off"), ("aac", "r128"), ("aac", "r128_2pass"),
                                      ("libopus", "off"), ("libopus", "r128_2pass")]:
            with self.subTest(codec=codec, normalization=normalization):
                cfg = self.config(codec, normalization)
                info = self.info()
                if normalization == "r128_2pass":
                    info["loudness"] = {i: self.app._measure_loudness(self.source, i, cfg["adv_a"]) for i in range(2)}
                dst = self.root / f"{codec}-{normalization}.mp4"
                run(*self.app._build_cmd(info, dst, cfg))
                output = v.probe(dst)
                self.assertEqual(output["naudio"], 2)
                self.assertEqual([s["lang"] for s in output["astreams"]], ["ces", "eng"])
                self.assertEqual([s["rate"] for s in output["astreams"]], [48000, 48000] if codec == "libopus" else [44100, 48000])
                copied_video = run(v.FFMPEG, "-v", "error", "-i", dst, "-map", "0:v:0", "-c", "copy", "-f", "hash", "-")
                self.assertEqual(original_video, copied_video)
                run(v.FFMPEG, "-v", "error", "-xerror", "-i", dst, "-map", "0:a", "-f", "null", "-")
                for track in range(2):
                    packets = self.audio_packets(dst, track)
                    for before, after in zip(packets, packets[1:]):
                        end = float(before["pts_time"]) + float(before["duration_time"])
                        self.assertLess(abs(float(after["pts_time"]) - end), 0.002)
                    end = float(packets[-1]["pts_time"]) + float(packets[-1]["duration_time"])
                    # AAC frame padding may add up to one 1024-sample frame.
                    self.assertAlmostEqual(end, 8, delta=0.15)
                    if normalization == "r128_2pass":
                        measured = self.app._measure_loudness(dst, track, cfg["adv_a"])
                        self.assertAlmostEqual(float(measured["input_i"]), -14, delta=0.6)

    def test_video_and_audio_reencoding(self):
        cfg = self.config()
        cfg["proc"] = "both"
        cfg["adv"].update(sharpen=0.6)
        info = self.info()
        info["loudness"] = {i: self.app._measure_loudness(self.source, i, cfg["adv_a"]) for i in range(2)}
        dst = self.root / "encoded.mp4"
        cmd = self.app._build_cmd(info, dst, cfg)
        self.assertIn("unsharp=5:5:0.6:5:5:0", cmd)
        run(*cmd)
        self.assertEqual(v.probe(dst)["naudio"], 2)
        run(v.FFMPEG, "-v", "error", "-xerror", "-i", dst, "-map", "0", "-f", "null", "-")

    def test_gpu_sharpen_uploads_and_downloads_frames_when_available(self):
        cfg = self.config()
        cfg.update(proc="both", enc="hevc_nvenc", depth="8 bit")
        cfg["adv"].update(sharpen=0.7, sharpen_gpu=True, hwaccel=True)
        info = self.info()
        with patch.object(v, "_GPU_SHARPEN_OK", True):
            cmd = self.app._build_cmd(info, self.root / "gpu.mp4", cfg)
        self.assertIn("-init_hw_device", cmd)
        vf_index = cmd.index("-vf")
        self.assertEqual(cmd[vf_index + 1], "format=yuv420p,hwupload,unsharp_opencl=5:5:0.7:5:5:0,hwdownload,format=yuv420p")

    def test_gpu_sharpen_preserves_cpu_filters(self):
        cfg = self.config()
        cfg.update(proc="both", enc="hevc_nvenc", depth="8 bit")
        cfg["adv"].update(sharpen=0.7, sharpen_gpu=True, scale="custom", scale_w=128)
        info = self.info()
        with patch.object(v, "_GPU_SHARPEN_OK", True):
            cmd = self.app._build_cmd(info, self.root / "gpu-scaled.mp4", cfg)
        vf_index = cmd.index("-vf")
        self.assertEqual(cmd[vf_index + 1],
                         "scale=128:-2:flags=lanczos,format=yuv420p,hwupload,unsharp_opencl=5:5:0.7:5:5:0,hwdownload,format=yuv420p")
        self.assertNotIn("-hwaccel_output_format", cmd)

    def test_automatic_gop_is_two_seconds_and_creates_repeated_keyframes(self):
        cfg = self.config(normalize="off")
        cfg.update(proc="both", enc="libx264")
        cfg["adv"].update(gop=0, fps="orig")
        info = self.info()
        cmd = self.app._build_cmd(info, self.root / "auto-gop.mp4", cfg)
        self.assertEqual(cmd[cmd.index("-g") + 1], "50")  # 25 fps × 2 seconds
        run(*cmd)
        frames = json.loads(run(v.FFPROBE, "-v", "error", "-select_streams", "v:0",
                                "-show_frames", "-show_entries", "frame=key_frame",
                                "-of", "json", self.root / "auto-gop.mp4"))["frames"]
        self.assertGreaterEqual(sum(int(frame["key_frame"]) for frame in frames), 4)

    def test_nvenc_auto_gop_is_never_infinite(self):
        cfg = self.config(normalize="off")
        cfg.update(proc="both", enc="hevc_nvenc")
        cfg["adv"].update(gop=0, fps="orig")
        cmd = self.app._build_cmd(self.info(), self.root / "auto-gop-nvenc.mp4", cfg)
        self.assertEqual(cmd[cmd.index("-g") + 1], "50")

    def test_real_nvenc_keyframes_and_seek(self):
        check = v.run_hidden([v.FFMPEG, "-v", "error", "-f", "lavfi", "-i",
                              "testsrc2=s=160x90:d=0.1", "-c:v", "hevc_nvenc", "-f", "null", "-"], timeout=20)
        if check.returncode:
            self.skipTest("NVENC unavailable on this host")
        cfg = self.config(normalize="off")
        cfg.update(proc="both", enc="hevc_nvenc", preset="p5", depth="10 bit")
        cfg["adv"]["hwaccel"] = True
        dst = self.root / "real-nvenc.mp4"
        run(*self.app._build_cmd(self.info(), dst, cfg))
        self.app._validate_output(dst, self.info(), cfg)
        packets = json.loads(run(v.FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_packets",
                                 "-show_entries", "packet=pts_time,flags", "-of", "json", dst))["packets"]
        key_times = sorted(float(p["pts_time"]) for p in packets if "K" in p["flags"])
        self.assertGreaterEqual(len(key_times), 4)
        self.assertLessEqual(max(b - a for a, b in zip(key_times, key_times[1:])), 2.05)
        # Input seeking exercises the index and random access decoding.
        raw = run(v.FFMPEG, "-v", "error", "-xerror", "-ss", "5", "-i", dst,
                  "-map", "0:v:0", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-")
        self.assertEqual(len(raw), 160 * 90 * 3)

    def test_output_validation_rejects_single_keyframe(self):
        cfg = self.config(normalize="off")
        cfg.update(proc="both", audio="none")
        dst = self.root / "bad-gop.mp4"
        cmd = self.app._build_cmd(self.info(), dst, cfg)
        cmd[cmd.index("-g") + 1] = "999999"
        force_index = cmd.index("-force_key_frames")
        del cmd[force_index:force_index + 2]
        cmd[-1:-1] = ["-sc_threshold", "0"]
        run(*cmd)
        with self.assertRaisesRegex(RuntimeError, "Missing periodic keyframes"):
            self.app._validate_output(dst, self.info(), cfg)

    def test_real_gpu_sharpen_preserves_ten_bit_output(self):
        v.probe_gpu_sharpen()
        if not v._GPU_SHARPEN_OK:
            self.skipTest("OpenCL sharpening not available")
        cfg = self.config(normalize="off")
        cfg.update(proc="both", enc="hevc_nvenc", preset="p5", depth="10 bit")
        cfg["adv"].update(sharpen=.6, sharpen_gpu=True, hwaccel=True)
        dst = self.root / "real-gpu-sharpen10.mp4"
        cmd = self.app._build_cmd(self.info(), dst, cfg)
        self.assertIn("unsharp_opencl", cmd[cmd.index("-vf") + 1])
        run(*cmd)
        self.assertEqual(v.probe(dst)["pix_fmt"], "yuv420p10le")
        self.app._validate_output(dst, self.info(), cfg)

    def test_batch_continues_after_invalid_destination_and_protects_source(self):
        cfg = self.config(normalize="off")
        cfg.update(out_root=self.root, collision="overwrite", skip_bigger=False, keep_partial=False)
        bad = dict(self.info(), dst=self.source, completed=False)
        good = dict(self.info(), dst=self.root / "after-error.mp4", completed=False)
        stamp = fingerprint(self.source)
        self.app.files = [bad, good]
        self.app._convert_worker(cfg)
        self.assertEqual(bad["job_state"], "error")
        self.assertEqual(good["job_state"], "done")
        self.assertEqual(fingerprint(self.source), stamp)
        self.assertEqual(list(self.root.glob("*.vbc-part-*")), [])

    def test_web_optimized_and_metadata_switches_change_output(self):
        source = self.root / "tagged.mp4"
        run(v.FFMPEG, "-v", "error", "-y", "-i", self.source, "-map", "0", "-c", "copy",
            "-metadata", "title=Keep this title", "-metadata", "comment=User comment", source)
        info = dict(self.info(), path=source)
        for enabled in (True, False):
            cfg = self.config(normalize="off")
            cfg.update(web_optimized=enabled, pass_metadata=enabled)
            dst = self.root / f"metadata-{enabled}.mp4"
            run(*self.app._build_cmd(info, dst, cfg))
            data = json.loads(run(v.FFPROBE, "-v", "error", "-show_format", "-of", "json", dst))
            self.assertEqual(data["format"]["tags"].get("title"), "Keep this title" if enabled else None)
            content = dst.read_bytes()
            self.assertEqual(content.find(b"moov") < content.find(b"mdat"), enabled)

    def test_failed_atomic_save_preserves_original_and_cleans_temp(self):
        path = self.root / "atomic.json"
        atomic_json(path, {"valid": True})
        with self.assertRaises(ValueError):
            atomic_json(path, {"bad": float("nan")})
        self.assertEqual(json.loads(path.read_text()), {"valid": True})
        self.assertEqual(list(self.root.glob("atomic.json.*.tmp")), [])

    def test_unique_path_reserves_missing_outputs_and_exceeds_1000(self):
        base = self.root / "collision.mp4"
        reserved = [base] + [base.with_name(f"collision ({i}).mp4") for i in range(2, 1001)]
        self.assertEqual(v.App._unique_path(base, reserved).name, "collision (1001).mp4")

    def test_scanning_failure_always_finishes(self):
        def failing_scan():
            raise OSError("Folder unavailable")
        self.app._run_scan(failing_scan)
        self.assertEqual(self.app.msgq.get_nowait(), ("scan_error", "Folder unavailable"))
        self.assertEqual(self.app.msgq.get_nowait(), ("scan_done", 0))

    def test_splitter_drag_resizes_contents_only_on_release(self):
        try:
            root = v.tk.Tk()
        except v.tk.TclError as exc:
            self.skipTest(str(exc))
        try:
            root.geometry("700x250")
            pane = v.DeferredPanedWindow(root)
            pane.pack(fill="both", expand=True)
            left, right = v.tk.Frame(pane, width=320), v.tk.Frame(pane, width=320)
            pane.add(left, weight=0)
            pane.add(right, weight=1)
            root.update()
            x = pane.sashpos(0) + 2
            width = left.winfo_width()
            pane.event_generate("<ButtonPress-1>", x=x, y=100)
            for offset in (10, 20, 40, 60):
                pane.event_generate("<B1-Motion>", x=x + offset, y=100)
                root.update()
                self.assertEqual(left.winfo_width(), width)
            pane.event_generate("<ButtonRelease-1>", x=x + 60, y=100)
            root.update()
            self.assertGreater(left.winfo_width(), width)
        finally:
            root.destroy()

    def test_gop_respects_changed_output_fps_and_manual_interval(self):
        self.assertEqual(v.App._resolved_gop({"fps": 60}, dict(v.ADV_DEFAULTS, fps="24")), 48)
        self.assertEqual(v.App._resolved_gop({"fps": 29.97}, v.ADV_DEFAULTS), 60)
        self.assertEqual(v.App._resolved_gop({"fps": float("nan")}, v.ADV_DEFAULTS), 60)
        self.assertEqual(v.App._resolved_gop({"fps": 60}, dict(v.ADV_DEFAULTS, gop=123)), 123)

    def test_measurement_failure_is_explicit(self):
        with self.assertRaises(RuntimeError):
            self.app._measure_loudness(self.root / "missing.mp4", 0, v.ADV_A_DEFAULTS)

    def test_context_menu_file_sizes_and_savings_are_exact(self):
        source = self.root / "context-source.mp4"
        output = self.root / "context-output.mp4"
        source.write_bytes(b"x" * 10000)
        output.write_bytes(b"x" * 7250)
        stats = v.App._video_size_stats({"path": source, "dst": output})
        self.assertEqual(stats[:3], (10000, 7250, 2750))
        self.assertAlmostEqual(stats[3], 27.5)
        self.assertEqual(v.App._exact_size_text(1024), "1 024 B (1.00 KiB)")
        self.assertIsNone(v.App._video_size_stats({"path": self.root / "missing.mp4"}))

    def test_worker_failure_always_notifies_ui(self):
        with patch.object(v.App, "_convert_worker_impl", side_effect=OSError("disk full")):
            self.app._convert_worker({})
        events = []
        while not self.app.msgq.empty():
            events.append(self.app.msgq.get_nowait())
        self.assertEqual([kind for kind, _ in events], ["log", "worker_error", "finished"])
        self.assertTrue(events[-1][1]["fatal"])

    def test_project_roundtrip_and_changed_files(self):
        info = self.info()
        dst = self.root / "completed.mp4"
        dst.write_bytes(b"output")
        settings = {"audio": "192", "out": str(self.root)}
        key = settings_key(settings)
        info.update(dst=dst, job_state="done", job_key=key,
                    source_stamp=fingerprint(self.source), output_stamp=fingerprint(dst))
        self.assertTrue(is_complete(info, key))
        self.app.files = [info]
        self.app.project_path = self.root / "project.vbc.json"
        self.app.project_settings = settings
        self.app._write_project()
        restored = read_project(self.app.project_path)["files"][0]
        self.assertTrue(is_complete(restored, key))
        self.assertFalse(is_complete(restored, settings_key(dict(settings, audio="256"))))
        dst.write_bytes(b"modified output")
        self.assertFalse(is_complete(restored, key))

    def test_resume_skips_complete_and_replaces_incomplete(self):
        cfg = self.config(normalize="off")
        cfg.update(out_root=self.root, collision="skip", skip_bigger=False, keep_partial=True)
        completed = self.info()
        completed.update(completed=True, dst=self.root / "already.mp4")
        completed["dst"].write_bytes(b"do not touch")
        unfinished = self.info()
        unfinished.update(completed=False, dst=self.root / "unfinished.mp4", resume_owned=True)
        unfinished["dst"].write_bytes(b"partial")
        self.app.files = [completed, unfinished]
        self.app._convert_worker(cfg)
        self.assertEqual(completed["dst"].read_bytes(), b"do not touch")
        self.assertEqual(unfinished["job_state"], "done")
        self.assertEqual(v.probe(unfinished["dst"])["naudio"], 2)

    def test_gui_defaults_and_settings_roundtrip(self):
        try:
            with patch.object(v.App, "_probe_encoders", lambda app: None):
                app = v.App()
        except v.tk.TclError as exc:
            self.skipTest("Tk runtime unavailable in this headless test environment: " + str(exc))
        app.withdraw()
        try:
            settings = app._settings_data()
            self.assertEqual(settings["in"], "")
            self.assertEqual(settings["out"], "")
            self.assertEqual(settings["pct"], 60)
            self.assertEqual(settings["pct_min"], "1000")
            self.assertEqual(settings["pct_max"], "31000")
            self.assertEqual(settings["enc"], "hevc_nvenc")
            self.assertEqual(settings["audio"], "192")
            self.assertEqual(settings["adv_a"], v.ADV_A_DEFAULTS)
            self.assertEqual(v.detect_profile(settings["adv"]), "balanced")
            self.assertFalse(settings["adv"]["sharpen_gpu"])
            self.assertEqual(app.quick_scale_var.get(), v.loc(v.QUICK_SCALES)["orig"])
            self.assertEqual(app.quick_fps_var.get(), v.loc(v.QUICK_FPS)["orig"])
            app.quick_scale_var.set(v.loc(v.QUICK_SCALES)["1080"])
            app.quick_fps_var.set(v.loc(v.QUICK_FPS)["24"])
            app._on_quick_video_change()
            self.assertEqual(app.adv["scale"], "1080")
            self.assertEqual(app.adv["fps"], "24")
            app._apply_advanced(dict(v.ADV_DEFAULTS))
            app.audio_var.set(v.loc(v.AUDIO_MODES)["copy"])
            self.assertEqual(str(app.audio_codec_cb.cget("state")), "disabled")
            app.audio_var.set(v.loc(v.AUDIO_MODES)["192"])
            self.assertEqual(str(app.audio_codec_cb.cget("state")), "readonly")
            app.audio_codec_var.set(v.loc(v.AUDIO_CODECS)["libopus"])
            app._on_audio_codec_change()
            selected = app._settings_data()
            self.assertEqual(selected["adv_a"]["codec"], "libopus")
            self.assertEqual(selected["audio"], "192")
            altered = dict(settings, audio="256", out=str(self.root), **{"in": str(self.root)})
            app._load_settings(altered)
            self.assertEqual(app._settings_data(), altered)
            # Removing a sorted row must not append to the list being iterated,
            # reset completed states, or change which file an item ID refers to.
            for name, duration in [("Z.mp4", 100), ("A.mp4", 9), ("B.mp4", 20)]:
                app._add_row(dict(self.info(), rel=Path(name), duration=duration))
            app.tree.set("2", "state", "custom status")
            app._sort_tree("dur")
            self.assertEqual(app.tree.get_children(), ("1", "2", "0"))
            app._remove_video_row("0")
            self.assertEqual([str(f["rel"]) for f in app.files], ["A.mp4", "B.mp4"])
            self.assertEqual(app.tree.get_children(), ("0", "1"))
            self.assertEqual(app.tree.set("1", "state"), "custom status")
            app._sort_tree("dur")
            self.assertEqual(app.tree.get_children(), ("1", "0"))
            self.assertTrue(self.source.exists())
            app._toggle_settings_panel()
            self.assertTrue(app._settings_hidden)
            app._toggle_settings_panel()
            self.assertFalse(app._settings_hidden)
            # Freeze the in-flight job and update only the next queued file.
            app.running = True
            app.files[0].update(job_state="encoding", encode_cfg={"marker": "keep current"})
            app.files[1].update(job_state="pending", encode_cfg={"marker": "replace pending"})
            app.web_optimized_var.set(False)
            app.pass_metadata_var.set(False)
            with patch.object(v.messagebox, "showinfo"):
                app._apply_remaining_settings()
            self.assertEqual(app.files[0]["encode_cfg"], {"marker": "keep current"})
            self.assertFalse(app.files[1]["encode_cfg"]["web_optimized"])
            self.assertFalse(app.files[1]["encode_cfg"]["pass_metadata"])
            app.running = False
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
