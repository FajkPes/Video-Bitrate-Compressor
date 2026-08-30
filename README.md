# Video Bitrate Compressor

A practical Windows batch encoder that compresses every video to a percentage of **its own source bitrate**. It was created to shrink mixed collections consistently—for example, reducing many videos to roughly 50% without calculating a different target bitrate for every file.

## Highlights

- Percentage, fixed-bitrate, and bitrate-cap modes
- Batch queue, folders, individual files, drag and drop, and optional recursion
- HEVC/H.265, H.264, and AV1 options through NVIDIA, Intel, AMD, or CPU encoders
- Resolution, frame-rate, rotation, deinterlacing, denoise, rate-control, and advanced FFmpeg controls
- Audio passthrough or re-encoding, multiple audio tracks, channel/sample-rate controls, timing offset, and EBU R128 loudness normalization
- MP4, MKV, MOV, and source-container output
- Pause, safe stop, playable partial-file option, collision handling, and source-overwrite protection
- English by default with optional Czech available inside the app

## Download and run

1. Open the [latest release](https://github.com/FajkPes/Video-Bitrate-Compressor/releases/latest).
2. Download `Video-Bitrate-Compressor-v1.2.0-Windows-x64.zip`.
3. Extract the **entire ZIP** to a normal folder.
4. Double-click `Start Video Bitrate Compressor.bat` or `VideoBitrateCompressor.exe`.

The complete release includes the app runtime, FFmpeg, FFprobe, and drag-and-drop support. Python is not required. Keep the extracted files together. `Check Installation.bat` performs a read-only dependency check.

## Basic use

1. Choose a source folder or add files directly.
2. Choose a different destination folder.
3. Leave **Percentage of original bitrate** selected and set the desired percentage.
4. Pick an encoder. The default CPU encoder works without a specific GPU; supported hardware encoders are faster.
5. Review audio settings, then choose **Scan Folder** and **Start Encode**.

The original videos are not edited. Completed results are written to the destination through temporary `.vbc-part` files and moved into place only after FFmpeg finishes. The app blocks any destination path that resolves to a source file.

## Audio normalization

Open **Audio Options** and select either the precise two-pass or faster one-pass EBU R128 mode. The default target is `-14 LUFS`, with adjustable true peak and loudness range. Normalization requires re-encoding the selected audio tracks.

## Source setup

Python 3.10+ with Tkinter is recommended. Install the one Python dependency with:

```powershell
py -3 -m pip install -r requirements.txt
py -3 video_compressor.py
```

Place `ffmpeg.exe` and `ffprobe.exe` next to the script or add both to `PATH`. The release ZIP already includes them.

To create the portable Windows build, install `requirements-build.txt`, keep FFmpeg and FFprobe beside the source, and run `build_windows.bat`.

## Notes

- Actual file-size reduction varies with container overhead, audio settings, codec efficiency, and source complexity.
- Hardware encoding depends on compatible drivers and hardware. Use `libx265` or `libx264` CPU encoding when hardware initialization is unavailable.
- Expert FFmpeg arguments are intentionally powerful; invalid options can make an encode fail, but the source file remains untouched.

## License and credits

The application source is licensed under the [MIT License](LICENSE). The Windows release includes separate third-party components under their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Created by **FajkPes** with assistance from **ChatGPT Codex** and **Claude Code**.
