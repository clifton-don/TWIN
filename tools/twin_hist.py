#!/usr/bin/env python3
"""改动历史（只用 Python 标准库）。

网页和 AI 每次写知识库里的文件之前，先把文件原来的样子存一份；写完再存一份新样子。
这样可以看“改了什么”，也可以一键撤回。
  - 存在知识库根目录的 .history/ 里（和知识库在同一块加密盘上），不上传，不进 AI 资料。
  - 同样的内容只存一份（按内容哈希），所以占地方很少。
  - 超过 KEEP_DAYS 天的记录在启动时清理掉。
"""
import datetime as dt
import difflib
import hashlib
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from twin import ROOT

HIST = ROOT / ".history"
BLOBS = HIST / "blobs"
LOG = HIST / "log.jsonl"
STATE = HIST / "state.json"  # 每个文件上次见到的 [修改时间, 大小, 内容哈希]，用来发现在别处的改动
KEEP_DAYS = 180
# 这些地方的文件不记：程序自己、对话记录、历史本身
IGNORE = {".history", ".chats", "tools", ".git", ".obsidian", "_VAULT"}
_local = threading.local()
_lock = threading.Lock()


def _key(data):
    if data is None:
        return None
    k = hashlib.sha256(data).hexdigest()
    f = BLOBS / k[:2] / k
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    return k


def _blob(k):
    return None if k is None else (BLOBS / k[:2] / k).read_bytes()


def _rel(path):
    try:
        p = Path(path).resolve()
        rel = p.relative_to(ROOT.resolve())
    except (ValueError, OSError):
        return None
    if not rel.parts or rel.parts[0] in IGNORE:
        return None
    return rel.as_posix()


def capture(path):
    """在写文件之前调用：记下这个文件改之前的样子。同一次操作里只记第一次。"""
    g = getattr(_local, "g", None)
    if g is None:
        return
    rel = _rel(path)
    if rel is None or rel in g["files"]:
        return
    p = ROOT / rel
    g["files"][rel] = _key(p.read_bytes()) if p.is_file() else None


def set_label(text):
    g = getattr(_local, "g", None)
    if g is not None and text:
        g["label"] = str(text)[:120]


@contextmanager
def group(label, source="手动", undo_of=None):
    """一次操作（点一下、确认一张卡片）里写的所有文件算一条记录。"""
    g = {"files": {}, "label": label, "source": source, "undo_of": undo_of, "id": None}
    _local.g = g
    try:
        yield g
    finally:
        _local.g = None
        _commit(g)


def _commit(g):
    changes = []
    for rel, before in g["files"].items():
        p = ROOT / rel
        after = _key(p.read_bytes()) if p.is_file() else None
        if after != before:
            changes.append({"path": rel, "before": before, "after": after})
    if not changes:
        return
    g["id"] = f"{time.time_ns():x}"
    entry = {"id": g["id"], "time": dt.datetime.now().isoformat(timespec="seconds"), "label": g["label"],
             "source": g["source"], "files": changes}
    if g["undo_of"]:
        entry["undo_of"] = g["undo_of"]
    _append(entry)
    _remember([c["path"] for c in changes])  # 网页自己写的，下次扫描时不要再算成“别处的改动”


def _append(entry):
    with _lock:
        HIST.mkdir(exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------- 自动发现在别处的改动（Obsidian、记事本、Claude 直接改的文件）----------
_scan_lock = threading.Lock()


def _load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_state(state):
    HIST.mkdir(exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE)


def _remember(rels):
    with _scan_lock:
        state = _load_state()
        if state is None:
            return
        for rel in rels:
            p = ROOT / rel
            if p.is_file():
                st = p.stat()
                state[rel] = [st.st_mtime_ns, st.st_size, _key(p.read_bytes())]
            else:
                state.pop(rel, None)
        _save_state(state)


def scan(rels):
    """对比上次看到的样子，把在网页以外改过、新建、删掉的文件记成一条“别处的改动”。
    rels：要看管的文件（资料库里的所有 md）。第一次运行只建立底稿，不记改动。返回新记录的 id 或 None。"""
    if not _scan_lock.acquire(blocking=False):
        return None  # 另一个扫描正在跑
    try:
        state = _load_state()
        first = state is None
        state = state or {}
        changes, seen = [], set()
        for rel in rels:
            p = ROOT / rel
            try:
                st = p.stat()
            except OSError:
                continue
            seen.add(rel)
            old = state.get(rel)
            if old and old[0] == st.st_mtime_ns and old[1] == st.st_size:
                continue
            k = _key(p.read_bytes())
            if not first and (old is None or old[2] != k):
                changes.append({"path": rel, "before": old[2] if old else None, "after": k})
            state[rel] = [st.st_mtime_ns, st.st_size, k]
        for rel in [r for r in state if r not in seen]:
            if not (ROOT / rel).exists():
                if not first:
                    changes.append({"path": rel, "before": state[rel][2], "after": None})
                del state[rel]
        _save_state(state)
        if not changes:
            return None
        names = [c["path"].rsplit("/", 1)[-1] for c in changes]
        label = "在别处改了：" + "、".join(names[:3]) + (f" 等 {len(names)} 个文件" if len(names) > 3 else "")
        eid = f"{time.time_ns():x}"
        _append({"id": eid, "time": dt.datetime.now().isoformat(timespec="seconds"), "label": label,
                 "source": "别处", "files": changes})
        return eid
    finally:
        _scan_lock.release()


def install():
    """让所有通过 pathlib 写文件的地方都先经过 capture。只在网页服务进程里调用一次。"""
    if getattr(Path, "_twin_hist", False):
        return
    wt, wb, op, ul = Path.write_text, Path.write_bytes, Path.open, Path.unlink

    def write_text(self, *a, **k):
        capture(self)
        if len(a) < 3:
            k.setdefault("newline", "\n")  # Windows 上也写成 \n 换行，网页和 Obsidian 读起来一致
        return wt(self, *a, **k)

    def write_bytes(self, *a, **k):
        capture(self)
        return wb(self, *a, **k)

    def open_(self, mode="r", *a, **k):
        if any(c in mode for c in "wax+"):
            capture(self)
            if "b" not in mode and len(a) < 3:
                k.setdefault("newline", "\n")
        return op(self, mode, *a, **k)

    def unlink(self, *a, **k):
        capture(self)
        return ul(self, *a, **k)

    # 故意替换 Path 的写方法：所有写文件都经过改动历史
    Path.write_text, Path.write_bytes, Path.open, Path.unlink = write_text, write_bytes, open_, unlink  # pyright: ignore[reportAttributeAccessIssue]
    Path._twin_hist = True  # pyright: ignore[reportAttributeAccessIssue]


def _entries():
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def entries(limit=3000):  # 网页按日、周、月折叠，展开时才画，所以多给一些也不卡
    es = _entries()
    undone = {e["undo_of"]: e["id"] for e in es if e.get("undo_of")}
    out = []
    for e in reversed(es[-limit:]):
        out.append({"id": e["id"], "time": e["time"], "label": e["label"], "source": e["source"],
                    "files": [f["path"] for f in e["files"]], "undone": e["id"] in undone,
                    "undo_of": e.get("undo_of", "")})
    return out


def _find(eid):
    for e in _entries():
        if e["id"] == eid:
            return e
    raise RuntimeError("找不到这条记录了。")


def _text(data):
    if data is None:
        return []
    try:
        return data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None


def diff(eid):
    e = _find(eid)
    out = []
    for f in e["files"]:
        a, b = _text(_blob(f["before"])), _text(_blob(f["after"]))
        kind = "新建" if f["before"] is None else "删除" if f["after"] is None else "修改"
        if a is None or b is None:
            out.append({"path": f["path"], "kind": kind, "lines": ["（不是文本文件，不显示内容）"]})
            continue
        lines = list(difflib.unified_diff(a, b, lineterm="", n=2))[2:]
        out.append({"path": f["path"], "kind": kind, "lines": lines[:400]})
    return {"id": e["id"], "label": e["label"], "time": e["time"], "files": out}


def undo(eid, force=False):
    """把这条记录涉及的文件恢复成改之前的样子。文件后来又被改过时，默认不动，免得冲掉后来的改动。"""
    e = _find(eid)
    changed = []
    for f in e["files"]:
        p = ROOT / f["path"]
        now = _key(p.read_bytes()) if p.is_file() else None
        if now != f["after"]:
            changed.append(f["path"])
    if changed and not force:
        raise RuntimeError("CHANGED:" + "、".join(changed))
    with group(f"撤销：{e['label']}", "撤销", undo_of=eid) as g:
        for f in e["files"]:
            p = ROOT / f["path"]
            if f["before"] is None:
                if p.exists():
                    p.unlink()
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(_blob(f["before"]))
    return {"message": f"已撤销：{e['label']}", "id": g["id"]}


def since(days):
    """最近 days 天的记录，周报用。"""
    cut = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    return [e for e in _entries() if e["time"] >= cut]


def prune():
    """删掉太旧的记录和不再被引用的内容。"""
    if not LOG.exists():
        return
    cut = (dt.datetime.now() - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    with _lock:
        es = _entries()
        keep = [e for e in es if e["time"] >= cut]
        if len(keep) != len(es):
            LOG.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in keep), encoding="utf-8")
        used = {k for e in keep for f in e["files"] for k in (f["before"], f["after"]) if k}
        used |= {v[2] for v in (_load_state() or {}).values()}  # 每个文件的当前版本也要留着
        for d in BLOBS.glob("*") if BLOBS.exists() else []:
            for b in d.glob("*"):
                if b.name not in used:
                    b.unlink()
