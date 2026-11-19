#!/usr/bin/env python3
"""暂存箱：先把资料、截图、想法丢进 _INBOX，再决定放到哪里（只用 Python 标准库）。

  - 随手记：网页上写一段话，存成 _INBOX 里的一个 md。
  - 拖文件进网页，或者直接把文件复制到 _INBOX 文件夹。
  - 归档：自己选目录；或者请 AI 建议放哪、要不要给项目加任务。确认后才移动、才加任务。
  - 发给 AI 的：文本文件的内容（去掉私密段落和疑似敏感值，最多 6000 字）、文件名、目录名列表、项目名列表。
    图片、PDF、Office 文件只发文件名；压缩包发里面的文件名列表（不解压）。private / secret 文件只发文件名。
"""
import base64
import datetime as dt
import os
import re
import shutil
import zipfile
from pathlib import Path

from twin import PRUNE, ROOT, privacy_of

import twin_ai
import twin_hist

INBOX = ROOT / "_INBOX"
TEXT_EXT = {".md", ".txt", ".csv", ".json", ".log"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
SKIP_TOP = {"_INBOX", "_TEMPLATES", "_RULES", "tools", ".history", ".chats"}
MAX_UPLOAD = 25 * 1024 * 1024
README = """---
type: inbox
updated: {today}
privacy: internal
---
# 暂存箱

> 先把东西丢进这个文件夹（或者在网页“暂存箱”里随手记、拖文件进去），再在网页上归档。
> 归档时可以自己选位置，也可以请 AI 建议。移动和加任务都要你确认，都能在“改动历史”里撤销。
"""


def _ensure():
    INBOX.mkdir(exist_ok=True)
    r = INBOX / "README.md"
    if not r.exists():
        r.write_text(README.format(today=twin_ai.today()), encoding="utf-8")


ZIP_EXT = {".zip", ".rar", ".7z", ".tar", ".gz"}
OFFICE_EXT = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


def _kind(p):
    s = p.suffix.lower()
    return ("text" if s in TEXT_EXT else "image" if s in IMG_EXT else "pdf" if s == ".pdf" else
            "zip" if s in ZIP_EXT else "office" if s in OFFICE_EXT else "other")


def _safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", str(name)).strip().strip(".")
    return name[:120] or "untitled"


def _item(name):
    p = (INBOX / _safe_name(name))
    if not p.is_file() or p.name == "README.md":
        raise RuntimeError("暂存箱里没有这个文件了，刷新一下。")
    return p


def items():
    _ensure()
    out = []
    for p in sorted(INBOX.iterdir(), key=lambda x: -x.stat().st_mtime):
        if not p.is_file() or p.name == "README.md" or p.name.startswith("."):
            continue
        it = {"name": p.name, "size": p.stat().st_size, "kind": _kind(p),
              "time": dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M"), "preview": "",
              "age": (dt.date.today() - dt.date.fromtimestamp(p.stat().st_mtime)).days}
        if it["kind"] == "text":
            text = p.read_text(encoding="utf-8", errors="ignore")
            it["preview"] = re.sub(r"\s+", " ", re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S))[:220]
            if p.suffix == ".md":
                it["path"] = f"_INBOX/{p.name}"
        out.append(it)
    return out


def count():
    if not INBOX.exists():
        return 0
    return sum(1 for p in INBOX.iterdir() if p.is_file() and p.name != "README.md" and not p.name.startswith("."))


PROJECT_SUBDIRS = ("01_code", "02_docs", "03_materials")


_TARGETS = {"t": 0, "v": []}


def targets():
    """目录列表很少变，缓存 60 秒；归档时会新建目录，所以 move 之后清掉。"""
    import time
    if time.time() - _TARGETS["t"] > 60:
        _TARGETS["v"], _TARGETS["t"] = _targets(), time.time()
    return _TARGETS["v"]


def _targets():
    """可以归档到的目录：各分支往下两层；03_Projects 里到每个项目（有 board.md 或 index.md 的文件夹）
    和它的 01_code / 02_docs / 03_materials（还没建的也列出来，放进去时自动建）。"""
    out = []
    for top in sorted(ROOT.iterdir()):
        if not top.is_dir() or top.name in SKIP_TOP or top.name in PRUNE or top.name.startswith("."):
            continue
        for d, dirs, files in os.walk(top):
            rel = Path(d).relative_to(ROOT)
            dirs[:] = sorted(x for x in dirs if x not in PRUNE and not x.startswith("."))
            depth = len(rel.parts)
            if rel.parts[0] == "03_Projects":  # 项目放几层分类都行：到每个项目为止，加上它的编号子目录
                k = depth - 1
                if k >= 1 and ("board.md" in files or "index.md" in files):  # 按名字比，Windows 上 INDEX.md（分类总索引）不算项目
                    out.append(rel.as_posix())
                    vers = [x for x in dirs if re.match(r"V\d+_", x)]  # 拆了版本的项目：根目录只放说明，东西归到各版本和它的编号子目录
                    if vers:
                        for v in vers:
                            out.append((rel / v).as_posix())
                            out += [(rel / v / x).as_posix() for x in sorted(os.listdir(Path(d) / v)) if re.match(r"\d\d_", x) and (Path(d) / v / x).is_dir()]
                    else:
                        subs = dict.fromkeys([*PROJECT_SUBDIRS, *(x for x in dirs if re.match(r"\d\d_", x))])
                        out += [(rel / x).as_posix() for x in subs]
                    dirs[:] = []
                    continue
                if k > 3:
                    dirs[:] = []
                    continue
                if k == 3 and "00wheels" in rel.parts:
                    dirs[:] = []  # 轮子库到分类为止（sensors、display…），不列每个模块
            elif depth > 3:
                dirs[:] = []
                continue
            out.append(rel.as_posix())
    return out


def add_note(text, title=""):
    text = str(text or "").strip()
    if not text:
        raise RuntimeError("写点内容再存。")
    _ensure()
    now = dt.datetime.now()
    slug = _safe_name(title or re.sub(r"\s+", "_", text[:16]))
    p = INBOX / f"{now:%Y-%m-%d_%H%M}_{slug}.md"
    head = f"# {title}\n\n" if title else ""
    p.write_text(f"---\ntype: note\nupdated: {now:%Y-%m-%d}\nprivacy: internal\n---\n{head}{text}\n", encoding="utf-8")
    twin_hist.set_label(f"暂存箱：随手记 {p.name}")
    return {"name": p.name}


def upload(name, data_b64):
    _ensure()
    data = base64.b64decode(data_b64.split(",", 1)[-1])
    if len(data) > MAX_UPLOAD:
        raise RuntimeError("文件太大了（超过 25 MB）。大文件请直接复制到 _INBOX 文件夹。")
    p = _unique(INBOX / _safe_name(name))
    p.write_bytes(data)
    twin_hist.set_label(f"暂存箱：放入 {p.name}")
    return {"name": p.name}


def _unique(p):
    n = 2
    base, ext = p.stem, p.suffix
    while p.exists():
        p = p.with_name(f"{base}_{n}{ext}")
        n += 1
    return p


def move(name, dest, new_name="", new_dir=""):
    _TARGETS["t"] = 0
    src = _item(name)
    dest = str(dest or "").strip().strip("/")
    d = (ROOT / dest).resolve()
    if not dest or ROOT not in d.parents or set(Path(dest).parts) & (SKIP_TOP | PRUNE) or dest not in targets():
        raise RuntimeError("目标目录不对，请从列表里选。")
    new_dir = _safe_name(new_dir) if str(new_dir or "").strip() else ""
    if new_dir:  # 在选中的目录下新建一层文件夹（只能一层，名字去掉斜杠等）
        d = d / new_dir
    d.mkdir(parents=True, exist_ok=True)  # 项目的 03_materials 等还没建时自动建
    nm = _safe_name(new_name or src.name)
    if not Path(nm).suffix:
        nm += src.suffix
    target = _unique(d / nm)
    twin_hist.capture(src)
    twin_hist.capture(target)
    shutil.move(str(src), str(target))
    rel = target.relative_to(ROOT).as_posix()
    twin_hist.set_label(f"归档到 {target.parent.name}：{target.name}")
    return {"path": rel, "message": f"已放到 {rel}"}


def delete(name):
    p = _item(name)
    p.unlink()
    twin_hist.set_label(f"暂存箱：删掉 {p.name}")
    return {"ok": True}


SUGGEST_PROMPT = """我的暂存箱里有一件东西，帮我决定放到知识库的哪里，以及要不要给某个项目加任务。

文件名：{name}
类型：{kind}
我补充的说明：{note}
内容（私密段落和疑似敏感值已移除，可能被截断）：
<<<
{content}
>>>

可以放的目录（只能从这里选一个，原样写出）：
{dirs}

现有项目（加任务时 project 写项目名里的几个字）：
{projects}

如果列表里没有合适的，可以在某个目录下新建一层文件夹：dest 写那个已有目录，new_dir 写新文件夹名（短，中文或英文都行）；有合适的就让 new_dir 为空，别为一个文件就建文件夹。
规则：看文件名和后缀判断。项目相关的图片、PDF、表格、资料放进那个项目的 03_materials，文档放 02_docs，源码或工程压缩包放 01_code；不是项目的按内容放到对应分支。
只有内容里明确有要做的事时才加任务，最多 3 个。不确定就把 confidence 写低。
任务名要短（15 个字左右，比如“补拍第 17–23 课视频”），文件名、拍摄要求这些细节写进 note。同一件事合成一条，不要每个文件一条。
summary 一句话，20 个字以内。

只输出一个 json 代码块：
{{"summary":"一句话说这是什么","dest":"目录","new_dir":"要新建的文件夹名，不需要就空","name":"建议的文件名（保留扩展名，可以中文）","reason":"为什么放这里","tasks":[{{"project":"项目名","text":"任务","priority":"P0|P1|P2","due":"YYYY-MM-DD 或空","note":"细节，可空"}}],"confidence":"高|中|低"}}"""


def suggest(name, note="", provider_id=None):
    p = _item(name)
    kind = _kind(p)
    content = f"（不是文本文件，只能看文件名和后缀 {p.suffix.lower() or '无'}）"
    if p.suffix.lower() == ".zip":  # 压缩包只列里面的文件名（本地读目录，不解压），帮 AI 判断是代码、图纸还是资料
        try:
            ns = [n for n in zipfile.ZipFile(p).namelist() if not n.endswith("/")]
            content = f"压缩包，共 {len(ns)} 个文件，前几个：\n" + "\n".join(ns[:40])
        except zipfile.BadZipFile:
            pass
    if kind == "text":
        raw = p.read_text(encoding="utf-8", errors="ignore")
        if privacy_of(raw) in ("private", "secret"):
            content = "（这是私密文件，内容不发送）"
        else:
            content = twin_ai._clean(re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S))[:6000]
    twin_ai.check_outgoing(note or "")
    ds = targets()
    projects = "\n".join(f"- {re.split(r'[（(]', b['name'])[0].strip()}（{b['path'].rsplit('/', 1)[0]}）" for b in twin_ai.boards())
    prompt = SUGGEST_PROMPT.format(name=p.name, kind=kind, note=note or "无", content=content, dirs="\n".join(ds), projects=projects)
    ans = twin_ai.call_model("你是一个帮人整理知识库的助手，只按要求输出 json。", [{"role": "user", "content": prompt}],
                             twin_ai.active_provider(provider_id), 1200)
    data = twin_ai.parse_json_block(ans) or {}
    if data.get("dest") not in ds:
        data["dest"] = ""  # AI 编了一个不存在的目录，让用户自己选
    data["new_dir"] = _safe_name(data["new_dir"])[:40] if data.get("dest") and str(data.get("new_dir") or "").strip() else ""
    data["tasks"] = [t for t in data.get("tasks", []) if isinstance(t, dict) and t.get("text")][:3]
    return data

