"""测试公共设置：把 tools/ 加进 import 路径，并提供一个临时的假知识库。

测试只用这里造的假数据，不读真实资料。
"""
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import twin  # noqa: E402


def md(privacy, body="", title="t"):
    """拼一个带 Frontmatter 的 md 文件内容；privacy=None 表示没有这个字段。"""
    head = ["---", "type: note", f"title: {title}"]
    if privacy is not None:
        head.append(f"privacy: {privacy}")
    head.append("---")
    return "\n".join(head) + "\n" + body


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """临时知识库根目录：twin.ROOT 指向这里，写文件用返回的 write(rel, text)。"""
    monkeypatch.setattr(twin, "ROOT", tmp_path)

    def write(rel, text):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    return write
