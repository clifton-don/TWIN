@echo off
rem TWIN launcher. Keep this file ASCII-only: cmd mis-reads UTF-8 batch files.
rem Starts tools\launch.ps1 with no console window; TWIN then lives in the tray (bottom-right).
rem Prompts and errors are shown as dialogs. Logs: tools\runtime\twin.log
cd /d "%~dp0"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0tools\launch.ps1" %*
