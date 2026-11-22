"""DeepSeek 新模型：默认会先“思考”，TWIN 不显示思考，看起来像不回话。这里用假的服务端回应检查处理对不对。"""
import io
import json
import urllib.error

import pytest

import twin_ai

DS = {"name": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-pro", "api_key": "test"}


class Resp(io.BytesIO):
    def __init__(self, body, ctype="text/event-stream"):
        super().__init__(body.encode())
        self.headers = {"Content-Type": ctype}


def sse(*chunks):
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


@pytest.fixture
def sent(monkeypatch):
    """把发出去的请求记下来，回一段假的回应。"""
    box = {"reply": None, "payload": None}

    def fake(req, timeout=0):
        box["payload"] = json.loads(req.data)
        r = box["reply"]
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(twin_ai.urllib.request, "urlopen", fake)
    return box


def test_deepseek_thinking_off_and_old_names_mapped():
    p = twin_ai._openai_payload({**DS, "model": "deepseek-chat"}, "s", [], 100)
    assert p["model"] == "deepseek-flash" and p["thinking"] == {"type": "disabled"}
    assert twin_ai._openai_payload(DS, "s", [], 100)["model"] == "deepseek-v4-pro"
    other = twin_ai._openai_payload({**DS, "base_url": "https://api.moonshot.cn/v1", "model": "kimi-latest"}, "s", [], 100)
    assert "thinking" not in other and other["model"] == "kimi-latest"


def test_stream_skips_thinking_and_returns_answer(sent):
    sent["reply"] = Resp(sse({"choices": [{"delta": {"reasoning_content": "想一想"}}]},
                             {"choices": [{"delta": {"content": "你好"}}]},
                             {"choices": [{"delta": {"content": "！"}, "finish_reason": "stop"}]}))
    assert "".join(twin_ai.call_model_stream("s", [{"role": "user", "content": "hi"}], DS)) == "你好！"
    assert sent["payload"]["thinking"] == {"type": "disabled"}


def test_stream_only_thinking_gives_clear_error(sent):
    sent["reply"] = Resp(sse({"choices": [{"delta": {"reasoning_content": "想了很久"}, "finish_reason": "length"}]}))
    with pytest.raises(RuntimeError, match="思考"):
        list(twin_ai.call_model_stream("s", [], DS))


def test_unknown_model_name_explained(sent):
    body = io.BytesIO(b'{"error":{"message":"Model Not Exist","type":"invalid_request_error"}}')
    sent["reply"] = urllib.error.HTTPError("https://api.deepseek.com/chat/completions", 400, "Bad Request", {}, body)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="deepseek-flash"):
        twin_ai.call_model("s", [], {**DS, "model": "deepseek-pro"})


def test_think_on_streams_thinking_separately(sent):
    """开了“显示思考过程”：DeepSeek 打开思考，字数放宽，思考以 {"think": …} 单独给出，不混进回答。"""
    sent["reply"] = Resp(sse({"choices": [{"delta": {"reasoning_content": "想一想"}}]},
                             {"choices": [{"delta": {"content": "答案"}, "finish_reason": "stop"}]}))
    out = list(twin_ai.call_model_stream("s", [], DS, think=True))
    assert out == [{"think": "想一想"}, "答案"]
    assert sent["payload"]["thinking"] == {"type": "enabled"} and sent["payload"]["max_tokens"] >= 16000


def test_think_setting_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(twin_ai, "CONFIG_FILE", tmp_path / "ai.json")
    cfg = twin_ai.update_config({"providers": [{**DS, "id": "", "think": True}]})
    assert cfg["providers"][0]["think"] is True
