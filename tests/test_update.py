"""检查更新：没发过版本（404）不算错；连不上时给看得懂的话，不把原始报错丢给用户。"""
import io
import json
import urllib.error

import pytest

import twin_update


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(twin_update, "REPOS", {"gitee": "", "github": "someone/TWIN"})
    monkeypatch.setattr(twin_update, "CACHE", tmp_path / "update.json")

    def use(fn):
        monkeypatch.setattr(twin_update, "_get", fn)
    return use


def http_error(code):
    def fn(url, timeout=10):
        raise urllib.error.HTTPError(url, code, "x", {}, io.BytesIO(b""))  # type: ignore[arg-type]
    return fn


def test_no_release_yet_is_not_an_error(repo):
    repo(http_error(404))
    r = twin_update.check("0.27.0-beta", force=True)
    assert "error" not in r and r["newer"] is False and r["latest"] == "0.27.0-beta"


def test_offline_gives_plain_message(repo):
    def offline(url, timeout=10):
        raise urllib.error.URLError("getaddrinfo failed")
    repo(offline)
    r = twin_update.check("0.27.0-beta", force=True)
    assert r["error"].startswith("暂时连不上更新服务器") and "getaddrinfo" in r["detail"]
    assert "HTTP" not in r["error"]


def test_newer_release_found(repo):
    rel = {"tag_name": "v0.28.0-beta", "body": "notes", "html_url": "https://x",
           "assets": [{"name": "TWIN.zip", "browser_download_url": "https://x/TWIN.zip"}]}
    repo(lambda url, timeout=10: json.dumps(rel).encode())
    r = twin_update.check("0.27.0-beta", force=True)
    assert r["newer"] is True and r["latest"] == "0.28.0-beta" and r["url"].endswith(".zip")
