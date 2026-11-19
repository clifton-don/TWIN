"""启动脚本的约束：bat 只能是 ASCII + CRLF（cmd 读 UTF-8 的 bat 会切错中文），ps1 要带 BOM（PowerShell 5.1 才认中文），
盘上自带的运行环境不进空白版、升级不碰。"""
import re

from conftest import TOOLS

import twin
import twin_update

ROOT = TOOLS.parent
BOM = b"\xef\xbb\xbf"
CURLY = "“”‘’"


def test_bat_ascii_crlf():
    raw = (ROOT / "Open_Web.bat").read_bytes()
    assert raw.isascii(), "Open_Web.bat 里只能有英文，中文提示放进 tools/launch.ps1"
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode()
    assert "launch.ps1" in text and "-WindowStyle Hidden" in text  # 不留黑色窗口
    assert "TWIN.exe" in text  # 有 TWIN.exe 时转给它，不闪窗口


def test_launcher_source_ascii_winexe():
    src = (TOOLS / "launcher" / "TWIN.cs").read_bytes()
    assert src.isascii(), "TWIN.cs 只能放英文：csc 没有 BOM 时按系统编码读"
    assert b"CreateNoWindow = true" in src
    assert "/TWIN.exe" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_gitattributes_keeps_bat_crlf():
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\.bat\s+.*eol=crlf", text, re.M)


def test_ps1_bom_and_no_curly_quotes():
    # PowerShell 5.1 没有 BOM 时按系统编码读中文，注释会吞掉下一行；中文弯引号会被当成字符串的引号
    files = sorted(TOOLS.glob("*.ps1"))
    assert {f.name for f in files} >= {"launch.ps1", "launch_ui.ps1", "make_logo.ps1"}
    for f in files:
        raw = f.read_bytes()
        assert raw.startswith(BOM) and not raw.startswith(BOM * 2), f.name  # 两个 BOM 时第一行会被当成命令报错
        assert not any(c in raw.decode("utf-8-sig") for c in CURLY), f.name


def test_pinned_hashes():
    text = (TOOLS / "launch.ps1").read_text(encoding="utf-8-sig")
    hashes = re.findall(r"Sha = '([0-9a-f]+)'", text)
    assert len(hashes) == 4 and all(len(h) == 64 for h in hashes)


def test_logo_assets():
    ico = (TOOLS / "web" / "logo.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00" and int.from_bytes(ico[4:6], "little") >= 4
    assert (TOOLS / "web" / "logo-64.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_runtime_not_shipped_or_overwritten():
    assert "runtime" in twin.BLANK_SKIP
    assert not twin_update._keep("tools/runtime/python/python.exe")
    assert not twin_update._keep("tools/runtime/KeePassXC/KeePassXC.exe")
    assert twin_update._keep("tools/launch.ps1")
    assert twin_update._keep("tools/launch_ui.ps1")


def test_mac_launcher_shipped():
    assert "Open_Web.command" in twin.BLANK_FILES
    text = (ROOT / "Open_Web.command").read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash") and "\r\n" not in text
