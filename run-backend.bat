@echo off
cd /d "%~dp0"
backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --port 8000
