@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Video Bitrate Compressor

rem --- samostatna aplikace ma vlastni identitu pro Windows Defender ---
if exist "%~dp0VideoBitrateCompressor.exe" (
    start "" "%~dp0VideoBitrateCompressor.exe"
    exit /b 0
)

rem --- spustit bez konzolového okna, pokud je k dispozici pythonw ---
where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw "video_compressor.py"
    exit /b 0
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Python nebyl nalezen v PATH.
    echo   Nainstaluj Python 3 z https://www.python.org/downloads/
    echo   a pri instalaci zaskrtni "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

python "video_compressor.py"
if %errorlevel% neq 0 (
    echo.
    echo   Aplikace skoncila s chybou %errorlevel%.
    pause
)
