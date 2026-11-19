@echo off
rem TWIN launcher, first run. Keep this file ASCII-only: cmd mis-reads UTF-8 batch files.
rem 1) Builds TWIN.exe here with the C# compiler that ships with Windows (source: tools\launcher\TWIN.cs).
rem 2) Hands off to TWIN.exe, which starts TWIN with no window at all. After this, just double-click TWIN.exe.
cd /d "%~dp0"
if exist "%~dp0TWIN.exe" goto run
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" goto fallback
"%CSC%" -nologo -target:winexe "-win32icon:%~dp0tools\web\logo.ico" "-out:%~dp0TWIN.exe" "%~dp0tools\launcher\TWIN.cs" >nul
if not exist "%~dp0TWIN.exe" goto fallback

:run
start "" "%~dp0TWIN.exe" %*
exit /b

:fallback
rem No compiler (very old Windows): run the PowerShell launcher hidden instead.
start "" powershell -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0tools\launch.ps1" %*
