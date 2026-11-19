@echo off
rem TWIN launcher. Keep this file ASCII-only: cmd mis-reads UTF-8 batch files.
rem All checks (portable Python, KeePassXC) and messages live in tools\launch.ps1.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launch.ps1" %*
if errorlevel 1 pause
