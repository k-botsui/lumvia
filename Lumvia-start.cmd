@echo off
cd /d "%~dp0"
py -3 scripts\run_compose.py start
if errorlevel 1 pause
