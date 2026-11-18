@echo off
cd /d "%~dp0"
docker compose -f "%~dp0compose.yaml" stop
if errorlevel 1 pause
