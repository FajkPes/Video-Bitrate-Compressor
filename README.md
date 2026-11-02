# Video Bitrate Compressor

A Windows batch tool for compressing video, re-encoding or normalizing audio, and managing conversions without configuring FFmpeg commands by hand.

## Why use it?

The app was built for more than one common job: reduce video sizes across a batch while accounting for each source's bitrate, or fix and convert audio in existing videos without re-encoding the picture. It brings video and audio controls, queue management and output checks together in one Windows interface.

## Features

- Batch-process videos with a percentage of each source's bitrate, a fixed bitrate, or a fixed cap that keeps lower-bitrate sources unchanged.
- Re-encode **only the audio** while copying the video stream without recompression; useful when the picture is already fine but the audio needs changing.
- Normalize audio using one-pass or two-pass EBU R128 loudness processing; adjust target LUFS, true peak and loudness range.
- Choose audio passthrough or re-encoding, codec and bitrate; retain all audio tracks or select the first, adjust channel layout, sample rate and audio offset.
- Queue multiple videos and apply settings to the remaining items.
- Choose CPU encoding or NVIDIA NVENC when available, with speed and quality profiles.
- Set bitrate, resolution and frame-rate limits, audio behavior and output container.
- Preserve common metadata and optionally optimize MP4/MOV files for web playback.
- Check duration, audio tracks, keyframes and a seek before accepting an output.

## Download and start

Download the Windows ZIP from [Releases](https://github.com/FajkPes/Video-Bitrate-Compressor/releases/latest), extract everything and run `VideoBitrateCompressor.exe`. The `tools` folder contains FFmpeg and FFprobe and must stay with the application.

Add videos to the queue. For video compression, choose **Video + audio**, a bitrate mode and an encoding profile. To change audio without re-encoding the picture, choose **Audio only — passthru video**, select an audio bitrate or enable normalization, and start the queue. Normalization re-encodes the audio track; copying video preserves the encoded video stream rather than re-rendering its frames. For normalization, two-pass EBU R128 first measures the audio and then applies the correction; the one-pass mode is faster. Audio codec and container compatibility still matter. Resolution options act as upper limits rather than enlarging smaller sources. Existing outputs are protected by the selected collision behavior; a temporary output is checked before it becomes the final file.

NVENC and GPU sharpening require supported hardware and FFmpeg capabilities. GPU sharpening can be slower when transfers and initialization outweigh its benefit. Windows Controlled Folder Access may require allowing both the application and `tools/ffmpeg.exe`. The interface currently starts in Czech and can be switched to English.

[Detailed documentation](README-DETAILS.md) · [All releases](https://github.com/FajkPes/Video-Bitrate-Compressor/releases)

## Credits

**Idea, concept and design:** FajkPes  
**Coding:** ChatGPT Codex, Claude and Google Antigravity
