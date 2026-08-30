@echo off
setlocal
cd /d "%~dp0"
title Video Bitrate Compressor

if exist "VideoBitrateCompressor.exe" (
    start "" "VideoBitrateCompressor.exe"
    exit /b 0
)

where pyw >nul 2>&1
if %errorlevel%==0 (
    start "" pyw -3 "video_compressor.py"
    exit /b 0
)

where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw "video_compressor.py"
    exit /b 0
)

echo.
echo VideoBitrateCompressor.exe was not found and Python 3 is not installed.
echo Download the complete Windows release from:
echo https://github.com/FajkPes/Video-Bitrate-Compressor/releases/latest
echo.
pause
exit /b 1

rem Created by FajkPes with assistance from ChatGPT Codex and Claude Code.
