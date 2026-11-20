"""项目时间线、开机自动启动、对话回答的依据。都不碰真实资料，开机启动用假的注册表。"""
import os
import shutil
import subprocess
import sys
import time
import types
from datetime import date

import pytest

import twin
import twin_ai
import twin_autostart
import twin_timeline


# ---------- 项目时间线 ----------

@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(twin, "PROJECTS", tmp_path / "03_Projects")
    monkeypatch.setattr(twin_timeline, "ROOT", tmp_path)
    twin_timeline._CACHE.clear()
    d = tmp_path / "03_Projects" / "台灯"
    d.mkdir(parents=True)
    (d / "index.md").write_text("---\nprivacy: internal\n---\n# 台灯\n", encoding="utf-8")

    def put(rel, day):
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        t = time.mktime(date.fromisoformat(day).timetuple()) + 3600
        os.utime(p, (t, t))
    return d, put


def test_timeline_months_kinds_versions(project):
    d, put = project
    put("V1_2024原版/main.ino", "2024-03-05")
    put("V1_2024原版/板子.kicad_pcb", "2024-03-20")
    put("V2_2026重做/外壳.step", "2026-01-10")
    put("02_docs/说明.pdf", "2026-01-11")
    put("node_modules/x.js", "2026-02-01")  # 依赖文件夹不算
    t = twin_timeline.timeline("03_Projects/台灯/index.md")
    assert t["start"] == "2024-03-05" and t["last"] == "2026-01-11" and t["files"] == 4
    months = {m["month"]: m for m in t["months"]}
    assert set(months) == {"2024-03", "2026-01"}
    assert dict(months["2024-03"]["kinds"]) == {"代码": 1, "电路板": 1}
    assert [v["name"] for v in t["versions"]] == ["V1_2024原版", "V2_2026重做"]
    assert t["versions"][0]["from"] == "2024-03-05" and t["versions"][0]["to"] == "2024-03-20"


def test_timeline_ignores_twin_own_files(project):
    d, put = project
    (d / "board.md").write_text("x", encoding="utf-8")
    t = twin_timeline.timeline("03_Projects/台灯")
    assert t["files"] == 0 and t["months"] == []


@pytest.mark.skipif(not shutil.which("git"), reason="没装 git")
def test_timeline_reads_git(project):
    d, put = project
    put("main.c", "2025-05-01")
    env = {**os.environ, "GIT_AUTHOR_DATE": "2025-05-02T10:00:00", "GIT_COMMITTER_DATE": "2025-05-02T10:00:00"}
    for cmd in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "第一版能亮了"]):
        subprocess.run(["git", "-C", str(d), *cmd], check=True, env=env, capture_output=True)
    t = twin_timeline.timeline("03_Projects/台灯", fresh=True)
    assert t["commits"] == 1
    m = [x for x in t["months"] if x["month"] == "2025-05"][0]
    assert m["commits"][0] == {"date": "2025-05-02", "msg": "第一版能亮了"}


def test_timeline_rejects_non_project(project):
    with pytest.raises(ValueError):
        twin_timeline.timeline("../outside")
    with pytest.raises(ValueError):
        twin_timeline.timeline("03_Projects")


# ---------- 开机自动启动（假注册表）----------

class FakeReg(types.SimpleNamespace):
    def __init__(self):
        super().__init__(HKEY_CURRENT_USER="HKCU", KEY_SET_VALUE=2, REG_SZ=1, store={})

    def OpenKey(self, *a):
        class K:
            def __enter__(self):
                return self

            def __exit__(self, *e):
                return False
        return K()

    def QueryValueEx(self, k, name):
        if name not in self.store:
            raise OSError("missing")
        return self.store[name], 1

    def SetValueEx(self, k, name, _, __, value):
        self.store[name] = value

    def DeleteValue(self, k, name):
        self.store.pop(name)


@pytest.fixture
def fake_win(tmp_path, monkeypatch):
    root = tmp_path / "TWIN"
    root.mkdir()
    (root / "TWIN.exe").write_bytes(b"MZ")
    reg = FakeReg()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(twin_autostart, "ROOT", root)
    monkeypatch.setattr(twin_autostart, "_reg", lambda: reg)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return root, reg


def test_autostart_on_off(fake_win):
    root, reg = fake_win
    assert twin_autostart.status() == {"supported": True, "on": False}
    st = twin_autostart.set_on(True)
    assert st["on"] and st["points_here"]
    cmd = reg.store["TWIN"]
    assert "--find" in cmd and "--no-browser" in cmd and twin_autostart._copy_path().exists()
    assert twin_autostart.set_on(False)["on"] is False and not twin_autostart._copy_path().exists()


def test_autostart_needs_exe(fake_win):
    root, reg = fake_win
    (root / "TWIN.exe").unlink()
    st = twin_autostart.status()
    assert st["supported"] is False and "Open_Web.bat" in str(st["why"])
    with pytest.raises(RuntimeError):
        twin_autostart.set_on(True)


def test_autostart_command_finds_by_folder():
    cmd = twin_autostart._command(exe=r"C:\x\TWIN-autostart.exe", root=r"E:\备份\TWIN")
    assert cmd == r'"C:\x\TWIN-autostart.exe" --find "备份\TWIN" --prefer "E:" --no-browser'


# ---------- 对话回答的依据 ----------

def test_sources_are_relevant_docs_not_all_boards(tmp_path, monkeypatch):
    import twin_search
    files = [("03_Projects/台灯/board.md", "| 任务 |"), ("03_Projects/台灯/02_docs/外壳.md", "外壳 用 白色 磨砂 PLA 打印 外壳 外壳"),
             ("01_Skills/焊接.md", "焊接 温度 烙铁")]
    for rel, text in files:  # 相关度索引从盘上读文件
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    monkeypatch.setattr(twin_search, "ROOT", tmp_path)
    monkeypatch.setattr(twin_ai, "detail_files", lambda: files)
    monkeypatch.setattr(twin_ai, "boards", lambda *a: [{"path": "03_Projects/台灯/board.md", "name": "台灯"}])
    monkeypatch.setattr(twin_ai, "DETAIL_INDEX", None)
    text, picked = twin_ai.detail_context_with_sources([{"role": "user", "content": "外壳用什么颜色打印"}])
    assert "03_Projects/台灯/board.md" in text  # 板块照样发给 AI
    assert picked == ["03_Projects/台灯/02_docs/外壳.md"]  # 但依据只列相关文档


# ---------- 新装的 TWIN 还没有 03_Projects 时也能建项目（只测判断，不真的建：boards 里的路径是导入时定死的）----------

def test_projects_folder_allowed_before_it_exists(monkeypatch):
    import twin_inbox
    import twin_ai_parts.boards as boards
    monkeypatch.setattr(twin_inbox, "targets", lambda: [])
    assert boards.parent_ok("03_Projects")
    assert not boards.parent_ok("05_Network") and not boards.parent_ok("../x")
