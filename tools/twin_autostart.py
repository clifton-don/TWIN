"""开机自动启动（只在 Windows 上）：设置里的开关。

打开时把 TWIN.exe 复制一份到 %LOCALAPPDATA%\\TWIN\\TWIN-autostart.exe，并在当前用户的“登录时启动”
（注册表 HKCU\\...\\Run，不需要管理员）里写一项。移动硬盘的盘符会变，所以它登录时按文件夹名在每个盘上找
TWIN（先找上次的盘），找到就在后台启动（不打开浏览器），盘没插就什么都不做。关掉时删掉这一项和那份复制。
"""
import os
import shutil
import sys
from pathlib import Path

from twin import ROOT

NAME = "TWIN"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _copy_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "TWIN" / "TWIN-autostart.exe"


def _command(exe=None, root=None):
    """写进“登录时启动”的命令：按 TWIN 文件夹相对盘根的位置找，先试现在这个盘。"""
    root = Path(root or ROOT)
    rel = str(root.relative_to(root.anchor)) or "."
    drive = root.drive or ""
    return f'"{exe or _copy_path()}" --find "{rel}"' + (f' --prefer "{drive}"' if drive else "") + " --no-browser"


def _reg():
    import winreg
    return winreg


def status():
    if sys.platform != "win32":
        return {"supported": False, "on": False, "why": "只有 Windows 上能设开机自动启动。"}
    if not (ROOT / "TWIN.exe").exists():
        return {"supported": False, "on": False, "why": "还没有 TWIN.exe：先双击一次 Open_Web.bat。"}
    winreg = _reg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value, _ = winreg.QueryValueEx(k, NAME)
    except OSError:
        return {"supported": True, "on": False}
    return {"supported": True, "on": True, "points_here": value == _command()}


def set_on(on):
    st = status()
    if not st["supported"]:
        raise RuntimeError(st["why"])
    winreg = _reg()
    copy = _copy_path()
    if on:
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "TWIN.exe", copy)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _command())
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, NAME)
        except OSError:
            pass
        copy.unlink(missing_ok=True)
    return status()


def refresh_copy():
    """TWIN.exe 重新编译过（比如升级后），开机启动用的那份也跟着换新。启动时调一次，出错不管。"""
    try:
        copy = _copy_path()
        src = ROOT / "TWIN.exe"
        if copy.exists() and src.exists() and src.stat().st_mtime > copy.stat().st_mtime:
            shutil.copy2(src, copy)
    except OSError:
        pass
