@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
python --version >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  py -3 --version >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY goto nopy
%PY% tools\twin_web.py
if errorlevel 1 pause
exit /b

:nopy
echo.
echo  没找到 Python，TWIN 需要它才能运行。
echo  1. 打开 https://www.python.org/downloads/ ，点最上面黄色的 "Download Python" 按钮。
echo  2. 运行下载的安装包，第一页先勾上最下面的 "Add python.exe to PATH"，再点 "Install Now"。
echo  3. 装好后重新双击这个文件。
echo.
echo  Python was not found. Install it from https://www.python.org/downloads/
echo  (tick "Add python.exe to PATH" on the first page), then run this file again.
echo.
start "" https://www.python.org/downloads/
pause
