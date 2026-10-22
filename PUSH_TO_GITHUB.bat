@echo off
cd /d "%~dp0"
start "" pythonw push_to_github.py 2>nul || python push_to_github.py
