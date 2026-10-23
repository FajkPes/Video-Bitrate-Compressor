@echo off
setlocal
cd /d "%~dp0"
py -3 -m PyInstaller --noconfirm --clean VideoBitrateCompressor.spec
if errorlevel 1 exit /b %errorlevel%
echo EXE is in dist. For a portable package, copy it beside README.md and the tools folder containing FFmpeg and FFprobe.
