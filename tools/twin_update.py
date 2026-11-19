#!/usr/bin/env python3
"""检查更新和一键升级（只用 Python 标准库）。

  - 新版本发布在 Gitee / GitHub 的 Release 里，附件是 `python tools/twin.py blank` 打出来的空白版 zip。
  - 检查：每天最多问一次，只发一个请求，不带任何资料。
  - 也可以不联网：在“设置 → 版本”里选一个别人发给你的空白版 zip（本地升级包），后面步骤一样。
  - 升级：下载 zip → 先把现在的程序备份到 _export/ → 只覆盖程序和说明（tools、_TEMPLATES、README 等）。
    资料、对话、密码、_RULES 里你改过的规则一律不动（通用规则文件只在没有时补上）。重启后生效。
"""
import base64
import io
import json
import re
import time
import urllib.request
import zipfile
from pathlib import Path

import twin_plugins
from twin import BLANK_FILES, BLANK_SKIP, ROOT

# 发布的仓库，写成“用户名/仓库名”；两个都填就先问 Gitee（国内快），问不到再问 GitHub。都空着就不检查。
REPOS = {"gitee": "", "github": "clifton-don/TWIN"}
API = {"gitee": "https://gitee.com/api/v5/repos/{}/releases/latest", "github": "https://api.github.com/repos/{}/releases/latest"}
CACHE = Path(__file__).resolve().parent / ".cache" / "update.json"
MAX_ZIP = 50 * 1024 * 1024
OVERWRITE = {f for f in BLANK_FILES if not f.startswith("_RULES/")}  # 规则文件只补不改


def _vt(v):
    """0.18.0-beta → (0, 18, 0)，用来比大小。"""
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "TWIN", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_ZIP + 1)


def check(current, force=False):
    if not any(REPOS.values()):
        return {"current": current, "enabled": False}
    if not force and CACHE.exists() and time.time() - CACHE.stat().st_mtime < 86400:
        d = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        d, err = None, ""
        for host, repo in REPOS.items():
            if not repo:
                continue
            try:
                r = json.loads(_get(API[host].format(repo)))
                zips = [a for a in r.get("assets", []) if str(a.get("name", "")).endswith(".zip")]
                d = {"latest": r.get("tag_name", "").lstrip("v"), "notes": (r.get("body") or "")[:2000],
                     "url": zips[0]["browser_download_url"] if zips else "", "page": r.get("html_url", "")}
                break
            except Exception as e:  # 网络不通、仓库没发版：换下一个
                err = str(e)
        if not d:
            return {"current": current, "enabled": True, "error": f"检查不到更新：{err[:120]}"}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return {"current": current, "enabled": True, **d, "newer": bool(d.get("url")) and _vt(d["latest"]) > _vt(current)}


def _keep(rel):
    """zip 里的这个文件升级时要不要写：程序和说明覆盖，通用规则没有才补，其余（资料、分支说明）不碰。"""
    parts = rel.split("/")
    if ".." in parts or rel.startswith("/") or BLANK_SKIP & set(parts):
        return False
    if parts[:2] == ["tools", "plugins"] and len(parts) > 3 and parts[2] in twin_plugins.removed():  # 自己移除的插件不装回来
        return False
    if parts[0] in ("tools", "_TEMPLATES") or rel in OVERWRITE:
        return True
    return rel in BLANK_FILES and not (ROOT / rel).exists()


def apply(current):
    info = check(current, force=True)
    if not info.get("newer"):
        raise RuntimeError(info.get("error") or "已经是最新版了。")
    return _install(_get(info["url"], 120), current, info["latest"])


def apply_local(name, data, current):
    """本地升级包：网页上选的空白版 zip（data 是 data: URL）。只认比现在新的版本。"""
    try:
        raw = base64.b64decode(str(data).split(",", 1)[-1])
        z = zipfile.ZipFile(io.BytesIO(raw))
        src = z.read("TWIN/tools/twin_web.py").decode("utf-8")
    except (ValueError, KeyError, zipfile.BadZipFile):
        raise RuntimeError(f"“{name}”不是 TWIN 的升级包。要用 twin.py blank 打出来的空白版 zip。") from None
    m = re.search(r'^VERSION = "([^"]+)"', src, re.M)
    ver = m[1] if m else ""
    if not ver or _vt(ver) <= _vt(current):
        raise RuntimeError(f"这个包是 {ver or '未知版本'}，不比现在的 {current} 新，没有安装。")
    return _install(raw, current, ver)


def _install(data, current, version):
    if len(data) > MAX_ZIP:
        raise RuntimeError("更新包太大，不像是 TWIN，没有安装。")
    z = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in z.namelist() if n.startswith("TWIN/") and not n.endswith("/")]
    if "TWIN/tools/twin_web.py" not in names:
        raise RuntimeError("更新包里没有 TWIN 程序，没有安装。")
    backup = ROOT / "_export" / f"升级前备份-{current}-{time.strftime('%Y%m%d-%H%M')}.zip"
    backup.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as b:
        for f in [ROOT / x for x in OVERWRITE] + sorted((ROOT / "tools").rglob("*")) + sorted((ROOT / "_TEMPLATES").rglob("*")):
            if f.is_file() and not BLANK_SKIP & set(f.relative_to(ROOT).parts):
                b.write(f, f.relative_to(ROOT).as_posix())
    n = 0
    for name in names:
        rel = name[5:]
        if _keep(rel):
            out = ROOT / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(z.read(name))
            n += 1
    CACHE.unlink(missing_ok=True)
    return {"version": version, "files": n, "backup": backup.relative_to(ROOT).as_posix()}
