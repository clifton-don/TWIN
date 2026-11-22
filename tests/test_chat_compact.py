"""聊长了自动压缩：总结怎么生成、怎么带进对话、存档时下标怎么跟着走。全用假数据和假的 AI 回应。"""
import json

import pytest

import twin_ai


@pytest.fixture
def fake_model(monkeypatch):
    box = {}

    def call(system, messages, provider=None, max_tokens=4000):
        box["system"], box["text"], box["max"] = system, messages[0]["content"], max_tokens
        return " 要点：他在准备周末旅行。 "
    monkeypatch.setattr(twin_ai, "call_model", call)
    monkeypatch.setattr(twin_ai, "active_provider", lambda pid=None: {"kind": "openai"})
    return box


def test_compact_merges_old_summary(fake_model):
    out = twin_ai.compact_chat("旧总结：喜欢爬山", [{"role": "user", "content": "周末去哪"}, {"role": "assistant", "content": "去郊外"}])
    assert out == "要点：他在准备周末旅行。"
    assert "旧总结：喜欢爬山" in fake_model["text"] and "我：周末去哪" in fake_model["text"] and "AI：去郊外" in fake_model["text"]


def test_compact_blocks_sensitive_values(fake_model):
    with pytest.raises(RuntimeError):
        twin_ai.compact_chat("", [{"role": "user", "content": "我的手机 13812345678"}])
    assert "text" not in fake_model  # 没发出去


def test_summary_goes_into_system_prompt(monkeypatch):
    import twin_org
    monkeypatch.setattr(twin_ai, "system_prompt", lambda: "SYS")
    monkeypatch.setattr(twin_ai, "detail_context_with_sources", lambda m: ("", []))
    monkeypatch.setattr(twin_org, "context", lambda m: "")
    sys_, msgs = twin_ai._prepare([{"role": "user", "content": "接着说"}], summary="前面定了去郊外")
    assert "前面定了去郊外" in sys_ and msgs == [{"role": "user", "content": "接着说"}]
    sys2, _ = twin_ai._prepare([{"role": "user", "content": "接着说"}])
    assert "前面部分的总结" not in sys2


def test_save_chat_keeps_summary_and_shifts_index(monkeypatch, tmp_path):
    import twin_web
    monkeypatch.setattr(twin_web, "CHATS", tmp_path)
    monkeypatch.setattr(twin_web, "chat_file", lambda cid: tmp_path / f"{cid}.json")
    msgs = [{"role": "user", "content": str(i)} for i in range(210)]
    j = twin_web.save_chat({"id": "abc", "title": "t", "messages": msgs, "summary": {"upto": 150, "text": "总结"}})
    data = json.loads((tmp_path / f"{j['id']}.json").read_text(encoding="utf-8"))
    assert len(data["messages"]) == 200 and data["summary"] == {"upto": 140, "text": "总结"}
