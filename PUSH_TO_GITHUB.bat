@echo off
title R1 FLASH ULTRA - SMART GITHUB PUSH TOOL
cd /d "%~dp0"
echo Starting GitHub Auto-Push...
python push_to_github.py
if errorlevel 1 (
    echo.
    echo [!] An error occurred during push.
)
echo.
pause
