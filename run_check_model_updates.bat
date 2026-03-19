@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python check_model_updates.py
