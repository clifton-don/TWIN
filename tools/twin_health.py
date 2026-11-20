#!/usr/bin/env python3
"""知识库体检（只用 Python 标准库，全在本地算，不经过 AI）。

查这些：过期任务、很久没动的项目、总览表和项目页对不上、断掉的链接、还没写的分支总结、
缺隐私级别的文件、公开文件里的疑似敏感值、暂存箱里没归档的东西、到期没回看的决定。
"""
import datetime as dt
import json
import re
import time
from pathlib import Path

from twin import PROGRAM_DOCS, ROOT, SKIP_FILES, SKIP_SUBDIRS, find_sensitive, mask, privacy_of

import twin_ai

STALE_DAYS = 14
IGNORE_FILE = ROOT / "tools" / "health_ignore.json"  # 点了“忽略”的问题，存在本机
_CACHE = {"t": 0.0, "data": None}
WIKI = re.compile(r"\[\[([^\]]+)\]\]")
MDLINK = re.compile(r"\[[^\]]*\]\(([^)\s]+\.md)(?:#[^)]*)?\)")
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.S)
PLACEHOLDER = {"链接", "文件名", "名称", "示例叶子", "x"}
TEMPLATE_HINT = ("（3–5 句话", "[[示例叶子]]")


def _resolver(items):
    paths = [it["path"] for it in items]
    by_name = {}
    for p in paths:
        by_name.setdefault(p.split("/")[-1], p)
    pset = set(paths)

    def resolve(name):
        name = name.split("|")[0].split("#")[0].strip().rstrip("\\")
        want = name if name.endswith(".md") else name + ".md"
        if want in pset:
            return want
        for p in paths:
            if p.endswith("/" + want):
                return p
        return by_name.get(want.split("/")[-1])
    return resolve


def _issue(level, kind, title, detail="", path="", board=False):
    return {"level": level, "kind": kind, "title": title, "detail": detail, "path": path, "board": board,
            "key": f"{kind}|{path}|{title}"}


def ignored():
    try:
        return json.loads(IGNORE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_ignore(key, on=True):
    data = ignored()
    if on:
        data[key] = dt.date.today().isoformat()
    else:
        data.pop(key, None)
    IGNORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    clear()


def check(items, inbox_count=0, fresh=False):
    """items：资料库目录（twin_web.tree()）。结果缓存 60 秒。"""
    if not fresh and _CACHE["data"] and time.time() - _CACHE["t"] < 60:
        return _CACHE["data"]
    out, today = [], dt.date.today()
    bs = twin_ai.boards()

    # 1. 过期任务 + 2. 很久没动的项目 + 3. P0 项目没有任何截止
    for b in bs:
        name = re.split(r"[（(]", b["name"])[0].strip()
        for t in b["open"]:
            if t["days"] is not None and t["days"] < 0:
                out.append(_issue("red", "过期任务", f"{name}：{t['task']}", f"过期 {-t['days']} 天，做完就打钩，做不完就改截止", b["path"], True))
        try:
            fm = twin_ai.frontmatter((ROOT / b["path"]).read_text(encoding="utf-8"))
            upd = dt.date.fromisoformat(fm.get("updated", "")[:10])
        except (OSError, ValueError):
            upd = dt.date.fromtimestamp((ROOT / b["path"]).stat().st_mtime)
        idle = (today - upd).days
        if b["open"] and idle >= STALE_DAYS and not b["loose"]:
            out.append(_issue("amber", "很久没动", f"{name}", f"{idle} 天没更新，还有 {len(b['open'])} 件没做。还在做吗？", b["path"], True))
        if b["priority"] == "P0" and b["open"] and b["next_days"] is None:
            out.append(_issue("grey", "没有截止", f"{name}", "P0 项目却没有任何截止日期，排不进“接下来”", b["path"], True))

    # 4. 总览表和项目页对不上
    try:
        dash = twin_ai.DASHBOARD.read_text(encoding="utf-8")
    except OSError:
        dash = ""
    resolve = _resolver(items)
    bmap = {b["path"]: b for b in bs}
    for line in dash.splitlines():
        if not line.startswith("|") or line.count("|") != 5:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = WIKI.search(cells[3]) if len(cells) > 3 else None
        if not m or not re.fullmatch(r"P[0-3]", cells[0]):
            continue
        b = bmap.get(resolve(m.group(1)) or "")
        if not b:
            continue
        name = re.split(r"[（(]", b["name"])[0].strip()
        if cells[0] != b["priority"]:
            out.append(_issue("amber", "两边对不上", f"{name} 的优先级", f"总览表写 {cells[0]}，项目页写 {b['priority']}", b["path"], True))
        if cells[2] and b["due"] and cells[2] != b["due"]:
            out.append(_issue("amber", "两边对不上", f"{name} 的截止", f"总览表写 {cells[2]}，项目页写 {b['due']}", b["path"], True))

    # 5. 断链、没写的总结、缺隐私级别、疑似敏感值
    unwritten = []
    for it in items:
        rel = it["path"]
        if rel.startswith(("_TEMPLATES/", "_INBOX/")) or rel in SKIP_FILES or rel in PROGRAM_DOCS:
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if rel.endswith("_SUMMARY.md") and any(h in text for h in TEMPLATE_HINT):
            unwritten.append(rel)
            continue
        body = CODE.sub("", text)
        bad = sorted({n.split("|")[0].strip().rstrip("\\") for n in WIKI.findall(body)
                      if not resolve(n) and n.split("|")[0].strip() not in PLACEHOLDER})
        base = Path(rel).parent
        for href in MDLINK.findall(body):
            if href.startswith(("http:", "https:")):
                continue
            target = (ROOT / base / href.replace("%20", " ")).resolve()
            if not target.exists():
                bad.append(href)
        if bad:
            out.append(_issue("amber", "断掉的链接", it["title"], "指向不存在的文件：" + "、".join(bad[:5]) + ("…" if len(bad) > 5 else ""), rel))
        lv = privacy_of(text)
        if lv is None and not SKIP_SUBDIRS & set(rel.split("/")):
            out.append(_issue("amber", "缺隐私级别", it["title"], "没有 privacy 字段，会被当成机密，AI 完全看不到", rel))
        if lv in (None, "public", "internal"):
            hits = find_sensitive(text)
            if hits:
                out.append(_issue("red", "疑似敏感值", it["title"], "、".join(f"{n} {mask(v)}" for n, v in hits[:3])
                                  + "。移到 VAULT，原处写 {{VAULT:名称}}", rel))

    if unwritten:
        names = [r.rsplit("/", 2)[-2] for r in unwritten]
        out.append(_issue("grey", "总结没写", f"{len(unwritten)} 个分支总结还是模板",
                          "AI 读这些分支时什么都看不到。先写有内容的分支就行：" + "、".join(names[:8]) + ("…" if len(names) > 8 else ""), unwritten[0]))

    # 6. 暂存箱、到期的回看
    if inbox_count:
        out.append(_issue("grey", "暂存箱", f"暂存箱里有 {inbox_count} 件没归档", "", "#inbox"))
    for d in twin_ai.due_reviews():
        if d["review_date"] <= today.isoformat():
            out.append(_issue("amber", "该回看了", d["title"], f"计划 {d['review_date']} 回看", d["path"]))

    order = {"red": 0, "amber": 1, "grey": 2}
    out.sort(key=lambda x: order[x["level"]])
    ign = ignored()
    hidden = [x for x in out if x["key"] in ign]
    out = [x for x in out if x["key"] not in ign]
    data = {"issues": out, "ignored": hidden, "red": sum(x["level"] == "red" for x in out), "amber": sum(x["level"] == "amber" for x in out),
            "grey": sum(x["level"] == "grey" for x in out), "time": dt.datetime.now().strftime("%H:%M")}
    _CACHE.update(t=time.time(), data=data)
    return data


def clear():
    _CACHE["t"] = 0
