@echo off
cd /d "%~dp0"
python daily_login_ceremony.py --check-only %*
pause
