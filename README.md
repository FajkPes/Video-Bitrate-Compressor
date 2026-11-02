# Video Bitrate Compressor

A Windows batch compressor that reduces each video's bitrate relative to its original bitrate.

## Why use it?

Video Bitrate Compressor reduces the bitrate of each video relative to its own source bitrate. It is intended for processing a batch without manually calculating a new bitrate for every file.

## Features

- Queue multiple videos and apply settings to the remaining items.
- Choose CPU encoding or NVIDIA NVENC when available, with speed and quality profiles.
- Set bitrate, resolution and frame-rate limits, audio behavior and output container.
- Preserve common metadata and optionally optimize MP4/MOV files for web playback.
- Check duration, audio tracks, keyframes and a seek before accepting an output.

## Download and start

Download the Windows ZIP from [Releases](https://github.com/FajkPes/Video-Bitrate-Compressor/releases/latest), extract everything and run `VideoBitrateCompressor.exe`. The `tools` folder contains FFmpeg and FFprobe and must stay with the application.

Add videos, choose the bitrate percentage and profile, and start the queue. Resolution options act as upper limits rather than enlarging smaller sources. Existing outputs are protected by the selected collision behavior; a temporary output is checked before it becomes the final file.

NVENC and GPU sharpening require supported hardware and FFmpeg capabilities. GPU sharpening can be slower when transfers and initialization outweigh its benefit. Windows Controlled Folder Access may require allowing both the application and `tools/ffmpeg.exe`. The interface currently starts in Czech and can be switched to English.

[Detailed documentation](README-DETAILS.md) · [All releases](https://github.com/FajkPes/Video-Bitrate-Compressor/releases)

## Credits

**Idea, concept and design:** FajkPes  
**Coding:** ChatGPT Codex, Claude and Google Antigravity
