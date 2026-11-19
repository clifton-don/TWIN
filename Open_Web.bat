@echo off
rem TWIN launcher (fallback). Keep this file ASCII-only: cmd mis-reads UTF-8 batch files.
rem Prefer TWIN.exe (built on first run, no flashing window). Without it, run tools\launch.ps1 hidden.
cd /d "%~dp0"
if exist "%~dp0TWIN.exe" (
  start "" "%~dp0TWIN.exe" %*
) else (
  start "" powershell -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0tools\launch.ps1" %*
)
