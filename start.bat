@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 from python.org, then run this file again.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 (
  echo Python 3.12 is required. Install it and retry.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check internet access and retry.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
