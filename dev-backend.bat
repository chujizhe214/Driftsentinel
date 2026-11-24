@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Local Python environment is missing. Run start-local.bat once to set it up.
    pause
    exit /b 1
)

echo Starting the local backend with automatic reload. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m scripts.dev_backend
if errorlevel 1 (
    echo If port 8000 is in use by DriftSentinel in Docker, run stop.bat and try again.
    pause
    exit /b 1
)
