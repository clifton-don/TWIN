"""启动脚本的约束：bat 只能是 ASCII + CRLF（cmd 读 UTF-8 的 bat 会切错中文），ps1 要带 BOM（PowerShell 5.1 才认中文），
盘上自带的运行环境不进空白版、升级不碰。"""
import re

from conftest import TOOLS

import twin
import twin_update

ROOT = TOOLS.parent


def test_bat_ascii_crlf():
    raw = (ROOT / "Open_Web.bat").read_bytes()
    assert raw.isascii(), "Open_Web.bat 里只能有英文，中文提示放进 tools/launch.ps1"
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode()
    assert "launch.ps1" in text and "-WindowStyle Hidden" in text  # 不留黑色窗口


def test_gitattributes_keeps_bat_crlf():
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\.bat\s+.*eol=crlf", text, re.M)


def test_ps1_has_bom_and_pinned_hashes():
    raw = (TOOLS / "launch.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    hashes = re.findall(r"Sha = '([0-9a-f]+)'", text)
    assert len(hashes) == 4 and all(len(h) == 64 for h in hashes)
    # PowerShell 把中文弯引号也当成字符串的引号，写进提示里会把字符串截断
    assert not any(c in text for c in "“”‘’")


def test_runtime_not_shipped_or_overwritten():
    assert "runtime" in twin.BLANK_SKIP
    assert not twin_update._keep("tools/runtime/python/python.exe")
    assert not twin_update._keep("tools/runtime/KeePassXC/KeePassXC.exe")
    assert twin_update._keep("tools/launch.ps1")


def test_mac_launcher_shipped():
    assert "Open_Web.command" in twin.BLANK_FILES
    text = (ROOT / "Open_Web.command").read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash") and "\r\n" not in text
