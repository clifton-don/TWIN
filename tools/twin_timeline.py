"""项目时间线：不用你手写，从项目文件夹里已有的东西整理出“什么时候开始、每个月做了什么、做了几版”。

数据来源（都只在本机算，不发给 AI）：
  - 文件的最后修改时间和类型（代码、电路板、3D / 外壳、文档、图片、固件……）。跳过依赖、编译产物这类文件夹，最多看 20000 个文件。
  - 项目有 git 仓库的话，加上提交记录（日期 + 说明）。
  - 版本文件夹（V1_2024原版、V2_2026重做……）各自的起止时间。
注意：整个文件夹拷贝过的话，文件时间可能都挤在拷贝那一天；git 记录不受影响。
"""
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import date
from pathlib import Path

from twin import PRUNE, ROOT, project_dirs

MAX_FILES = 20000
CACHE_SECONDS = 600
# 依赖、编译产物、编辑器缓存：时间是下载 / 编译那天，不代表你在做事
SKIP_DIRS = PRUNE | {".git", ".svn", ".hg", "node_modules", ".pio", ".vscode", ".idea", "__pycache__", "build", "dist", "out",
                     "managed_components", ".cache", "venv", ".venv", "target", "obj", "bin"}
TWIN_FILES = {"board.md", "index.md"}  # TWIN 自己写的板块和说明，打勾就会改时间，不算项目进展

KINDS = {}
for _label, _exts in {
    "代码": ".c .h .cpp .hpp .cc .ino .py .js .ts .tsx .jsx .vue .java .kt .go .rs .lua .sh .cs .m .swift .rb .php .html .css .scss .json .yaml .yml .toml .cmake .s",
    "电路板": ".kicad_pcb .kicad_sch .kicad_pro .sch .brd .pcbdoc .schdoc .prjpcb .epro .eprj .lbr .dsn .net",
    "制板文件": ".gbr .gtl .gbl .gto .gbo .gts .gbs .gko .drl .xln",
    "3D / 外壳": ".step .stp .stl .3mf .f3d .f3z .sldprt .sldasm .ipt .iam .obj .fbx .blend .scad .dxf .dwg",
    "文档": ".md .txt .pdf .doc .docx .xls .xlsx .csv .ppt .pptx .tex",
    "图片 / 视频": ".png .jpg .jpeg .gif .bmp .svg .webp .heic .mp4 .mov .avi",
    "固件": ".bin .hex .elf .uf2 .img",
}.items():
    for _e in _exts.split():
        KINDS[_e] = _label

_CACHE = {}


def _project_dir(rel):
    rel = str(rel or "").replace("\\", "/").strip("/")
    if not rel or ".." in rel.split("/"):
        raise ValueError("项目路径不对。")
    p = (ROOT / rel).resolve()
    if p.is_file() or p.suffix == ".md":
        p = p.parent
    if p not in {d.resolve() for d in project_dirs()}:
        raise ValueError("这不是一个项目文件夹。")
    return p


def _scan(d):
    """[(日期, 类型, 顶层子文件夹名)]，以及有没有因为文件太多没看完。"""
    out = []
    for cur, dirs, names in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        top = Path(cur).relative_to(d).parts[0] if Path(cur) != d else ""
        for nm in names:
            if nm.startswith((".", "~$")) or (not top and nm in TWIN_FILES):
                continue
            try:
                mt = os.stat(os.path.join(cur, nm)).st_mtime
            except OSError:
                continue
            out.append((date.fromtimestamp(mt), KINDS.get(os.path.splitext(nm)[1].lower(), "其他"), top))
            if len(out) >= MAX_FILES:
                return out, True
    return out, False


def _git(d):
    """这个文件夹的 git 提交（日期, 说明），最多 500 条；没装 git、不是仓库都返回空。"""
    git = shutil.which("git")
    if not git:
        return []
    try:
        r = subprocess.run([git, "-C", str(d), "log", "--date=short", "--pretty=%ad%x09%s", "-n", "500", "--", "."],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.splitlines():
        day, _, msg = line.partition("\t")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            out.append((date.fromisoformat(day), msg.strip()[:120]))
    return out


def build(d):
    files, truncated = _scan(d)
    commits = _git(d)
    months = {}

    def month(dt):
        return months.setdefault(dt.strftime("%Y-%m"), {"files": 0, "kinds": Counter(), "commits": []})
    for dt, kind, _ in files:
        m = month(dt)
        m["files"] += 1
        m["kinds"][kind] += 1
    for dt, msg in commits:
        month(dt)["commits"].append({"date": dt.isoformat(), "msg": msg})
    versions = []
    for v in sorted(x for x in d.iterdir() if x.is_dir() and re.match(r"^V\d+[_\-]", x.name)):
        ds = [dt for dt, _, top in files if top == v.name]
        if ds:
            versions.append({"name": v.name, "from": min(ds).isoformat(), "to": max(ds).isoformat(), "files": len(ds)})
    days = [dt for dt, _, _ in files] + [dt for dt, _ in commits]
    rows = []
    for key in sorted(months):
        m = months[key]
        cs = sorted(m["commits"], key=lambda c: c["date"])
        rows.append({"month": key, "files": m["files"], "kinds": m["kinds"].most_common(3), "commits": cs[:6], "more": max(len(cs) - 6, 0)})
    return {"name": d.name, "start": min(days).isoformat() if days else "", "last": max(days).isoformat() if days else "",
            "files": len(files), "commits": len(commits), "truncated": truncated, "versions": versions, "months": rows}


def timeline(rel, fresh=False):
    d = _project_dir(rel)
    hit = _CACHE.get(d)
    if hit and not fresh and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    data = build(d)
    _CACHE[d] = (time.time(), data)
    return data
