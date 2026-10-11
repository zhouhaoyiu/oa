@echo off
cd /d "%~dp0"
python main2.py %*
if errorlevel 1 pause
