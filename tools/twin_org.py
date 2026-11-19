#!/usr/bin/env python3
"""对话里的“帮我整理”（只用 Python 标准库）。

AI 在对话里提出动作，网页弹确认卡，点了“确认写入”才执行，每次都能在“改动历史”里撤销：
  - file_move    把暂存箱（或知识库里）的文件放到某个目录
  - note_create  在某个目录新建一篇笔记（internal）
  - note_append  在一篇非私密文档末尾追加内容
  - add_asset    新建一张资产卡片（私密）。价格区间只在本地卡片里填，不经过 AI。
  - asset_update 改已有资产卡片的状态、数量、放在哪（按名字在本地找，AI 看不到资产内容）
发给 AI 的：可以放文件的目录名、暂存箱里的文件名和文本内容（去掉私密段落和敏感值）、资产清单的分类标题。
资产清单的内容、私密文件的内容不发。
"""
import datetime as dt
import re
import shutil
from pathlib import Path

from twin import PRUNE, ROOT, privacy_of

import twin_ai
import twin_hist
import twin_inbox

NO_WRITE = {"_RULES", "_TEMPLATES", "tools", ".history", ".chats", "_VAULT", ".git", ".obsidian"}
ATTACH = re.compile(r"\[附件：([^\]\n]+)\]")
ATTACH_CAP = 6000


def _rel_ok(rel, must_exist=True):
    rel = str(rel or "").strip().strip("/").replace("\\", "/")
    p = (ROOT / rel).resolve()
    if not rel or ROOT.resolve() not in p.parents or set(Path(rel).parts) & (NO_WRITE | PRUNE):
        raise RuntimeError(f"这个位置不允许：{rel or '空'}")
    if must_exist and not p.exists():
        raise RuntimeError(f"找不到：{rel}")
    return rel, p


def _dir_ok(d):
    d = str(d or "").strip().strip("/")
    if d not in twin_inbox.targets():
        raise RuntimeError(f"目录“{d or '空'}”不在可以放的目录里，没有执行。")
    (ROOT / d).mkdir(parents=True, exist_ok=True)
    return ROOT / d


def _src(name):
    """暂存箱里的文件名，或知识库里的相对路径。"""
    name = str(name or "").strip().replace("\\", "/")
    if name.startswith("_INBOX/"):
        name = name[len("_INBOX/"):]
    if "/" not in name:
        return twin_inbox._item(name)
    _, p = _rel_ok(name)
    if not p.is_file():
        raise RuntimeError(f"不是文件：{name}")
    return p


def file_move(a):
    src = _src(a.get("from"))
    d = _dir_ok(a.get("to_dir"))
    nm = twin_inbox._safe_name(a.get("name") or src.name)
    if not Path(nm).suffix:
        nm += src.suffix
    target = twin_inbox._unique(d / nm)
    twin_hist.capture(src)
    twin_hist.capture(target)
    shutil.move(str(src), str(target))
    return f"已放到 {target.relative_to(ROOT).as_posix()}"


def note_create(a):
    d = _dir_ok(a.get("dir"))
    title = twin_ai._cell(a.get("title")) or "笔记"
    nm = twin_inbox._safe_name(a.get("name") or title)
    if not nm.endswith(".md"):
        nm = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", nm) + ".md"
    p = twin_inbox._unique(d / nm)
    body = str(a.get("text") or "").strip()
    p.write_text(f"---\ntype: note\nname: {title}\nupdated: {twin_ai.today()}\nprivacy: internal\n---\n# {title}\n\n{body}\n",
                 encoding="utf-8")
    return f"新建了 {p.relative_to(ROOT).as_posix()}"


def note_append(a):
    rel, p = _rel_ok(a.get("path"))
    if p.suffix != ".md":
        raise RuntimeError("只能往 .md 文档里追加。")
    text = p.read_text(encoding="utf-8")
    if privacy_of(text) in ("private", "secret"):
        raise RuntimeError("这是私密文档，AI 不能往里写。要加请自己打开编辑。")
    add = str(a.get("text") or "").strip()
    if not add:
        raise RuntimeError("没有要追加的内容。")
    head = a.get("heading")
    block = (f"\n## {twin_ai._cell(head)}\n" if head else "\n") + add + "\n"
    p.write_text(twin_ai._touch(text.rstrip("\n") + "\n" + block), encoding="utf-8")
    return f"已追加到 {rel}"


# ---------- 资产（旧总清单的列名对照，导入时用）----------
COLS = [("name", ("名称", "型号", "平台", "类别", "项目")), ("model", ("型号", "配置", "容量", "模块")),
        ("date", ("购入", "到期")), ("price", ("价格",)), ("qty", ("数量",)), ("status", ("状态", "健康")),
        ("note", ("用途", "备注", "存放", "付费"))]


def _colmap(header):
    """表头每一列对应哪个字段。第一列总是名称。"""
    out = []
    for i, h in enumerate(header):
        f = "name" if i == 0 else next((k for k, ws in COLS[1:] if any(w in h for w in ws)), "")
        out.append(f if f not in out else "")
    return out


def add_asset(a):
    """新建一张资产卡片（06_Assets 下对应的文件夹，私密）。价格区间来自本地卡片，不来自 AI。"""
    import twin_cards
    cat = a.get("category") or _section_cat(a.get("section", ""))
    fields = {k: a.get(k, "") for k in ("name", "model", "status", "qty", "acquired", "expires", "party", "value_range", "location")}
    fields["acquired"] = fields["acquired"] or a.get("date", "")
    fields["category"] = cat
    r = twin_cards.save("assets", "", fields)
    if a.get("note"):
        twin_cards.add_log("assets", r["path"], a["note"])
    return f"新建了资产卡片：{fields['name']}（私密）"


def _section_cat(sec):
    import twin_cards
    return next((c for w, c in twin_cards.SECTION_CAT if w in str(sec)), "physical")


def asset_update(a):
    """改一张已有资产卡片：状态、数量、放在哪；note 记进卡片的“记录”。"""
    import twin_cards
    c = twin_cards.find("assets", a.get("match") or a.get("name"))
    fields = {k: a[k] for k in ("status", "qty", "location", "expires", "party", "value_range") if a.get(k)}
    if fields:
        twin_cards.save("assets", c["path"], fields)
    if a.get("note"):
        twin_cards.add_log("assets", c["path"], a["note"])
    if not fields and not a.get("note"):
        raise RuntimeError("没有要改的内容。")
    words = dict(next(f for f in twin_cards.KINDS["assets"]["fields"] if f["key"] == "status")["options"])
    return f"{c['name']}：" + "，".join([f"状态 {words.get(fields['status'], fields['status'])}" if "status" in fields else "",
                                       *(f"{LABEL.get(k, k)} {v}" for k, v in fields.items() if k != "status"), a.get("note", "")]).strip("，")


LABEL = {"qty": "数量", "location": "放在哪", "expires": "到期", "party": "对方", "value_range": "价格区间"}


ACTIONS = {"file_move": file_move, "note_create": note_create, "note_append": note_append, "add_asset": add_asset,
           "asset_update": asset_update}


# ---------- 发给 AI 的整理背景 ----------
def _text_of(p):
    if twin_inbox._kind(p) != "text":
        return None
    raw = p.read_text(encoding="utf-8", errors="ignore")
    if privacy_of(raw) in ("private", "secret"):
        return "（私密文件，内容不发送）"
    return twin_ai._clean(re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)).strip()


def context(messages):
    """目录列表、暂存箱、资产分类；最后一句话里的附件带上文本内容。"""
    items = twin_inbox.items()
    inbox = "\n".join(f"- {it['name']}（{it['kind']}，{it['size'] // 1024 + 1} KB，{it['time']}）" for it in items) or "（空）"
    last = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    att = []
    for name in dict.fromkeys(ATTACH.findall(last)):
        try:
            p = twin_inbox._item(name.strip())
        except RuntimeError:
            att.append(f"<!-- 附件 {name}：已经不在暂存箱了 -->")
            continue
        body = _text_of(p)
        if body is None:
            att.append(f"<!-- 附件 {p.name}：{twin_inbox._kind(p)} 文件，只有文件名 -->")
        else:
            att.append(f"<!-- 附件 {p.name} 的内容（私密段落和敏感值已移除）-->\n{body[:ATTACH_CAP]}"
                       + ("\n…（后面省略）" if len(body) > ATTACH_CAP else ""))
    return ("\n\n=== 可以放文件、建笔记的目录（file_move / note_create 只能从这里选，原样写出）===\n" + "\n".join(twin_inbox.targets())
            + "\n\n=== 暂存箱里还没归档的文件 ===\n" + inbox
            + "\n\n=== 资产卡片的分类（add_asset 的 category 写左边的英文；资产内容是私密的，你看不到）===\n"
            + "\n".join(f"{g[0]}：{g[1]}" for g in __import__("twin_cards").KINDS["assets"]["groups"])
            + ("\n\n=== 这句话带的附件（已存进暂存箱）===\n" + "\n\n".join(att) if att else ""))
