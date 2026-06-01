@echo off
cd /d "%~dp0"
if defined CIOVACCO_NOTEBOOKLM_NOTEBOOK_ID (
  python scrape_ciovacco.py --sync-notebooklm
) else (
  python scrape_ciovacco.py
)
