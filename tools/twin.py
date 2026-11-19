#!/usr/bin/env python3
"""知识库工具（只用 Python 标准库）。

用法（在知识库根目录运行）：
  python tools/twin.py scan   检查缺少 privacy 字段的文件和疑似明文敏感值
  python tools/twin.py pack   生成 context_pack.md，这是唯一允许发给云端 AI 的内容
  python tools/twin.py codescan 01data
                              推送代码仓库前，检查代码里的密码、密钥、证书私钥
  python tools/twin.py blank  打包一份不含任何资料的空白 TWIN（给别人用），放在 _export/ 里
"""
import os
import re
import sys
from pathlib import Path
from typing import AbstractSet
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"_VAULT", ".git", ".obsidian", "tools", "01data"}
SKIP_SUBDIRS = {"diy_mk"}  # 项目库：内部文件不按 privacy 规则检查
# 项目库的索引本身就是该树枝的总结，打包时一并带上
PROJECT_INDEXES = ["03_Projects/diy_mk/INDEX.md"]
SKIP_FILES = {"CLAUDE.md", "AGENTS.md", "README.md", "context_pack.md"}  # 仓库首页和给 AI 工具的说明，不按 privacy 规则查
LEVELS = ("public", "internal", "private", "secret")

# 忘了写结束标记时，一直到文件末尾都算私密（和网页的显示一致），宁可少发也不能漏发
PRIVATE_BLOCK = re.compile(r"<!--\s*private\s*-->.*?(?:<!--\s*/private\s*-->|\Z)", re.S | re.I)
SENSITIVE = {
    "身份证号": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "银行卡号": re.compile(r"(?<![\dA-Za-z/.])\d{16,19}(?![\dA-Za-z])"),  # 链接、DOI 里的长数字不算
    "邮箱": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
}


# 遍历时整棵跳过的目录：源码库、依赖和构建产物，文件多，在移动硬盘上逐个扫会很慢
PRUNE = {".git", "node_modules", "miniprogram_npm", "build", ".pio", "dist", "__pycache__", ".obsidian",
         "_VAULT", ".chats", ".trash", "01data", ".history"}


PROJECTS = ROOT / "03_Projects"


def project_dirs():
    """03_Projects 下的每个项目文件夹：有 index.md（说明）或 board.md（任务板块）的就算，叫什么、放几层分类都行。
    找到项目就不再往里走，01_code 这类编号子目录、00wheels 轮子库也不进，所以不遍历源码。"""
    out = []
    for d, dirs, files in os.walk(PROJECTS):
        rel = Path(d).relative_to(PROJECTS)
        if rel.parts and ("index.md" in files or "board.md" in files):
            out.append(Path(d))
            dirs[:] = []
            continue
        dirs[:] = [] if len(rel.parts) >= 4 else [x for x in dirs if x not in PRUNE and not x.startswith(".")
                                                   and x != "00wheels" and not re.match(r"^\d\d_", x)]
    return sorted(out)


def project_boards():
    return [d / "board.md" for d in project_dirs() if (d / "board.md").exists()]


def walk_md(base=None, skip: AbstractSet[str] = frozenset()):
    """按目录剪枝地找 .md 文件（不进入 PRUNE 和 skip 里的目录）。返回排好序的 Path 列表。"""
    out = []
    for d, dirs, files in os.walk(base or ROOT):
        dirs[:] = [x for x in dirs if x not in PRUNE and x not in skip]
        out += [Path(d) / f for f in files if f.endswith(".md")]
    return sorted(out)


def md_files():
    for p in walk_md(ROOT, SKIP_SUBDIRS | {"tools"}):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in SKIP_DIRS or str(rel) in SKIP_FILES:
            continue
        yield p, rel


def privacy_of(text):
    """返回 privacy 级别；没有 Frontmatter 或字段时返回 None。"""
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.strip().lower().startswith("privacy:"):
            value = line.split(":", 1)[1].split("#")[0].strip().lower()
            # 值中含有 private / secret 字样，按更严格的级别处理
            for level in ("secret", "private", "internal", "public"):
                if level in value:
                    return level
            return None
    return None


def _luhn(num):
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch) * (2 if i % 2 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


def _real_card(num):
    """真银行卡号：开头是 3/4/5/6（或万事达 2221–2720），并且通过 Luhn 校验。时间戳、设备号一般过不了。"""
    ok_prefix = num[0] in "3456" or 222100 <= int(num[:6]) <= 272099
    return ok_prefix and _luhn(num)


def _real_id(num):
    """18 位身份证号：出生日期合理，最后一位校验码对得上。"""
    if not ("19000101" <= num[6:14] <= "20991231"):
        return False
    w = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    return "10X98765432"[sum(int(a) * b for a, b in zip(num[:17], w)) % 11] == num[17].upper()


def find_sensitive(text):
    text = PRIVATE_BLOCK.sub("", text)
    hits, seen = [], []
    for name, pat in SENSITIVE.items():
        for m in pat.finditer(text):
            if (name == "银行卡号" and not _real_card(m.group(0))) or (name == "身份证号" and not _real_id(m.group(0))):
                continue  # 长得像但不是：时间戳、设备 ID、产品密钥里的数字等
            # 同一段数字只报一次（身份证号也会匹配银行卡号规则）
            if any(a <= m.start() < b for a, b in seen):
                continue
            seen.append(m.span())
            hits.append((name, m.group(0)))
    return hits


def mask(value):
    return value[:2] + "*" * max(len(value) - 4, 0) + value[-2:]


def scan():
    problems = 0
    for p, rel in md_files():
        text = p.read_text(encoding="utf-8")
        level = privacy_of(text)
        if level is None:
            print(f"[缺少 privacy，按 secret 处理] {rel}")
            problems += 1
        for name, value in find_sensitive(text):
            print(f"[疑似明文{name}: {mask(value)}] {rel}  → 请移入 _VAULT，改用 {{{{VAULT:名称}}}}")
            problems += 1
    print(f"\n检查完成，发现 {problems} 个问题。" if problems else "检查完成，没有发现问题。")
    return problems


CODE_EXT = {".ino", ".c", ".cpp", ".h", ".hpp", ".py", ".js", ".ts", ".json", ".lua",
            ".yaml", ".yml", ".env", ".ini", ".conf", ".txt", ".md", ".sh"}
CODE_SKIP = {"node_modules", "miniprogram_npm", "build", ".pio", ".git", "__pycache__", "dist"}
SECRET = {
    "证书私钥": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "API Key": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    "疑似密码/密钥": re.compile(
        r"(?i)\b\w*(pass(word|wd)?|pwd|ssid|token|secret|api_?key|app_?key|access_?key|"
        r"device_?key|product_?key|client_?id)\w*\b[\"']?\s*[:=]\s*[\"']([^\"'\s]{4,})[\"']"),
    "疑似 #define 密钥": re.compile(
        r"(?i)#define\s+\w*(pass|ssid|key|token|secret|pwd)\w*\s+\"([^\"]{4,})\""),
}


def codescan(target):
    base = (ROOT / target).resolve() if not Path(target).is_absolute() else Path(target)
    hits = 0
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in CODE_EXT:
            continue
        if any(part in CODE_SKIP for part in p.parts) or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pat in SECRET.items():
                m = pat.search(line)
                if not m:
                    continue
                value = m.groups()[-1] if m.groups() else m.group(0)
                if value.startswith("{{VAULT") or value.upper() in {"YOUR_SSID", "YOUR_PASSWORD", "XXXX"}:
                    continue
                rel = p.relative_to(base)
                print(f"[{name}] {rel}:{lineno}  {mask(value)}")
                hits += 1
                break
    if hits:
        print(f"\n发现 {hits} 处疑似敏感信息。推送到 GitHub 之前，请把这些值移到 secrets.h / config.json 等单独文件，"
              "并把该文件加入 .gitignore。")
    else:
        print("没有发现疑似敏感信息。")
    return hits


def has_leaves(folder):
    return any(f.name != "_SUMMARY.md" for f in walk_md(folder, SKIP_SUBDIRS))


# _RULES 里除了访问规则，经验教训也属于上云内容（AI 据此调整建议）
PUBLIC_RULES = {"AI_ACCESS_RULES.md", "Lessons.md"}


def public_context():
    """收集可以发给云端 AI 的内容。返回 (各文件文本列表, 被拦截的文件)。"""
    out, blocked = [], []
    for p, rel in md_files():
        if rel.parts[0] == "_RULES" and rel.name not in PUBLIC_RULES:
            continue
        text = p.read_text(encoding="utf-8")
        if privacy_of(text) != "public":
            continue
        if p.name == "_SUMMARY.md" and not has_leaves(p.parent):
            continue  # 还没有叶子的分支不上云
        body = PRIVATE_BLOCK.sub("[私密段落已移除]", text)
        hits = find_sensitive(body)
        if hits:
            blocked.append((rel, hits))
            continue
        out.append(f"\n\n<!-- 文件：{rel.as_posix()} -->\n\n{body.strip()}")
    for rel_str in PROJECT_INDEXES:
        p = ROOT / rel_str
        if not p.exists():
            continue
        body = PRIVATE_BLOCK.sub("[私密段落已移除]", p.read_text(encoding="utf-8"))
        hits = find_sensitive(body)
        if hits:
            blocked.append((Path(rel_str), hits))
        else:
            out.append(f"\n\n<!-- 文件：{rel_str} -->\n\n{body.strip()}")
    return out, blocked


PACK_HEADER = ("# 个人知识库上下文包（仅含 public 层：决策端与各分支总结）\n\n"
               "> 细节文件未包含。需要细节时请告诉我文件名，由我在本地查看。\n")


def pack():
    out, blocked = public_context()
    if blocked:
        print("以下 public 文件含疑似敏感值，已拒绝打包，请先处理：")
        for rel, hits in blocked:
            print(f"  {rel}: " + "、".join(f"{n} {mask(v)}" for n, v in hits))
        return 1
    target = ROOT / "context_pack.md"
    target.write_text(PACK_HEADER + "".join(out) + "\n", encoding="utf-8")
    print(f"已生成 {target.name}，共 {len(out)} 个文件。可以发给云端 AI。")
    return 0


# 空白版：程序、说明、通用规则和模板，加上空的树枝文件夹；资料、对话、密码、缓存一概不带。
# 别人解压后双击 Open_Web.bat，第一次打开会设密码、走设置向导，规则文件按默认值自动生成
BLANK_FILES = ["README.md", "LICENSE", "Guide.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md", "Open_Web.bat", ".gitignore", ".gitattributes",
               "_RULES/AI_ACCESS_RULES.md", "_RULES/FIELD_SPEC.md"]
BLANK_TREES = ["tools", "_TEMPLATES"]  # docs/ 里是 GitHub 首页的图，空白版不带，省体积
BLANK_SKIP = {"__pycache__", ".cache", ".auth.json", "health_ignore.json", "rename_v3.py"}
BLANK_DIRS = ["_INBOX", "00_Crown"]
# 空白版每个树干放一份 _SUMMARY.md：这里存什么、怎么存、建议的分支。(说明, 模板, 默认密级, [(分支, 范围)])
BLANK_GUIDE = {
    "01_Skills": ("工作、学术、职业相关的能力。一个技能一个文件，写会到什么程度、在哪用过、下一步补什么。做饭、运动这类放 02_Life。",
                  "skill.md", "internal", [("01_Engineering", "工程技术"), ("02_Academic", "数学、论文、实验"), ("03_Language", "写作、外语、演讲"),
                                           ("04_Social", "团队、管理"), ("05_Mind", "学习方法、决策、知识管理"), ("06_Business", "接单、报价、合同")]),
    "02_Life": ("生活里的能力、偏好和状态：会做的菜、运动记录、去过的地方、喜欢的音乐。能力类用 skill 模板，清单和偏好类用 life 模板。",
                "life.md", "internal", [("01_Cooking", "烹饪"), ("02_Sports", "运动"), ("03_Health", "健康"), ("04_Music", "音乐"), ("05_Art", "艺术"),
                                        ("06_Hobbies", "兴趣"), ("07_Travel", "旅行"), ("08_Home", "居家"), ("09_Finance", "理财（只写习惯和规则，不写金额）"),
                                        ("10_Affairs", "证件、事务（只写流程和链接）"), ("11_Relationships", "情感"), ("12_Growth", "成长")]),
    "03_Projects": ("在做和做过的项目。一个项目一个文件夹，可以按分类套几层；文件夹里有 index.md（项目说明）或 board.md（任务板块）就算一个项目，在“待办 → 项目库”里都能找到。在网页里新建项目会自动建好 index.md、board.md 和 01_code / 02_docs / 03_materials。TWIN 只读 md，工程文件原地放着，代码用 Git 管，大文件放网盘，index.md 里写链接。",
                    "project.md", "internal", []),
    "04_Milestones": ("已经发生的经历：毕业、比赛、发表、入职、搬家。一件事一个文件，写时间、做了什么、结果，可以链到相关技能和项目。",
                      "milestone.md", "internal", [("01_Education", "教育"), ("02_Projects", "项目履历"), ("03_Competitions", "竞赛"), ("04_Research", "科研"),
                                                   ("05_Career", "职业"), ("06_Life_Events", "生活大事")]),
    "05_Network": ("认识的人：怎么认识的、能互相帮什么、上次联系是什么时候。人物卡默认 private，不会发给 AI；某张卡选了“给 AI 看摘要”才发几项摘要。电话、住址这些不要写，需要的话写保险箱占位符。",
                   "person.md", "private", [("01_Mentors", "导师"), ("02_Collaborators", "合作者"), ("03_Teammates", "队友"), ("04_Industry", "行业"), ("05_Personal", "亲友")]),
    "06_Assets": ("设备、账号、实物、财务。默认 private，不会发给 AI。只写“有什么、放在哪、怎么用”，密码、卡号、金额不写进来，放在知识库外面的保险箱，这里用 {{VAULT:名称}} 占位。",
                  "asset.md", "private", [("01_Devices", "设备"), ("02_Digital", "数字资产、账号"), ("03_Finance", "财务"), ("04_Physical", "实物")]),
    "07_Decisions": ("做过的重要决定：当时的选项、为什么这么选、事后复盘。下次遇到类似的事，AI 会参考这里。一个决定一个文件。",
                     "decision.md", "internal", []),
}
BLANK_SUMMARY = """---
type: summary
branch: {d}
level: trunk
updated: {today}
privacy: public
---
# {d} · 总结

> 这里存什么：{what}
> 怎么存：新建文件用 `_TEMPLATES/{tpl}`，默认密级 `{priv}`（见 `_RULES/FIELD_SPEC.md`）。也可以把资料丢进 `_INBOX`，在网页“收件箱”里让它帮你归档。
> 这一页是本分支的总结，会作为摘要发给 AI，只写结论，不写细节和敏感信息。还没有内容的分支不会发出去。

## 总结
（还没有内容）
{subs}"""


def blank():
    import zipfile
    ver = (re.search(r'^VERSION = "([^"]+)"', (ROOT / "tools" / "twin_web.py").read_text(encoding="utf-8"), re.M) or [0, "dev"])[1]
    out = ROOT / "_export" / f"TWIN-空白版-{ver}.zip"
    out.parent.mkdir(exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        files = [ROOT / f for f in BLANK_FILES if (ROOT / f).exists()]
        for t in BLANK_TREES:
            files += [f for f in sorted((ROOT / t).rglob("*")) if f.is_file() and not BLANK_SKIP & set(f.relative_to(ROOT).parts)]
        for f in files:
            z.write(f, "TWIN/" + f.relative_to(ROOT).as_posix())
            n += 1
        for d in BLANK_DIRS:
            z.writestr(f"TWIN/{d}/", "")
        for d, (what, tpl, priv, subs) in BLANK_GUIDE.items():
            rows = "".join(f"| {b} | {r} | 待填写 |\n" for b, r in subs)
            z.writestr(f"TWIN/{d}/_SUMMARY.md", BLANK_SUMMARY.format(d=d, what=what, tpl=tpl, priv=priv, today=date.today().isoformat(),
                       subs=f"\n## 各分支\n| 分支 | 范围 | 状态 |\n|---|---|---|\n{rows}" if subs else ""))
            for b, _ in subs:
                z.writestr(f"TWIN/{d}/{b}/", "")
    print(f"已生成 {out.relative_to(ROOT)}（{n} 个文件，{out.stat().st_size // 1024} KB）。里面没有你的任何资料，可以直接发给别人。")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "scan":
        sys.exit(1 if scan() else 0)
    if cmd == "pack":
        sys.exit(pack())
    if cmd == "blank":
        sys.exit(blank())
    if cmd == "codescan" and len(sys.argv) > 2:
        sys.exit(1 if codescan(sys.argv[2]) else 0)
    print(__doc__)
