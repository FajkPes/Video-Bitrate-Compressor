@echo off
setlocal
cd /d "%~dp0"
title Video Bitrate Compressor - Installation Check

if not exist "VideoBitrateCompressor.exe" (
    echo ERROR: VideoBitrateCompressor.exe is missing.
    pause
    exit /b 1
)

start "" /wait "VideoBitrateCompressor.exe" --check
set "check_code=%errorlevel%"
if %check_code%==0 (
    echo Installation check passed. The app, FFmpeg, FFprobe and drag-and-drop support are available.
) else (
    echo Installation check failed. Extract the complete release ZIP again and keep all files together.
)
echo.
pause
exit /b %check_code%

rem Created by FajkPes with assistance from ChatGPT Codex and Claude Code.
