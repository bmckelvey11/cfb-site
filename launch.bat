@echo off
cd /d "%~dp0"
start "" http://127.0.0.1:5000
python -m cfb_system_maker web --port 5000
pause
