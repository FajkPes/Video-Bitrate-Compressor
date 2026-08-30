# Video Bitrate Compressor 1.2.0

- Prepared the first public, portable Windows release.
- Made English the clean-install default while preserving the optional Czech interface.
- Removed personal saved paths and settings from the distribution.
- Replaced three Czech-only runtime messages with localized English output.
- Changed the clean-install encoder default to broadly compatible CPU-based x265; hardware encoders remain available.
- Added a self-contained Windows executable, English launchers, and a read-only installation check.
- Bundled FFmpeg and FFprobe so the release works offline after extraction.
- Kept the existing protections against overwriting source videos and incomplete destination files.
