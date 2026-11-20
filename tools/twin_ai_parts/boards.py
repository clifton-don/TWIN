# twin_ai 的一部分：零散待办、项目任务表、项目链接、子任务。
# 由 twin_ai.py 末尾 import；外面照旧用 twin_ai.xxx。要先 import twin_ai（twin_ai_parts/__init__.py 会保证）。

import datetime as dt
import json
import re
from pathlib import Path
from twin import find_sensitive, privacy_of, PRIVATE_BLOCK, project_boards, ROOT, SKIP_SUBDIRS, walk_md
from twin_ai import _cell, _insert_row, _parse_due, _table_rows, _touch, _write, BRIEFS, DASHBOARD, deadlines, DECISIONS, goals, today, todos
from twin_ai_parts.jobs import open_tasks

# ---------- 零散待办：不属于任何项目的小事，放在一个普通的项目文件里，打勾、截止、完成记录、子任务都和项目任务一样 ----------
LOOSE_NAME, LOOSE_REL = "零散待办", "03_Projects/零散待办/board.md"
LOOSE = ROOT / LOOSE_REL
LOOSE_MD = """---
type: project
name: 零散待办
status: active
board: P2
loose: true
updated: {today}
privacy: internal
---
# 零散待办

不属于任何项目的小事。在 TWIN 的“项目 → 零散待办”里管理；哪件长大了，点任务右边的“⋯ → 移到项目”。

| 优先级 | 任务 | 截止 | 状态 | 备注 |
|---|---|---|---|---|
{rows}"""


DASHBOARD_MD = """---
type: crown
updated: {today}
privacy: public
---
# 决策端 · 总览（树顶）

> 程序会自动维护“板块”“待决策”“近期事件”这几张表，其余部分自己写。

## 1. 当前焦点（本月最重要的 1–3 件事）

## 2. 计划
| 周期 | 目标 | 对应长期方向 | 状态 |
|---|---|---|---|

## 3. 板块（大任务，细分任务在各自文件里，“今天”页点开看）
| 优先级 | 板块 | 最终截止 | 文件 |
|---|---|---|---|

## 4. 待决策
| 优先级 | 决策 | 截止 | 文件 |
|---|---|---|---|

## 5. 近期事件（只记会影响决策的）
| 日期 | 事件 | 影响 | 关联 |
|---|---|---|---|

## 6. 建议池
已搬到 [[Suggestions]]，在 TWIN 的“设置 → 建议池”里管理。
"""


def ensure_loose():
    """第一次用时建总览（空白版没有）和“零散待办”项目，把决策端“事项”表里的待办搬过来，那张表换成一行说明。"""
    if not DASHBOARD.exists():
        _write(DASHBOARD, DASHBOARD_MD.format(today=today()))
    if LOOSE.exists():
        return
    try:
        text = DASHBOARD.read_text(encoding="utf-8")
    except OSError:
        text = ""
    rows = []
    for c in _table_rows(text, "事项"):
        if len(c) >= 5 and c[1]:
            m = re.search(r"☑\s*(\d{4}-\d{2}-\d{2})?", c[4])
            st = f"{DONE} {m.group(1) or ''}".strip() if m else TODO
            rows.append(f"| {c[0]} | {c[1]} | {c[2]} | {st} | {c[3]} |\n")
    _write(LOOSE, LOOSE_MD.format(today=today(), rows="".join(rows)))
    lines = text.splitlines()
    i = next((i for i, l in enumerate(lines) if l.startswith("|") and "事项" in l and "状态" in l), None)
    if i is not None:
        j = i + 2
        while j < len(lines) and lines[j].startswith("|"):
            j += 1
        lines[i:j] = ["已搬到 [[零散待办/board]]，在 TWIN 的“项目 → 零散待办”里管理。"]
        _write(DASHBOARD, _touch("\n".join(lines) + "\n"))


def move_task(rel, index, to):
    """把一件任务挪到另一个项目（含零散待办）：优先级、截止、备注、子任务、完成记录一起带走。"""
    src = board(rel)
    t = next((x for x in src["tasks"] if x["i"] == index), None)
    if not t:
        raise RuntimeError("任务表已经变了，请刷新。")
    if (ROOT / to).resolve() == (ROOT / rel).resolve():
        raise RuntimeError("已经在这个项目里了。")
    dst = board(to)
    add_task(to, t["task"], t["priority"], t["due"], t["note"])
    j = max(x["i"] for x in board(to)["tasks"])  # 刚加的在表的最后
    if t["subs"]:
        set_subtasks(to, j, t["subs"])
    if t["status"] != TODO:
        set_task(to, j, t["status"])
    if t["review"]:
        set_task_review(to, j, t["review"])
    delete_task(rel, index)
    return f"“{t['task']}”移到了 {dst['name']}"


# 板块文件：frontmatter 里写 board: P0/P1/P2/P3，可选 due（最终截止）、why（为什么是这个优先级）、goal（一句话目标）。
# 任务表：表头含“任务”或“工作内容”，以及“状态”或“进度”；可选“优先级”“截止/完成日期”“说明/原因/备注”列。
BOARD_DIRS = ("03_Projects", "04_Milestones", "02_Life", "01_Skills")
DONE, TODO, DOING = "✓ 已完成", "未开始", "进行中"  # 进行中 = 动手了还没做完：勾了一部分子任务自动标上，没拆步骤的手动点
PRI_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
COLS = {"task": ("任务", "工作内容", "事项"), "status": ("状态", "进度"), "pri": ("优先级",),
        "due": ("截止", "完成日期", "日期"), "note": ("说明", "原因", "备注"), "subs": ("子任务",), "review": ("完成记录",)}


def _step_due(s):
    """“10/25-10/27”取后一个日期作截止。"""
    parts = re.findall(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.月]\d{1,2}", s or "")
    return _parse_due(parts[-1]) if parts else None


def _task_table(text):
    """返回 (列名映射, 表头行号, [(行号, 单元格)])；没有任务表返回 None。"""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|") or i + 1 >= len(lines) or not re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            continue
        head = [c.strip() for c in line.strip().strip("|").split("|")]
        col = {}
        for key, names in COLS.items():
            for n, h in enumerate(head):
                if any(x in h for x in names) and n not in col.values():
                    col[key] = n
                    break
        if "task" in col and "status" in col:
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append((j, [c.strip() for c in lines[j].strip().strip("|").split("|")]))
                j += 1
            return col, i, rows, len(head)
    return None


def _status(v):
    return DONE if ("完成" in v or "☑" in v or "✓" in v) else DOING if "进行" in v else TODO


def _board_files():
    ensure_loose()
    seen = set()
    for d in BOARD_DIRS:
        base = ROOT / d
        for f in walk_md(base, SKIP_SUBDIRS | {"References"}) if base.exists() else []:
            if f.name != "_SUMMARY.md":
                seen.add(f)
                yield f
    yield from (f for f in project_boards() if f not in seen)


# 所有项目的任务表统一成这几列、这个顺序；子任务、完成记录用到时才有。旧表（比如“完成日期 | 工作内容 | 进度 | 备注”）读到时自动改过来
STD_COLS = (("pri", "优先级"), ("task", "任务"), ("subs", "子任务"), ("due", "截止"), ("status", "状态"), ("note", "备注"), ("review", "完成记录"))


def _normalize_table(f):
    text = f.read_text(encoding="utf-8")
    t = _task_table(text)
    if not t:
        return text
    col, head, rows, width = t
    keys = [k for k, _ in STD_COLS if k in col or k not in ("subs", "review")]
    extra = [n for n in range(width) if n not in col.values()]  # 认不出的列放到最后，不丢
    lines = text.splitlines()
    hdr = [c.strip() for c in lines[head].strip().strip("|").split("|")]
    names = [n for k, n in STD_COLS if k in keys] + [hdr[n] for n in extra]
    if hdr == names:
        return text
    pick = lambda c: [c[col[k]] if k in col and col[k] < len(c) else "" for k in keys] + [c[n] if n < len(c) else "" for n in extra]
    lines[head], lines[head + 1] = _write_row(names, len(names)), "|" + "---|" * len(names)
    for ln, c in rows:
        lines[ln] = _write_row(pick(c), len(names))
    text = "\n".join(lines) + "\n"
    f.write_text(text, encoding="utf-8")
    return text


def board(rel):
    f = _board_path(rel)
    text = _normalize_table(f)
    fm, t = frontmatter(text), _task_table(text)
    today_ = dt.date.today()
    tasks, pushed, rel_ = [], _push_log(), f.relative_to(ROOT).as_posix()
    if t:
        col, _, rows, _ = t
        g = lambda c, k: c[col[k]] if k in col and col[k] < len(c) else ""
        for n, (_, c) in enumerate(rows):
            if not g(c, "task"):
                continue
            d, subs = _step_due(g(c, "due")), parse_subs(g(c, "subs"))
            st, k = _status(g(c, "status")), sum(x["done"] for x in subs)
            st = DOING if st == TODO and k else st  # 以前勾了一部分子任务的，也算进行中
            tasks.append({"i": n, "task": g(c, "task"), "subs": subs, "sub_done": k, "status": st, "priority": g(c, "pri"),
                          "due": g(c, "due"), "days": (d - today_).days if d else None, "note": g(c, "note"), "review": g(c, "review"),
                          "pushes": pushed.get(f"{rel_}|{g(c, 'task')}", []),
                          "done_on": (re.search(r"\d{4}-\d{2}-\d{2}", g(c, "status")) or [""])[0]})
    # 排序：没做完（按优先级、截止）→ 已完成；同一档保持表里原来的顺序
    order = {DOING: 0, TODO: 1, DONE: 2}
    tasks.sort(key=lambda x: (order[x["status"]], PRI_ORDER.get(x["priority"], 2),
                              x["days"] if x["days"] is not None else 9999, x["i"]))
    fd = _parse_due(fm.get("due", ""))
    open_ = [x for x in tasks if x["status"] != DONE]
    dated = [x for x in open_ if x["days"] is not None]
    soon = min(dated, key=lambda x: x["days"]) if dated else None  # 最近要到期的那一步
    return {"next_due": soon["due"] if soon else fm.get("due", ""),
            "next_days": soon["days"] if soon else ((fd - today_).days if fd else None),
            "open": open_,
            "path": f.relative_to(ROOT).as_posix(), "name": fm.get("name") or fm.get("title") or f.stem,
            "priority": fm.get("board", ""), "goal": fm.get("goal", ""), "why": fm.get("why", ""), "loose": fm.get("loose") == "true",
            "status": (fm.get("status") or "active").lower(),
            "due": fm.get("due", ""), "days": (fd - today_).days if fd else None,
            "done": len(tasks) - len(open_), "total": len(tasks), "tasks": tasks, "next": open_[:2],
            "overdue": sum(1 for x in open_ if x["days"] is not None and x["days"] < 0),
            "has_table": bool(t), "links": board_links(text),
            "ended": max((x["done_on"] for x in tasks), default="") or fm.get("date_end", "") or fm.get("updated", "")}  # 结项日期：最后打勾那天


# ---------- 建议池：对 TWIN 这个工具本身的改进建议，存在 _RULES/Suggestions.md，一行一个“- 建议 （日期）”，在“设置 → 建议池”里管理 ----------
# 不随对话上云；以前记在决策端“想法池”一节（中间有一版在 00_Crown/Suggestions.md），第一次用时搬过来
SUGG = ROOT / "_RULES" / "Suggestions.md"
SUGG_OLD = ROOT / "00_Crown" / "Suggestions.md"
SUGG_NOTE = "已搬到 [[Suggestions]]，在 TWIN 的“设置 → 建议池”里管理。"
SUGG_MD = """---
type: rule
updated: {today}
privacy: internal
---
# 建议池

> 对 TWIN 这个工具本身的修改和优化建议：缺什么功能、哪里不顺手、哪里容易出错。用的时候想到就记一条，AI 帮你干活时发现做不了的也会记。
> 在“设置 → 建议池”里看；攒几条可以让 AI 汇总成一份清单，发给做 TWIN 的人，或者自己照着改。

"""
IDEA_RX = re.compile(r"^- (.+?)(?:\s*（(\d{4}-\d{2}-\d{2})）)?\s*$")


def _sugg_ensure():
    if SUGG.exists():
        return
    items = []
    if SUGG_OLD.exists():
        items = [l for l in SUGG_OLD.read_text(encoding="utf-8").splitlines() if l.startswith("- ") and l.strip() != "-"]
        SUGG_OLD.unlink()
    if DASHBOARD.exists():
        lines = DASHBOARD.read_text(encoding="utf-8").splitlines()
        start = next((i for i, l in enumerate(lines) if l.startswith("## ") and ("想法" in l or "建议池" in l)), None)
        if start is not None:
            end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            items += [l for l in lines[start + 1:end] if l.startswith("- ") and l.strip() != "-"]
            lines[start:end] = [re.sub(r"想法池.*", "建议池", lines[start]), SUGG_NOTE, ""]
            _write(DASHBOARD, _touch("\n".join(lines) + "\n"))
    _write(SUGG, SUGG_MD.format(today=today()) + "".join(x + "\n" for x in items))


def _idea_lines():
    _sugg_ensure()
    lines = SUGG.read_text(encoding="utf-8").splitlines()
    return lines, [i for i, l in enumerate(lines) if l.startswith("- ") and l.strip() != "-"]


def ideas():
    lines, idx = _idea_lines()
    out = []
    for k, i in enumerate(idx):
        m = IDEA_RX.match(lines[i].rstrip())
        out.append({"i": k, "text": m.group(1) if m else lines[i][2:].strip(), "date": (m and m.group(2)) or ""})
    return out


def idea_add(text):
    text = _cell(text)
    if not text:
        raise RuntimeError("写点内容再存。")
    lines, idx = _idea_lines()
    lines.insert(idx[-1] + 1 if idx else len(lines), f"- {text} （{today()}）")
    _write(SUGG, _touch("\n".join(lines) + "\n"))
    return f"建议池：{text}"


def idea_remove(k, text):
    """删掉一条建议。带上原文核对，防止文件刚被别处改过、删错行。"""
    lines, idx = _idea_lines()
    xs = ideas()
    if not 0 <= k < len(idx) or xs[k]["text"] != text:
        raise RuntimeError("建议池刚被改过，刷新再试。")
    del lines[idx[k]]
    _write(SUGG, _touch("\n".join(lines) + "\n"))
    return text


INACTIVE = {"paused": "暂停", "done": "已完成", "dropped": "放弃", "archived": "归档"}
STATUS_WORDS = {"active": "进行中", **INACTIVE}


def boards(include_inactive=False):
    """所有项目板块。默认只要进行中的；暂停、完成、放弃、归档的不进“接下来”、体检和发给 AI 的进度。"""
    out = []
    for f in _board_files():
        try:
            head = f.read_text(encoding="utf-8")[:1500]
        except OSError:
            continue
        if re.search(r"^board:\s*P[0-3]", head, re.M):
            b = board(f.relative_to(ROOT).as_posix())
            b.pop("tasks")
            if include_inactive or b["status"] not in INACTIVE:
                out.append(b)
    out.sort(key=lambda b: (not b["loose"], PRI_ORDER.get(b["priority"], 4), b["next_days"] if b["next_days"] is not None else 9999))
    return out


def _focus_key(x):
    """急的标准：过期 → 两周内到期（越近越前）→ 优先级。"""
    d = x["days"] if x["days"] is not None else 999
    return (d >= 0, d if d <= 14 else 999,
            PRI_ORDER.get(x["bpri"], 3), PRI_ORDER.get(x["priority"], 3), d)


def board_next(b):
    """一个板块的未完成任务，最急的在前。"""
    name = re.split(r"[（(]", b["name"])[0].strip()
    its = [{"kind": "task", "path": b["path"], "i": t["i"], "text": t["task"], "board": name,
            "priority": t["priority"] or b["priority"], "bpri": b["priority"], "due": t["due"],
            "days": t["days"],
            "subs": len(t["subs"]), "sub_done": t["sub_done"], "loose": b["loose"], "doing": t["status"] == DOING} for t in b["open"]]
    return sorted(its, key=_focus_key)


def focus(bs, limit=7):
    """“接下来”：所有板块（含零散待办）的未完成任务，挑最该先做的几件。
    先每个板块各出最急的一件，排好序；还有空位再补各板块的第二件。"""
    first, second = [], []
    for b in bs:
        its = board_next(b)
        first += its[:1]
        second += its[1:2]
    return (sorted(first, key=_focus_key) + sorted(second, key=_focus_key))[:limit]


def _board_path(rel):
    f = (ROOT / rel).resolve()
    if f.suffix != ".md" or not f.exists() or not any((ROOT / d).resolve() in f.parents for d in BOARD_DIRS):
        raise RuntimeError("找不到这个板块。")
    return f


def _write_row(cells, width):
    cells = cells + [""] * (width - len(cells))
    return "| " + " | ".join(cells) + " |"


def set_task(rel, index, status):
    if status not in (DONE, TODO, DOING):
        raise RuntimeError("状态只能是已完成、进行中或未开始。")
    f = _board_path(rel)
    text = f.read_text(encoding="utf-8")
    t, lines = _task_table(text), text.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, _, rows, width = t
    ln, cells = rows[index]
    cells = cells + [""] * (width - len(cells))
    cells[col["status"]] = f"{DONE} {today()}" if status == DONE else status  # 打勾时记下完成日期
    if status == DONE and "subs" in col and col["subs"] < len(cells):  # 整条打勾 = 子任务都做完了
        cells[col["subs"]] = fmt_subs([{**x, "done": True} for x in parse_subs(cells[col["subs"]])])
    lines[ln] = _write_row(cells, width)
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"{cells[col['task']]}：{status}"


def _iso(due):
    due = str(due or "").strip()
    if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        raise RuntimeError("日期格式不对。")
    return due


# ---------- 改期记录：截止往后推一次记一次（往前提、清空不算）。同一件推了两次以上，任务旁边标出来，AI 也会看到 ----------
PUSH_LOG = ROOT / "00_Crown" / "改期记录.json"


def _push_log():
    try:
        return json.loads(PUSH_LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_task_due(rel, index, due):
    due = _iso(due)
    f = _board_path(rel)
    text = f.read_text(encoding="utf-8")
    t, lines = _task_table(text), text.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, _, rows, width = t
    if "due" not in col:
        raise RuntimeError("这个任务表没有“截止”列，请在文件里加一列。")
    ln, cells = rows[index]
    cells = cells + [""] * (width - len(cells))
    old, n = cells[col["due"]].strip(), 0
    cells[col["due"]] = due
    lines[ln] = _write_row(cells, width)
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", old) and due > old:
        log, key = _push_log(), f"{f.relative_to(ROOT).as_posix()}|{cells[col['task']]}"
        log.setdefault(key, []).append({"from": old, "to": due, "on": today()})
        PUSH_LOG.parent.mkdir(parents=True, exist_ok=True)
        PUSH_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=0), encoding="utf-8")
        n = len(log[key])
    return f"{cells[col['task']]}：截止 {due or '已清除'}" + (f"（这件已经第 {n} 次往后推了）" if n >= 2 else "")


def _find_board(key):
    key = str(key or "").strip()
    bs = boards(True)
    hits = [b for b in bs if b["name"] == key] or [b for b in bs if key and (key in b["name"] or b["name"].split("（")[0] in key)]
    if len(hits) != 1:
        raise RuntimeError(f"名字含“{key}”的项目有 {len(hits)} 个，没法确定是哪个。")
    return hits[0]["path"], re.split(r"[（(]", hits[0]["name"])[0].strip()


def _find_task(rel, key, done=False):
    key = str(key or "").strip()
    opens = [t for t in board(rel)["tasks"] if (t["status"] == DONE) == done]
    hits = [t for t in opens if t["task"] == key] or [t for t in opens if key and key in t["task"]]
    if len(hits) != 1:
        raise RuntimeError(f"含“{key}”的{'已完成' if done else '未完成'}任务有 {len(hits)} 个，请到项目页里手动改。")
    return hits[0]


def _pri(v):
    v = str(v or "").strip().upper()
    if v not in PRI_ORDER:
        raise RuntimeError("优先级只能是 P0–P3。")
    return v


def _sync_dashboard(rel, pri=None, due=None):
    """看板“板块”表里有这个项目的一行时，把优先级 / 最终截止一起改掉，免得两边对不上。"""
    p = Path(rel)
    keys = {f"[[{p.parent.name}/{p.stem}]]", f"[[{p.stem}]]"} if p.stem == "board" else {f"[[{p.stem}]]"}
    try:
        text = DASHBOARD.read_text(encoding="utf-8")
    except OSError:
        return
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("|") and any(k in l for k in keys) and l.count("|") == 5:
            cells = l.split("|")
            if pri:
                cells[1] = f" {pri} "
            if due is not None:
                cells[3] = f" {due} "
            lines[i] = "|".join(cells)
            _write(DASHBOARD, _touch("\n".join(lines) + "\n"))
            return


def set_board_name(rel, name):
    """项目改名：改板块里的名字和大标题，总览表那一行一起改。文件夹名不动，链接不会断。"""
    name = _cell(name)
    if not name:
        raise RuntimeError("项目名不能空。")
    f = _board_path(rel)
    text = f.read_text(encoding="utf-8")
    old = frontmatter(text).get("name", "")
    text = _set_fm(text, "name", name)
    text = re.sub(r"^# .*$", lambda m: f"# {name}", text, count=1, flags=re.M)
    f.write_text(_set_fm(text, "updated", today()), encoding="utf-8")
    p = Path(rel)
    keys = {f"[[{p.parent.name}/{p.stem}]]", f"[[{p.stem}]]"} if p.stem == "board" else {f"[[{p.stem}]]"}
    try:
        lines = DASHBOARD.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for i, l in enumerate(lines):
        if l.startswith("|") and l.count("|") == 5 and any(k in l for k in keys):
            cells = l.split("|")
            cells[2] = f" {name} "
            lines[i] = "|".join(cells)
            _write(DASHBOARD, _touch("\n".join(lines) + "\n"))
            break
    return f"项目改名：{old or p.parent.name} → {name}"


def project_parents():
    """手动新建项目时可以放的目录：03_Projects 本身和下面的分类文件夹（不是项目、不在项目里面的）。"""
    import os
    base, out = ROOT / "03_Projects", ["03_Projects"]
    for d, dirs, files in os.walk(base):
        dp = Path(d)
        if dp != base and ("board.md" in files or "index.md" in files):
            dirs[:] = []
            continue
        dirs[:] = sorted(x for x in dirs if not x.startswith((".", "_")) and x != "零散待办")
        if dp != base:
            out.append(dp.relative_to(ROOT).as_posix())
        if len(dp.relative_to(base).parts) >= 2:
            dirs[:] = []
    # 按名字比，Windows 不分大小写会把 INDEX.md 当成项目；新装的 TWIN 还没有 03_Projects，建项目时会顺手建
    return [x for x in out if not (ROOT / x).is_dir() or not {"board.md", "index.md"} & set(os.listdir(ROOT / x))]


def set_board_priority(rel, pr):
    pr = _pri(pr)
    f = _board_path(rel)
    text = _set_fm(f.read_text(encoding="utf-8"), "board", pr)
    f.write_text(_set_fm(text, "updated", today()), encoding="utf-8")
    _sync_dashboard(rel, pri=pr)
    return f"项目优先级：{pr}"


def set_task_priority(rel, index, pr):
    pr = _pri(pr)
    f = _board_path(rel)
    text = f.read_text(encoding="utf-8")
    t, lines = _task_table(text), text.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, _, rows, width = t
    if "pri" not in col:
        raise RuntimeError("这个任务表没有“优先级”列，请在文件里加一列。")
    ln, cells = rows[index]
    cells = cells + [""] * (width - len(cells))
    cells[col["pri"]] = pr
    lines[ln] = _write_row(cells, width)
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"{cells[col['task']]}：{pr}"


def set_board_due(rel, due):
    due = _iso(due)
    f = _board_path(rel)
    text = _set_fm(f.read_text(encoding="utf-8"), "due", due)
    f.write_text(_set_fm(text, "updated", today()), encoding="utf-8")
    _sync_dashboard(rel, due=due)
    return f"项目截止：{due or '已清除'}"


# ---------- 项目链接：在线进度表、仓库、网盘……写在 board.md 的“## 链接”小节，一行一个 ----------
LINKS_HEAD = "## 链接"
_LINK = re.compile(r"^- \[([^\]]+)\]\((https?://[^)\s]+)\)\s*$")


def board_links(text):
    m = re.search(rf"^{LINKS_HEAD}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return [{"name": x.group(1), "url": x.group(2)} for x in map(_LINK.match, m.group(1).splitlines()) if x] if m else []


def _clean_url(url):
    url = str(url or "").strip().replace("&amp;", "&")
    if not re.match(r"^https?://[^\s<>\"']+$", url) or ")" in url:
        raise RuntimeError("链接要以 http:// 或 https:// 开头，不能有空格。")
    return url


def set_board_link(rel, name, url, old_url=None):
    """加一个链接；同一个地址已经有了就改名字。old_url 给了就是把那条换掉。"""
    url, name = _clean_url(url), _cell(name).replace("[", "(").replace("]", ")") or "链接"
    f = _board_path(rel)
    src = f.read_text(encoding="utf-8")
    line = f"- [{name}]({url})"
    m = re.search(rf"^{LINKS_HEAD}\s*$(.*?)(?=^## |\Z)", src, re.M | re.S)
    if m:
        body = m.group(1).splitlines()
        hit = next((i for i, l in enumerate(body) if (lm := _LINK.match(l)) and lm.group(2) in (url, old_url)), None)
        if hit is None:
            last = max([i for i, l in enumerate(body) if _LINK.match(l)] or [0])
            body.insert(last + 1, line)
        else:
            body[hit] = line
        new = "\n".join(body)
        if not new.endswith("\n"):
            new += "\n"
        src = src[:m.start(1)] + new + src[m.end(1):]
    else:  # 没有这一节：放在第一个“## ”小节前面（一般是“一句话简介”后面），都没有就放最后
        block = f"{LINKS_HEAD}\n{line}\n\n"
        secs = [x.start() for x in re.finditer(r"^## ", src, re.M)]
        at = secs[1] if len(secs) > 1 else (secs[0] if secs else None)
        src = src[:at] + block + src[at:] if at is not None else src.rstrip("\n") + "\n\n" + block
    f.write_text(_touch(src), encoding="utf-8")
    return f"项目链接：{name}"


def del_board_link(rel, url):
    f = _board_path(rel)
    src = f.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    keep = [l for l in lines if not ((lm := _LINK.match(l.rstrip("\n"))) and lm.group(2) == url)]
    if len(keep) == len(lines):
        raise RuntimeError("没找到这个链接，请刷新。")
    f.write_text(_touch("".join(keep)), encoding="utf-8")
    return "删掉了一个项目链接"


def rename_task(rel, index, text, note=None):
    """改任务名（备注给了就一起改）。"""
    text = _cell(text)
    if not text:
        raise RuntimeError("新的任务名是空的。")
    f = _board_path(rel)
    src = f.read_text(encoding="utf-8")
    t, lines = _task_table(src), src.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, _, rows, width = t
    ln, cells = rows[index]
    cells = cells + [""] * (width - len(cells))
    old, cells[col["task"]] = cells[col["task"]], text
    if note is not None and "note" in col:
        cells[col["note"]] = _cell(note)
    lines[ln] = _write_row(cells, width)
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"“{old}”改名为“{text}”"


def set_task_review(rel, index, text):
    """完成记录：做完一件事后记一句情况，存在任务表的“完成记录”列，没有这一列就在表最右边加上。"""
    f = _board_path(rel)
    src = f.read_text(encoding="utf-8")
    t, lines = _task_table(src), src.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, head, rows, width = t
    if "review" not in col:
        lines[head] = _write_row([c.strip() for c in lines[head].strip().strip("|").split("|")] + ["完成记录"], width + 1)
        lines[head + 1] = lines[head + 1].rstrip() + "---|"
        for ln, c in rows:
            lines[ln] = _write_row(c, width + 1)
        col, width = {**col, "review": width}, width + 1
    ln, cells = rows[index]
    cells = cells + [""] * (width - len(cells))
    cells[col["review"]] = _cell(text)
    lines[ln] = _write_row(cells, width)
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"记下了：{cells[col['task']]}" if text else "完成记录已清空"


def delete_task(rel, index):
    f = _board_path(rel)
    src = f.read_text(encoding="utf-8")
    t, lines = _task_table(src), src.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, _, rows, _w = t
    ln, cells = rows[index]
    del lines[ln]
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"删掉了任务：{cells[col['task']] if col['task'] < len(cells) else ''}"


def _board_link(rel):
    p = Path(rel)
    return f"[[{p.parent.name}/board]]" if p.stem == "board" else f"[[{p.stem}]]"


def _dash_row(rel, add, pri="", name="", due=""):
    """总览“板块”表：项目暂停、完成时拿掉这一行，重新开始时加回来。"""
    if not DASHBOARD.exists():  # 新装的 TWIN 还没有总览：要加行就先建（和 ensure_loose 一样），要删行就没什么可删
        if not add:
            return
        _write(DASHBOARD, DASHBOARD_MD.format(today=today()))
    text = DASHBOARD.read_text(encoding="utf-8")
    link, lines = _board_link(rel), text.splitlines()
    hit = [i for i, l in enumerate(lines) if l.startswith("|") and l.count("|") == 5 and link in l]
    if add and not hit:
        text = _insert_row(text, "| 板块 |", f"| {pri} | {_cell(name)} | {due} | {link} |")
    elif not add and hit:
        del lines[hit[0]]
        text = "\n".join(lines) + "\n"
    else:
        return
    _write(DASHBOARD, _touch(text))


def set_board_status(rel, status):
    status = str(status or "").strip().lower()
    status = next((k for k, v in STATUS_WORDS.items() if status in (k, v)), status)
    if status not in STATUS_WORDS:
        raise RuntimeError("项目状态只能是：进行中、暂停、已完成、放弃、归档。")
    f = _board_path(rel)
    text = f.read_text(encoding="utf-8")
    text = _set_fm(text, "status", status)
    f.write_text(_set_fm(text, "updated", today()), encoding="utf-8")
    fm = frontmatter(text)
    _dash_row(rel, status == "active", fm.get("board", "P2"), fm.get("name", ""), fm.get("due", ""))
    return f"项目状态：{STATUS_WORDS[status]}"


BOARD_MD = """---
type: project
name: {name}
status: active
repo: ""
stack: []
skills: []
people: []
date_start: {month}
board: {pri}
due: {due}
goal: {goal}
why: {why}
updated: {today}
privacy: internal
---
# {name}

## 一句话简介
{goal}

## 任务
| 优先级 | 任务 | 截止 | 状态 | 备注 |
|---|---|---|---|---|
{rows}
## 踩坑日志
- {today}：项目建立
"""
INDEX_MD = """---
type: project
name: {name}
updated: {today}
privacy: internal
---
# {name}

- 任务和进度：[board.md](board.md)

## 项目结构
| 文件 | 说明 |
|------|------|
| board.md | 任务板块 |
| 01_code/ | 代码 |
| 02_docs/ | 文档 |
| 03_materials/ | 模型、图片、资料 |
"""


def parent_ok(parent):
    """新建项目能不能放在这里。03_Projects 本身总是可以（新装的 TWIN 还没有这个文件夹，建项目时会一起建）。"""
    import twin_inbox
    return parent == "03_Projects" or (parent in twin_inbox.targets() and parent.startswith(BOARD_DIRS))


def create_board(parent, folder, name, priority="P2", due="", goal="", why="", tasks=()):
    """新建项目：parent/folder/board.md。放在 03_Projects 里时一起建 index.md 和 01_code / 02_docs / 03_materials。"""
    import twin_inbox
    parent = str(parent or "").strip().strip("/")
    if not parent_ok(parent):
        raise RuntimeError(f"“{parent or '空'}”不是可以放项目的目录。")
    folder = re.sub(r'[\\/:*?"<>|\s]+', "_", str(folder or name).strip()).strip("._")[:80]
    name = _cell(name)
    if not name or not folder:
        raise RuntimeError("项目要有名字。")
    d = ROOT / parent / folder
    if d.exists():
        raise RuntimeError(f"{parent}/{folder} 已经有了，换个名字。")
    pri, due = _pri(priority or "P2"), _iso(due)
    rows = "".join(f"| {_pri(t.get('priority') or pri)} | {_cell(t.get('text'))} | {_iso(t.get('due', ''))} | {TODO} |  |\n"
                   for t in tasks if isinstance(t, dict) and t.get("text"))
    d.mkdir(parents=True)
    f = d / "board.md"
    f.write_text(BOARD_MD.format(name=name, month=today()[:7], pri=pri, due=due, goal=_cell(goal), why=_cell(why),
                                 today=today(), rows=rows), encoding="utf-8")
    if parent.startswith("03_Projects"):
        (d / "index.md").write_text(INDEX_MD.format(name=name, today=today()), encoding="utf-8")
        for sub in twin_inbox.PROJECT_SUBDIRS:
            (d / sub).mkdir()
    rel = f.relative_to(ROOT).as_posix()
    _dash_row(rel, True, pri, name, due)
    return rel


def add_task(rel, task, priority="", due="", note=""):
    f = _board_path(rel)
    text = f.read_text(encoding="utf-8")
    t, lines = _task_table(text), text.splitlines()
    if not t:
        raise RuntimeError("这个板块还没有任务表。")
    col, _, rows, width = t
    cells = [""] * width
    cells[col["task"]], cells[col["status"]] = _cell(task), TODO
    for k, v in (("pri", priority), ("due", due), ("note", note)):
        if k in col:
            cells[col[k]] = _cell(v)
    at = rows[-1][0] + 1 if rows else t[1] + 2
    lines.insert(at, _write_row(cells, width))
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"已加到板块：{_cell(task)}"


# ---------- 子任务：一条任务下面的几个小步骤，存在任务表的“子任务”列，一格里用 <br> 分行 ----------
SUB_SEP = "<br>"


def parse_subs(cell):
    out = []
    for part in re.split(r"<br\s*/?>", cell or ""):
        part = part.strip()
        if part:
            done = part[0] in "☑✓✅"
            text, _, note = part.lstrip("☑✓✅☐ ").strip().partition(" — ")  # 做完一步后补的一句说明
            out.append({"text": text.strip(), "done": done, "note": note.strip()})
    return out


def fmt_subs(subs):
    return SUB_SEP.join(f"{'☑' if x['done'] else '☐'} {_cell(x['text']).replace('<', '‹')}" + (f" — {_cell(x['note']).replace('<', '‹')}" if x.get("note") else "")
                        for x in subs if str(x.get("text", "")).strip())


def _ensure_col(text, key, title):
    """任务表没有这一列就加在“任务”列后面，已有的行补空格子。"""
    t = _task_table(text)
    if not t or key in t[0]:
        return text
    col, hi, rows, width = t
    at, lines = col["task"] + 1, text.splitlines()
    for ln, cells in [(hi, [c.strip() for c in lines[hi].strip().strip("|").split("|")]), (hi + 1, None)] + rows:
        if cells is None:
            lines[ln] = "|" + "---|" * (width + 1)
            continue
        cells = cells + [""] * (width - len(cells))
        cells.insert(at, title if ln == hi else "")
        lines[ln] = _write_row(cells, width + 1)
    return "\n".join(lines) + "\n"


def set_subtasks(rel, index, subs):
    """整组写回子任务，并按勾选情况带动任务状态：全勾 → 完成；勾了一部分 → 进行中（动手了没做完）；一个都没勾、又是从完成改回来的 → 未开始。"""
    subs = [{"text": str(x.get("text", "")).strip(), "done": bool(x.get("done")), "note": str(x.get("note") or "").strip()}
            for x in subs if isinstance(x, dict) and str(x.get("text", "")).strip()]
    f = _board_path(rel)
    text = _ensure_col(f.read_text(encoding="utf-8"), "subs", "子任务")
    t, lines = _task_table(text), text.splitlines()
    if not t or not 0 <= index < len(t[2]):
        raise RuntimeError("任务表已经变了，请刷新。")
    col, _, rows, width = t
    ln, cells = rows[index]
    cells = cells + [""] * (width - len(cells))
    k0 = sum(x["done"] for x in parse_subs(cells[col["subs"]]))
    cells[col["subs"]] = fmt_subs(subs)
    st, n, k = _status(cells[col["status"]]), len(subs), sum(x["done"] for x in subs)
    new = st
    # 只有这次真的又勾了一步、勾满了才算完成；删掉没做的步骤、剩下的恰好都做完了，不替他把整件任务打钩
    if n and k == n and (k > k0 or st == DONE):
        new = DONE
    elif k:
        new = DOING
    elif st == DONE:
        new = TODO
    if new != st:
        cells[col["status"]] = f"{DONE} {today()}" if new == DONE else new
    lines[ln] = _write_row(cells, width)
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    msg = f"{cells[col['task']]}：子任务 {k}/{n}" if n else f"{cells[col['task']]}：子任务清空了"
    return msg + (f"，任务改成{'已完成' if new == DONE else new}" if new != st else "")


def _sub_hit(subs, key):
    key = str(key or "").strip()
    hits = [j for j, x in enumerate(subs) if x["text"] == key] or [j for j, x in enumerate(subs) if key and key in x["text"]]
    if len(hits) != 1:
        raise RuntimeError(f"含“{key}”的子任务有 {len(hits)} 个，没法确定是哪个。")
    return hits[0]


def merge_tasks(rel, keys, text, note=None):
    """把几条任务合成一条：原来的任务名变成子任务（完成情况保留），优先级取最高、截止取最早，放在第一条的位置。"""
    keys = [k for k in keys if str(k).strip()]
    if len(keys) < 2:
        raise RuntimeError("合并至少要两条任务。")
    all_ = board(rel)["tasks"]
    picked = []
    for k in keys:
        hit = [t for t in all_ if t["task"] == k] or [t for t in all_ if k in t["task"]]
        if len(hit) != 1:
            raise RuntimeError(f"含“{k}”的任务有 {len(hit)} 个，没法确定是哪个。")
        if hit[0] not in picked:
            picked.append(hit[0])
    picked.sort(key=lambda t: t["i"])
    subs, head = [], _cell(text)
    for t in picked:
        subs += t["subs"] or [{"text": t["task"], "done": t["status"] == DONE}]
    for x in subs:  # “小车第二版：加防反接” 合进“小车第二版”后只留“加防反接”
        pre, sep, rest = x["text"].partition("：")
        if sep and rest and (pre in head or head in pre):
            x["text"] = rest.strip()
    pr = min((t["priority"] for t in picked if t["priority"] in PRI_ORDER), key=lambda p: PRI_ORDER[p], default="")
    dues = sorted(t["due"] for t in picked if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t["due"] or ""))
    notes = "；".join(t["note"] for t in picked if t["note"])
    first = picked[0]["i"]
    for t in sorted(picked[1:], key=lambda t: -t["i"]):
        delete_task(rel, t["i"])
    rename_task(rel, first, text, note if note is not None else notes)
    f = _board_path(rel)
    src = f.read_text(encoding="utf-8")
    t = _task_table(src)
    if t is None:
        raise RuntimeError("项目里找不到任务表。")
    col, _, rows, width = t
    lines, (ln, cells) = src.splitlines(), rows[first]
    cells = cells + [""] * (width - len(cells))
    if "pri" in col and pr:
        cells[col["pri"]] = pr
    if "due" in col:
        cells[col["due"]] = dues[0] if dues else cells[col["due"]]
    lines[ln] = _write_row(cells, width)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    set_subtasks(rel, first, subs)
    return f"把 {len(picked)} 条合成“{_cell(text)}”，原来的变成 {len(subs)} 个子任务"


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            fm[k.strip()] = v.split(" #")[0].strip().strip('"')
    return fm


def decisions():
    out = []
    for p in sorted(DECISIONS.glob("*.md")):
        fm = frontmatter(p.read_text(encoding="utf-8"))
        if fm.get("type") != "decision":
            continue
        out.append({"path": p.relative_to(ROOT).as_posix(), "title": fm.get("title", p.stem), "status": fm.get("status", "open"),
                    "review_date": fm.get("review_date", ""), "local_verdict": fm.get("local_verdict", ""),
                    "ai_verdict": fm.get("ai_verdict", ""), "chosen": fm.get("chosen", ""),
                    "outcome": fm.get("outcome", ""), "who_right": fm.get("who_right", "")})
    return out


def due_reviews():
    soon = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    return [d for d in decisions() if d["status"] != "reviewed" and d["review_date"] and d["review_date"] <= soon]


def brief_path(day=None):
    return BRIEFS / f"{day or today()}.md"


def home():
    bp = brief_path()
    brief = bp.read_text(encoding="utf-8") if bp.exists() else ""
    decs = todos()[1]
    bs = boards()
    rest = [b for b in boards(True) if b["status"] in INACTIVE]
    import twin_cards
    return {"expiring": twin_cards.expiring(), "focus": focus(bs), "boards": bs, "next": {b["path"]: board_next(b) for b in bs}, "inactive": rest, "decisions": decs, "goals": goals(), "deadlines": [d for d in deadlines() if d["days"] <= 14], "reviews": due_reviews(),
            "suggest": suggest_today(), "news": news_today(), "open_tasks": open_tasks(), "brief": re.sub(r"^---\n.*?\n---\n", "", brief, flags=re.S),
            "upgrade": upgrade_status()}


# ---------- 项目画像：聊天里确认过的项目真实情况，记在项目 index.md 的“## 项目画像”里，按几类分小节，越聊越清楚 ----------
PROFILE_SECTIONS = ("场景", "需求", "现状", "硬件与参数", "决定")
PROFILE_HEAD = "## 项目画像"


def _profile_file(rel):
    return _board_path(rel).parent / "index.md"


def _profile_block(text):
    """返回“## 项目画像”这一段的 (开始行, 结束行)，没有返回 None。"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == PROFILE_HEAD:
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
            return i, j
    return None


def profile_text(rel):
    """发给 AI 的项目画像：私密的项目不发，私密段落和像敏感值的行去掉。"""
    f = _profile_file(rel)
    if not f.exists():
        return ""
    text = f.read_text(encoding="utf-8")
    if privacy_of(text) in ("private", "secret"):
        return ""
    blk = _profile_block(PRIVATE_BLOCK.sub("", text))
    if not blk:
        return ""
    lines = PRIVATE_BLOCK.sub("", text).splitlines()[blk[0] + 1:blk[1]]
    return "\n".join(x for x in lines if x.strip() and not x.startswith(">") and not find_sensitive(x)).strip()


def add_profile(rel, section, items):
    section = section if section in PROFILE_SECTIONS else "现状"
    f = _profile_file(rel)
    text = f.read_text(encoding="utf-8") if f.exists() else f"---\ntype: project\nprivacy: internal\nupdated: {today()}\n---\n# {f.parent.name}\n"
    if not _profile_block(text):
        text = text.rstrip("\n") + f"\n\n{PROFILE_HEAD}\n\n> 和 AI 聊这个项目时确认过的真实情况，越聊越清楚。可以直接改。\n"
    lines = text.splitlines()
    blk = _profile_block(text)
    if blk is None:  # 上面刚补过标题，不会走到这里
        raise RuntimeError("项目说明里写不进项目画像。")
    i, j = blk
    have = "\n".join(lines[i:j])
    new = [x.replace("\n", " ").strip() for x in items if x.strip() and x.strip() not in have]
    if not new:
        return "项目画像里已经有了"
    sh = next((k for k in range(i + 1, j) if lines[k].strip() == f"### {section}"), None)
    add = [f"- {x}（{today()}）" for x in new]
    if sh is None:
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1
        lines[j:j] = ["", f"### {section}"] + add
    else:
        end = next((k for k in range(sh + 1, j) if lines[k].startswith("### ")), j)
        while end > sh + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = add
    f.write_text(_set_fm("\n".join(lines) + "\n", "updated", today()), encoding="utf-8")
    return f"项目画像 · {section}：" + "；".join(new)


# 排在后面加载的部分：只在函数里用到，放在末尾 import，避免循环依赖
from twin_ai_parts.reports import _set_fm, suggest_today, upgrade_status
from twin_ai_parts.news import news_today
