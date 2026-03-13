@echo off
setlocal

set ROOT=C:\Users\User\Documents\GitHub
set HOURS=8

python "%~dp0telegram_hub.py" --root "%ROOT%" --hours %HOURS% --send

if errorlevel 1 (
  echo Telegram hub failed with error %errorlevel%
  exit /b %errorlevel%
)

echo Telegram hub sent successfully.
exit /b 0

