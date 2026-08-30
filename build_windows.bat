@echo off
setlocal
cd /d "%~dp0"

py -3 -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --name VideoBitrateCompressor ^
  --collect-all tkinterdnd2 ^
  video_compressor.py

if errorlevel 1 exit /b %errorlevel%
copy /y ffmpeg.exe "dist\VideoBitrateCompressor\ffmpeg.exe" >nul
copy /y ffprobe.exe "dist\VideoBitrateCompressor\ffprobe.exe" >nul
echo Build completed in dist\VideoBitrateCompressor

rem Created by FajkPes with assistance from ChatGPT Codex and Claude Code.
