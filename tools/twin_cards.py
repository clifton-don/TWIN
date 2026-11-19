#!/usr/bin/env python3
"""卡片：资产、人脉这类“一样东西一张卡”的资料（只用 Python 标准库）。

一张卡就是一个 md 文件：Frontmatter 放字段，正文放备注和记录。网页上看到的是卡片，
改了字段也是写回这个 md，所以 Obsidian、记事本里照样能看能改。
每种卡片长什么样（字段、分组、放在哪个文件夹）都写在下面的 KINDS 里，网页按这个画，
以后要加新的卡片类型（比如证书、订阅），在 KINDS 里加一项就行。

这些文件都是 private，只在本机网页显示，不发给 AI。
例外：人脉卡上“给 AI 看摘要”选了“给”的，按 people_for_ai() 只发几项摘要（联系方式、记录、正文都不发）。
"""
import json
import re
import shutil

from twin import ROOT, walk_md

import twin_ai
import twin_hist
import twin_inbox

# 字段类型：text 文本、select 选一个、list 多个（存成 ["a", "b"]）、date 日期、readonly 只显示不改
KINDS = {
    "assets": {
        "title": "资产", "noun": "资产", "type": "asset", "base": "06_Assets", "group": "category",
        "groups": [  # 值、显示名、放在哪个文件夹
            ["device", "数码设备", "01_Devices"], ["digital", "账号与订阅", "02_Digital"],
            ["tool", "工具仪器", "04_Physical"], ["parts", "开发板与模块", "04_Physical"],
            ["physical", "其他实物", "04_Physical"], ["lease", "房屋与租约", "05_Leases"]],
        "badge": "status",
        "fields": [
            {"key": "name", "label": "名称", "type": "text"},
            {"key": "category", "label": "分类", "type": "select"},
            {"key": "model", "label": "型号 / 配置", "type": "text"},
            {"key": "status", "label": "状态", "type": "select",
             "options": [["in_use", "在用"], ["idle", "闲置"], ["lent", "借出"], ["broken", "坏了"], ["sold", "已卖"]]},
            {"key": "qty", "label": "数量", "type": "text"},
            {"key": "acquired", "label": "购入 / 起租", "type": "text", "hint": "比如 2026-03"},
            {"key": "expires", "label": "到期", "type": "text", "hint": "租约、订阅、保修到期，比如 2027-06-30"},
            {"key": "party", "label": "对方", "type": "text", "hint": "房东、卖家、服务商"},
            {"key": "value_range", "label": "价格 / 租金区间", "type": "text", "hint": "只写区间，比如 3k-5k；精确金额放保险箱"},
            {"key": "location", "label": "放在哪 / 托管在哪", "type": "text"},
            {"key": "serial", "label": "序列号 / 账号", "type": "readonly", "hint": "真实值在保险箱"},
        ],
        "sub": ["model", "location"], "meta": ["acquired", "expires", "value_range", "qty"],
        "template": "_TEMPLATES/asset.md",
    },
    "people": {
        "title": "人脉", "noun": "联系人", "type": "person", "base": "05_Network", "group": "relation",
        "groups": [["mentor", "导师", "01_Mentors"], ["collaborator", "合作方", "02_Collaborators"],
                   ["teammate", "队友", "03_Teammates"], ["industry", "行业", "04_Industry"],
                   ["personal", "朋友家人", "05_Personal"]],
        "badge": "relation",
        "fields": [
            {"key": "name", "label": "名字", "type": "text"},
            {"key": "relation", "label": "关系", "type": "select"},
            {"key": "ai", "label": "给 AI 看摘要", "type": "select", "options": [["yes", "给"]], "blank": "不给"},
            {"key": "org", "label": "在哪做什么", "type": "text", "hint": "公司或学校、职位"},
            {"key": "city", "label": "城市", "type": "text"},
            {"key": "strengths", "label": "擅长", "type": "list", "hint": "用逗号隔开", "wide": True},
            {"key": "help", "label": "能互相帮什么", "type": "text", "hint": "比如 他帮我看原理图，我帮他写网页", "wide": True},
            {"key": "projects", "label": "一起做的项目", "type": "list"},
            {"key": "last_contact", "label": "上次联系", "type": "text", "hint": "比如 2026-10-21"},
            {"key": "contact", "label": "联系方式", "type": "readonly", "hint": "真实值在保险箱", "wide": True},
        ],
        "sub": ["org", "strengths"], "meta": ["last_contact", "projects"],
        "template": "_TEMPLATES/person.md",
    },
}
for _k in KINDS.values():  # 分组字段的选项就是分组本身
    next(f for f in _k["fields"] if f["key"] == _k["group"])["options"] = [[g[0], g[1]] for g in _k["groups"]]

LOG_HEAD = "## 记录"
_FM = re.compile(r"^---\n(.*?)\n---\n?", re.S)


def _fm(text):
    """卡片的 Frontmatter（卡片都是 TWIN 自己写的，一定有）。"""
    m = _FM.match(text)
    if not m:
        raise RuntimeError("卡片开头的 --- 属性区格式不对。")
    return m


def _kind(kind):
    if kind not in KINDS:
        raise RuntimeError("没有这种卡片。")
    return KINDS[kind]


def expiring(days=30):
    """快到期（或已过期）的资产：租约、订阅、保修。只给本机网页的“今天”页用，不发给 AI。"""
    import datetime as dt
    today_, out = dt.date.today(), []
    for c in items("assets")["items"]:
        m = re.match(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", c.get("expires", ""))
        if not m or c.get("status") == "sold":
            continue
        try:
            d = dt.date(int(m[1]), int(m[2]), int(m[3] or 28))
        except ValueError:
            continue
        if (d - today_).days <= days:
            out.append({"name": c["name"], "path": c["path"], "due": c["expires"], "days": (d - today_).days})
    return sorted(out, key=lambda x: x["days"])


def ai_line(c):
    """一个人发给 AI 的那一行摘要（卡片上也显示这一行）。疑似敏感的字段整项不发。"""
    from twin import find_sensitive
    rel = {g[0]: g[1] for g in KINDS["people"]["groups"]}
    if find_sensitive(c["name"]):
        return ""
    parts = [("做什么", c.get("org")), ("在", c.get("city")), ("擅长", "、".join(c.get("strengths") or [])),
             ("能互相帮", c.get("help")), ("一起做过", "、".join(c.get("projects") or [])), ("上次联系", str(c.get("last_contact") or "")[:7])]
    txt = "；".join(f"{a} {b}" for a, b in parts if b and not find_sensitive(str(b)))
    return f"{c['name']}（{rel.get(c.get('relation'), '认识的人')}）" + (f"：{txt}" if txt else "")


def people_for_ai():
    """选了“给 AI 看摘要”的人，每人一行。"""
    lines = [ai_line(c) for c in items("people")["items"] if c.get("ai") == "yes"]
    return "\n".join("- " + x for x in lines if x)


def schema():
    return {k: {x: v[x] for x in ("title", "noun", "group", "groups", "badge", "fields", "sub", "meta")} for k, v in KINDS.items()}


# ---------- 读写 Frontmatter ----------
def _parse_value(v):
    v = v.strip()
    if v.startswith("["):
        try:
            return [str(x) for x in json.loads(v)]
        except ValueError:
            return [x.strip().strip('"') for x in v.strip("[]").split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1]
    return v


def read_fm(text):
    m = _FM.match(text)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            if not line or line[0] in " #-" or ":" not in line:
                continue
            k, _, v = line.partition(":")
            v = re.split(r"\s+#\s", v, maxsplit=1)[0]  # 去掉行尾注释
            out[k.strip()] = _parse_value(v)
    return out


def _dump_value(v):
    if isinstance(v, list):
        return json.dumps([str(x) for x in v if str(x).strip()], ensure_ascii=False)
    v = str(v or "").replace("\n", " ").strip()
    if not v:
        return '""'
    if re.search(r"(:\s|\s#|^[\[{\"'*&!|>%@`])", v) or v.lower() in ("true", "false", "null", "yes", "no"):
        return json.dumps(v, ensure_ascii=False)
    return v


def write_fm(text, values):
    """只改给出的字段，其他行（包括注释）原样保留；没有的字段加在 updated 前面。"""
    m = _FM.match(text)
    if not m:
        text = "---\nprivacy: private\n---\n" + text
        m = _fm(text)
    lines = m.group(1).splitlines()
    for k, v in values.items():
        new = f"{k}: {_dump_value(v)}"
        i = next((i for i, l in enumerate(lines) if re.match(rf"{re.escape(k)}\s*:", l)), None)
        if i is not None:
            lines[i] = new
        else:
            at = next((i for i, l in enumerate(lines) if re.match(r"(updated|privacy)\s*:", l)), len(lines))
            lines.insert(at, new)
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end():]


def body_of(text):
    return _FM.sub("", text, count=1)


# ---------- 卡片 ----------
def _files(k):
    base = ROOT / k["base"]
    for p in walk_md(base) if base.exists() else []:
        if p.name.startswith("_") or p.name in ("Asset_List.md",):  # 总清单是旧的总表，不是一张卡
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = read_fm(text)
        if fm.get("type") == k["type"]:
            yield p, text, fm


def _card(k, p, text, fm):
    c = {"path": p.relative_to(ROOT).as_posix(), "updated": str(fm.get("updated", ""))}
    for f in k["fields"]:
        lst = f["type"] == "list"
        v = fm.get(f["key"], [] if lst else "")
        c[f["key"]] = (v if isinstance(v, list) else [v] if v else []) if lst else str(v)
    if not c["name"] or c["name"] in ("姓名", "资产名称"):
        c["name"] = p.stem
    body = body_of(text)
    c["body"] = body
    # 正文里第一句实际内容（不是标题、注释、记录），卡片上没有别的副标题时显示它
    c["summary"] = next((l.strip("- ").strip() for l in re.sub(r"<!--.*?-->", "", body.split(LOG_HEAD)[0], flags=re.S).splitlines()
                         if l.strip() and not l.startswith("#") and l.strip("- ").strip()), "")[:80]
    c["log_all"] = _log_lines(body)
    if k["type"] == "person":
        c["ai_line"] = ai_line(c)
    c["log"] = c["log_all"][-3:]
    return c


def items(kind):
    k = _kind(kind)
    out = [_card(k, p, t, fm) for p, t, fm in _files(k)]
    out.sort(key=lambda c: (c.get(k["group"], ""), c["name"]))
    return {"items": out, "schema": schema()[kind]}


def _path_ok(k, rel):
    p = (ROOT / str(rel or "")).resolve()
    if (ROOT / k["base"]).resolve() not in p.parents or p.suffix != ".md" or not p.is_file():
        raise RuntimeError("找不到这张卡片了，刷新一下。")
    return p


def _folder(k, group):
    g = next((g for g in k["groups"] if g[0] == group), k["groups"][0])
    return ROOT / k["base"] / g[2], g[0]


def _clean_values(k, fields):
    out = {}
    for f in k["fields"]:
        if f["type"] == "readonly" or f["key"] not in fields:
            continue
        v = fields[f["key"]]
        if f["type"] == "list":
            if isinstance(v, str):
                v = re.split(r"[,，、]\s*", v)
            v = [twin_ai._cell(x) for x in v if str(x).strip()]
        else:
            v = twin_ai._cell(v)
            if f["type"] == "select" and v and v not in [o[0] for o in f["options"]]:
                v = next((o[0] for o in f["options"] if o[1] == v), "")  # 写的是中文名也认
                if not v:
                    raise RuntimeError(f"“{f['label']}”只能选：" + "、".join(o[1] for o in f["options"]))
        out[f["key"]] = v
    return out


def _new_text(k, name):
    try:
        tpl = (ROOT / k["template"]).read_text(encoding="utf-8")
    except OSError:
        tpl = f"---\ntype: {k['type']}\nname: \nupdated: \nprivacy: private\n---\n# \n"
    tpl = tpl.replace("资产名称", name).replace("姓名", name)
    return re.sub(r"^# .*$", f"# {name}", tpl, count=1, flags=re.M)


def save(kind, rel, fields, body=None):
    """新建（rel 为空）或修改一张卡。分组改了就把文件挪到对应文件夹。"""
    k = _kind(kind)
    vals = _clean_values(k, fields or {})
    if rel:
        p = _path_ok(k, rel)
        text = p.read_text(encoding="utf-8")
        name = vals.get("name") or read_fm(text).get("name") or p.stem
    else:
        name = vals.get("name", "")
        if not name:
            raise RuntimeError(f"{k['noun']}要有名字。")
        d, vals[k["group"]] = _folder(k, vals.get(k["group"], ""))
        d.mkdir(parents=True, exist_ok=True)
        p = twin_inbox._unique(d / (twin_inbox._safe_name(name) + ".md"))
        text = _new_text(k, name)
    vals["updated"] = twin_ai.today()
    text = write_fm(text, vals)
    if body is not None:
        text = _fm(text).group(0) + str(body).replace("\r\n", "\n").lstrip("\n")
    elif not rel:
        text = re.sub(r"^# .*$", f"# {name}", text, count=1, flags=re.M)
    p.write_text(text, encoding="utf-8")
    # 分组变了：挪到对应文件夹
    d, _ = _folder(k, read_fm(text).get(k["group"], ""))
    if rel and p.parent != d:
        d.mkdir(parents=True, exist_ok=True)
        target = twin_inbox._unique(d / p.name)
        twin_hist.capture(target)
        shutil.move(str(p), str(target))
        p = target
    twin_hist.set_label(f"{'改' if rel else '新建'}{k['noun']}卡片：{name}")
    return {"path": p.relative_to(ROOT).as_posix(), "message": f"已保存：{name}"}


def _log_lines(body):
    m = re.search(rf"^{LOG_HEAD}\s*$(.*?)(?=^## |\Z)", body, re.M | re.S)
    return [l[2:].strip() for l in m.group(1).splitlines() if l.startswith("- ")] if m else []


def add_log(kind, rel, text, when=None):
    """在“## 记录”下面加一行“- 日期 内容”。人脉卡顺便把上次联系改成今天。"""
    k = _kind(kind)
    p = _path_ok(k, rel)
    entry = twin_ai._cell(text)
    if not entry:
        raise RuntimeError("写点内容再记。")
    day = when or twin_ai.today()
    src = p.read_text(encoding="utf-8")
    line = f"- {day} {entry}"
    m = re.search(rf"^{LOG_HEAD}\s*$(.*?)(?=^## |\Z)", src, re.M | re.S)
    if m:
        block = m.group(1).rstrip("\n")
        src = src[:m.start(1)] + block + ("\n" if block else "\n") + line + "\n\n" + src[m.end(1):].lstrip("\n")
    else:
        src = src.rstrip("\n") + f"\n\n{LOG_HEAD}\n{line}\n"
    vals = {"updated": twin_ai.today()}
    if kind == "people":
        vals["last_contact"] = day
    p.write_text(write_fm(src, vals), encoding="utf-8")
    name = read_fm(src).get("name") or p.stem
    twin_hist.set_label(f"{name}：记一笔")
    return {"message": f"已记到 {name}"}


def delete(kind, rel):
    k = _kind(kind)
    p = _path_ok(k, rel)
    name = read_fm(p.read_text(encoding="utf-8")).get("name") or p.stem
    p.unlink()
    twin_hist.set_label(f"删掉{k['noun']}卡片：{name}")
    return {"message": f"已删掉：{name}（可以在改动历史里撤销）"}


def find(kind, key):
    """按名字找一张卡（对话里用）：先找名字完全一样的，再找包含这几个字的。"""
    key = str(key or "").strip()
    cs = items(kind)["items"]
    hits = [c for c in cs if c["name"] == key] or [c for c in cs if key and (key in c["name"] or key in c.get("model", ""))]
    if len(hits) != 1:
        raise RuntimeError(f"名字含“{key}”的{_kind(kind)['noun']}卡片有 {len(hits)} 张，没法确定是哪张。到“{_kind(kind)['title']}”页里改吧。")
    return hits[0]


# ---------- 从旧的资产总清单导入 ----------
ASSET_LIST = ROOT / "06_Assets" / "Asset_List.md"
SECTION_CAT = [("电脑", "device"), ("存储", "device"), ("开发板", "parts"), ("工具", "tool"), ("数字", "digital"), ("其他实物", "physical")]
IMPORT_NOTE = "> 已经填了内容的行转成了资产卡片（在网页“资产”页里看和改），这里只留没填的。"
STATUS_CN = {"在用": "in_use", "闲置": "idle", "借出": "lent", "坏了": "broken", "坏": "broken", "已卖": "sold", "卖了": "sold"}


def import_assets():
    """把总清单里已经填了内容的行变成一张张卡片，再从表里拿掉这些行。传感器那节是清点用的，不导入。"""
    import twin_org
    text = ASSET_LIST.read_text(encoding="utf-8")
    lines, made, drop = text.splitlines(), [], set()
    sec = None
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("## "):
            sec = next((c for w, c in SECTION_CAT if w in l), None)
        if sec and l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in l.strip().strip("|").split("|")]
            cmap = twin_org._colmap(header)
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                name = cells[0].replace("✱", "").strip()
                filled = [c for c in cells[1:] if c and not c.startswith("{{VAULT")]
                if name and name != "其他" and filled:
                    v = {f: cells[n] for n, f in enumerate(cmap) if f and n < len(cells) and cells[n]}
                    note = [f"{header[n]}：{cells[n]}" for n, f in enumerate(cmap) if not f and n < len(cells) and cells[n]]
                    fields = {"name": name, "category": sec, "model": v.get("model", ""), "acquired": v.get("date", ""),
                              "value_range": v.get("price", ""), "qty": v.get("qty", ""), "location": "",
                              "status": STATUS_CN.get(v.get("status", ""), "in_use" if sec != "digital" else "")}
                    body = "## 用途\n" + v.get("note", "") + "\n\n## 配置 / 备注\n" + "\n".join(f"- {x}" for x in note) + "\n"
                    made.append(save("assets", "", fields, None)["path"])
                    p = ROOT / made[-1]
                    t = p.read_text(encoding="utf-8")
                    p.write_text(_fm(t).group(0) + f"# {name}\n\n" + body, encoding="utf-8")
                    acct = next((c for c in cells if c.startswith("{{VAULT")), "")
                    if acct:
                        p.write_text(write_fm(p.read_text(encoding="utf-8"), {"serial": acct}), encoding="utf-8")
                    drop.add(j)
                j += 1
            i = j
            continue
        i += 1
    if not made:
        return {"message": "总清单里没有可以导入的行（只有名字、其他格子都空着的行不导入）。", "count": 0}
    keep = [l for n, l in enumerate(lines) if n not in drop]
    out = "\n".join(keep) + "\n"
    if IMPORT_NOTE not in out:
        out = re.sub(r"^(# .*\n)", r"\1\n" + IMPORT_NOTE + "\n", out, count=1, flags=re.M)
    ASSET_LIST.write_text(twin_ai._touch(out), encoding="utf-8")
    twin_hist.set_label(f"总清单导入成 {len(made)} 张资产卡片")
    return {"message": f"导入了 {len(made)} 张卡片", "count": len(made)}
