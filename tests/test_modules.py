"""twin_ai 拆成真模块后的约束：外面通过 twin_ai.xxx 用的名字都在，从哪个模块开始导入都行。"""
import importlib
import subprocess
import sys

import pytest
from conftest import TOOLS

import twin_ai

# 其他程序（twin_web、twin_cards、插件……）通过 twin_ai.xxx 用到的名字
PUBLIC = """DASHBOARD LANG LOOSE _cell _clean _find_board _icon_host _touch active_provider add_feedback ai_opinion apply_action
ask ask_stream board boards call_model chat_title check_outgoing draw_icon due_reviews edit_home_links ensure_weekly export_text
find_icon frontmatter geocode home home_links icon_file ideas latest_weekly load_config local_score make_brief make_news
make_suggest make_weekly mark_suggest news_star news_starred news_today parse_json_block profile project_parents public_config
review_decision rhythm save_icon save_job_decision save_profile today update_config upgrade_apply upgrade_payload upgrade_run
weather weather_tips""".split()

PARTS = ["jobs", "boards", "reports", "news", "day", "home"]


@pytest.mark.parametrize("name", PUBLIC)
def test_public_names(name):
    assert hasattr(twin_ai, name)


@pytest.mark.parametrize("first", ["twin_ai"] + [f"twin_ai_parts.{p}" for p in PARTS])
def test_import_from_any_entry(first):
    # 新进程里从不同模块开始导入，循环依赖不能报错
    code = f"import sys; sys.path.insert(0, {str(TOOLS)!r}); import {first}; import twin_ai; twin_ai.boards; twin_ai.make_brief"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_no_exec_loading():
    src = (TOOLS / "twin_ai.py").read_text(encoding="utf-8")
    assert "exec(" not in src


def test_icon_cache_in_tools():
    home = importlib.import_module("twin_ai_parts.home")
    assert home.SI_CACHE.parent == TOOLS / ".cache"


def test_helpers():
    jobs = importlib.import_module("twin_ai_parts.jobs")
    home = importlib.import_module("twin_ai_parts.home")
    assert jobs._num_or_none("3.5") == 3.5 and jobs._num_or_none("x") is None and jobs._num_or_none(None) is None
    assert jobs._num("x") == 0.0
    tag = '<link rel="icon" type="image/svg+xml" href="/a.svg">'
    assert (home._tag_attr(tag, "rel"), home._tag_attr(tag, "href"), home._tag_attr(tag, "media")) == ("icon", "/a.svg", "")
    assert twin_ai._as_list([1], []) == [1] and twin_ai._as_list("x", ["f"]) == ["f"] and twin_ai._as_list(None, []) == []
