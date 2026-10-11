@echo off
cd /d "%~dp0"
py -3 scripts\run_compose.py login
if errorlevel 1 pause
