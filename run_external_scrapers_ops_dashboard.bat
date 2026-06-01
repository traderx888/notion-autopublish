@echo off
setlocal
cd /d "%~dp0"
start "External Scrapers Ops Server" cmd /k python tools\external_scrapers_ops_server.py --host 127.0.0.1 --port 8765
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
start "" http://127.0.0.1:8765/
