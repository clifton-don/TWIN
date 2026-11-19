#!/usr/bin/env python3
"""插件：tools/plugins/<名字>/ 里放 plugin.py（后端）和 plugin.js（网页），在侧栏左下角抽屉里的“插件”里开关。怎么写见 plugins/README.md。

  - 开关记在 _RULES/Plugins.md。关着的插件：后端不加载（名字和说明直接从文件里读，不运行它），网页不下载它的脚本，和没装一样。
  - plugin.py 里写 NAME、DESC，以及 get(path, qs) / post(path, body) 处理 /api/p/<名字>/... 的请求。
  - 安装：把插件文件夹拷进 tools/plugins/，或在插件弹窗里上传 zip。移除：移到 _export/已移除插件/，表里记“移除”，升级时不会再装回来。
    插件自己的资料（比如练习进度）在知识库里，移除插件不会删。
"""
import ast
import base64
import importlib.util
import io
import re
import shutil
import time
import zipfile
from pathlib import Path

from twin import ROOT

DIR = Path(__file__).resolve().parent / "plugins"
CONF = ROOT / "_RULES" / "Plugins.md"
CONF_MD = """---
type: rules
updated: {today}
privacy: internal
---
# 插件开关

> 在网页侧栏左下角抽屉里的“插件”里开关，也可以直接改这张表。

| 插件 | 开启 |
|---|---|
"""
_MODS = {}


def _ids():
    return sorted(d.name for d in DIR.iterdir() if (d / "plugin.py").exists() and re.match(r"^[a-z0-9_]+$", d.name)) if DIR.exists() else []


def _rows(pat):
    if not CONF.exists():
        return set()
    return {m.group(1) for m in re.finditer(rf"^\|\s*([a-z0-9_]+)\s*\|\s*(?:{pat})\s*\|", CONF.read_text(encoding="utf-8"), re.M)}


def _enabled():
    return _rows("是|开|on|1")


def removed():
    """移除过的插件：升级时不再装回来。"""
    return _rows("移除")


def _meta(pid):
    """不运行 plugin.py，只读出 NAME、DESC。"""
    out = {}
    try:
        for n in ast.parse((DIR / pid / "plugin.py").read_text(encoding="utf-8")).body:
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                for tg in n.targets:
                    if isinstance(tg, ast.Name) and tg.id in ("NAME", "DESC"):
                        out[tg.id] = n.value.value
    except (OSError, SyntaxError, ValueError):
        pass
    return out


def module(pid):
    if pid not in _MODS:
        f = DIR / pid / "plugin.py"
        spec = importlib.util.spec_from_file_location(f"twin_plugin_{pid}", f)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _MODS[pid] = m
    return _MODS[pid]


def listing():
    on = _enabled()
    return [{"id": p, "name": _meta(p).get("NAME", p), "desc": _meta(p).get("DESC", ""), "on": p in on} for p in _ids()]


def _set_row(pid, val):
    import datetime as dt
    text = CONF.read_text(encoding="utf-8") if CONF.exists() else CONF_MD.format(today=dt.date.today().isoformat())
    row = f"| {pid} | {val} |"
    text, n = re.subn(rf"^\|\s*{pid}\s*\|.*\|\s*$", row, text, flags=re.M)
    if not n:
        text = text.rstrip("\n") + "\n" + row + "\n"
    CONF.write_text(text, encoding="utf-8")


def set_enabled(pid, on):
    if pid not in _ids():
        raise RuntimeError("没有这个插件。")
    _set_row(pid, "是" if on else "否")
    return listing()


def remove(pid):
    """移到 _export/已移除插件/，随时能拷回来。"""
    if pid not in _ids():
        raise RuntimeError("没有这个插件。")
    dest = ROOT / "_export" / "已移除插件" / f"{pid}-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(DIR / pid), str(dest))
    _MODS.pop(pid, None)
    _set_row(pid, "移除")
    return {"plugins": listing(), "moved": dest.relative_to(ROOT).as_posix()}


def install(name, data):
    """上传的 zip：里面一个插件文件夹（或者直接是 plugin.py 那一层）。装好默认关着，自己打开。"""
    raw = base64.b64decode(str(data).split(",", 1)[-1])
    if len(raw) > 30 * 1024 * 1024:
        raise RuntimeError("插件包太大了（超过 30 MB）。")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise RuntimeError("这不是 zip 文件。")
    names = [n for n in z.namelist() if not n.endswith("/")]
    if any(".." in n.split("/") or n.startswith("/") or ":" in n for n in names):
        raise RuntimeError("插件包里有不安全的路径，没有安装。")
    tops = {n.split("/")[0] for n in names}
    if len(tops) == 1 and f"{next(iter(tops))}/plugin.py" in names:
        pid, strip = next(iter(tops)), len(next(iter(tops))) + 1
    elif "plugin.py" in names:
        pid, strip = re.sub(r"[^a-z0-9_]", "_", Path(str(name)).stem.lower()), 0
    else:
        raise RuntimeError("插件包里没有 plugin.py，不是 TWIN 插件。")
    if not re.match(r"^[a-z0-9_]+$", pid):
        raise RuntimeError("插件文件夹名只能用小写字母、数字和下划线。")
    if (DIR / pid).exists():  # 同名的先移走，相当于升级插件
        remove(pid)
    for n in names:
        out = DIR / pid / n[strip:]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(z.read(n))
    _set_row(pid, "否")
    return {"plugins": listing(), "id": pid}


def script(pid):
    """开着的插件的网页脚本；关着或没有就是 None。"""
    f = DIR / pid / "plugin.js"
    return f.read_bytes() if pid in _enabled() and pid in _ids() and f.exists() else None


def handle(method, path, data):
    """/api/p/<名字>/<子路径> 交给插件；插件没开就报错。"""
    m = re.match(r"^/api/p/([a-z0-9_]+)/(.*)$", path)
    if not m or m.group(1) not in _enabled() or m.group(1) not in _ids():
        raise RuntimeError("这个插件没有开启。")
    mod = module(m.group(1))
    fn = getattr(mod, method, None)
    if not fn:
        raise RuntimeError("插件不支持这个请求。")
    return fn(m.group(2), data)
