#!/usr/bin/env python3
"""知识库网页版（只用 Python 标准库，只在本机运行）。

用法（双击根目录的 Open_Web.bat，或在知识库根目录运行）：
  python tools/twin_web.py          打开 http://127.0.0.1:8765
  python tools/twin_web.py 9000     换一个端口

说明：
  - md 文件仍是唯一的数据源。网页只是读写这些文件，AI 照常可用。
  - 默认只监听 127.0.0.1。加 --phone 时另外监听 Tailscale 地址，只有登录你 Tailscale 账号的手机能连。
  - 第一次打开时设置访问密码。密码只存加盐哈希（tools/.auth.json，不进 Git）。
    忘记密码：删掉 tools/.auth.json 再打开，就会重新设置。
  - 30 分钟不操作自动锁定。连续输错 5 次，锁定 1 分钟。
  - 保存时会检查文件是否在别处被改过，改过就拒绝覆盖。
"""
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import contextlib
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
AUTH_FILE = TOOLS / ".auth.json"
SKIP = {".git", ".obsidian", "node_modules", "__pycache__", "_VAULT", ".trash", ".history"}
LOCK_CHOICES = (5, 15, 30, 60)  # 多久没操作就锁（分钟），最长 1 小时
GRACE = 30  # 服务器这边多等 30 秒：网页按真实的最后操作时间先锁，服务器只是兜底
ITERATIONS = 240_000
sys.path.insert(0, str(TOOLS))
from twin import PROJECTS, SKIP_SUBDIRS, project_dirs, privacy_of, walk_md  # noqa: E402
import twin_ai  # noqa: E402
import twin_health  # noqa: E402
import twin_hist  # noqa: E402
import twin_inbox  # noqa: E402
import twin_update  # noqa: E402
import twin_plugins  # noqa: E402
import twin_cards  # noqa: E402
from twin_search import INDEX  # noqa: E402

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
PHONE = {"on": False}
SESSIONS = {}  # token -> 到期时间：最后一次操作 + 设的分钟数（网页有人在用时会来续，后台自己发的请求不算）
FAILS = {"count": 0, "until": 0.0}
LOCK = threading.Lock()
# 写文件的请求一个一个来：两个改动同时读同一个文件再各写各的，后写的会把先写的冲掉，撤销也会对不上。
# 要等 AI 的（简报、建议、要闻、周报等）不排队，免得点个勾要等 AI 写完
WRITE_LOCK = threading.RLock()
SLOW_WRITES = {"/api/brief", "/api/suggest", "/api/news", "/api/weekly", "/api/weather/tips", "/api/upgrade/apply"}


# ---------- 密码 ----------
def auth_configured():
    return AUTH_FILE.exists()


def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()


def _auth():
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_password(password):
    salt = secrets.token_hex(16)
    AUTH_FILE.write_text(json.dumps({**_auth(), "salt": salt, "hash": hash_pw(password, salt),
                                     "iterations": ITERATIONS}), encoding="utf-8")


def lock_min():
    """多久没操作就自动锁定（分钟），默认 30；以前存过的更长的或“不自动锁”按 60 算。"""
    m = int(_auth().get("lock_min", 30))
    return m if m in LOCK_CHOICES else 60


def expiry():
    return time.time() + lock_min() * 60 + GRACE


def set_lock_min(m):
    if m not in LOCK_CHOICES:
        raise RuntimeError("没有这个选项。")
    AUTH_FILE.write_text(json.dumps({**_auth(), "lock_min": m}), encoding="utf-8")


def check_password(password):
    try:
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return hmac.compare_digest(hash_pw(password, data["salt"]), data["hash"])


def new_session():
    token = secrets.token_urlsafe(32)
    with LOCK:
        SESSIONS[token] = expiry()
    return token


# ---------- 文件 ----------
def safe_path(rel):
    """把网页传来的相对路径转成知识库内的 md 文件，越界返回 None。"""
    if not rel:
        return None
    p = (ROOT / rel).resolve()
    if p.suffix.lower() != ".md" or ROOT not in p.parents:
        return None
    if SKIP & set(p.relative_to(ROOT).parts):
        return None
    return p


def title_of(text, fallback):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


TREE_CACHE = {"t": 0.0, "items": []}


def tree(fresh=False):
    """资料库目录。项目库（diy_mk 这类）只列总索引和每个项目的说明、板块、文档，不进源码目录。结果缓存 20 秒，写文件后会清掉。"""
    if not fresh and time.time() - TREE_CACHE["t"] < 20:
        return TREE_CACHE["items"]
    items = []
    paths = walk_md(ROOT, SKIP_SUBDIRS | {"tools"})
    for lib in SKIP_SUBDIRS:  # 项目库的总索引
        paths += list(PROJECTS.glob(f"{lib}/*.md"))
    for d in project_dirs():  # 每个项目只看说明、板块和文档，不进源码目录，所以不慢
        paths += [*d.glob("*.md"), *d.glob("[0-9][0-9]_docs/*.md")]
    for p in sorted(set(paths)):
        rel = p.relative_to(ROOT)
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                text = fh.read(3000)  # 标题和隐私级别都在开头，不用读全文
        except OSError:
            continue
        items.append({"path": rel.as_posix(), "title": title_of(text, p.stem),
                      "privacy": privacy_of(text) or ("internal" if SKIP_SUBDIRS & set(rel.parts) else "secret")})
    TREE_CACHE.update(t=time.time(), items=items)
    return items


def search(q):
    """按相关度排序（本地 BM25），不只是“包含这几个字”。"""
    meta = {it["path"]: it for it in tree()}
    return [{**meta[r["path"]], "snippet": r["snippet"]} for r in INDEX.search(q, list(meta.values())) if r["path"] in meta]


def run_tool(cmd):
    if cmd not in ("scan", "pack"):
        return "未知命令"
    # Windows 下子进程默认按 GBK 输出，这里强制 UTF-8，否则网页上显示乱码
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(TOOLS / "twin.py"), cmd], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout + r.stderr).strip()


def scan_external():
    """把在网页以外改过的文件（Obsidian、记事本、Claude 直接改的）记进改动历史。"""
    try:
        with WRITE_LOCK:  # 网页正在写的那一刻不扫，免得把写了一半的当成“在别处改了”
            if twin_hist.scan([it["path"] for it in tree()]):
                TREE_CACHE["t"] = 0
    except OSError:
        pass


def scan_loop():
    while True:
        scan_external()
        time.sleep(120)


def home():
    """首页数据，加上体检、暂存箱、周报。新的一周第一次打开时，自动生成上周周报（本地统计）。"""
    h = twin_ai.home()
    items = tree()
    health = twin_health.check(items, twin_inbox.count())
    try:
        with twin_hist.group("自动生成上周周报", "系统"):
            made = twin_ai.ensure_weekly(health)
    except Exception:  # noqa: BLE001  周报生成失败不影响首页
        made = ""
    h.update(health={k: health[k] for k in ("red", "amber", "grey")}, inbox=twin_inbox.count(),
             weekly=twin_ai.latest_weekly(), weekly_new=bool(made))
    return h


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8", cookie=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, name):
        """网页文件：没改过就回 304（浏览器用自己存的那份），改过才重新发；支持 gzip，手机远程打开更快。"""
        f = WEB / name
        st = f.stat()
        tag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
        if self.headers.get("If-None-Match") == tag:
            self.send_response(304)
            self.send_header("ETag", tag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        data = STATIC_GZ.get(tag) if "gzip" in (self.headers.get("Accept-Encoding") or "") else None
        if data is None and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            data = STATIC_GZ[tag] = gzip.compress(f.read_bytes(), 6)
        self.send_response(200)
        self.send_header("Content-Type", STATIC[name])
        self.send_header("Cache-Control", "no-cache")  # 每次都问一下有没有改，改完刷新就能看到新版
        self.send_header("ETag", tag)
        if data is not None:
            self.send_header("Content-Encoding", "gzip")
        else:
            data = f.read_bytes()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def host_ok(self):
        # 防止其他网站借 DNS 重绑定访问本机服务
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ALLOWED_HOSTS or (PHONE["on"] and host.endswith(".ts.net"))

    def cookie(self, name):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return ""

    def token(self):
        return self.cookie("twin_session")

    def logged_in(self):
        now = time.time()
        with LOCK:
            s = SESSIONS.get(self.token())
            if not s or now > s:
                SESSIONS.pop(self.token(), None)
                return False
            return True

    def do_GET(self):
        twin_ai.LANG.v = self.cookie("twin_lang")
        if not self.host_ok():
            return self.send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path == "/":
            if not auth_configured():
                return self.send(200, gate_page("setup").encode(), "text/html; charset=utf-8")
            if not self.logged_in():
                return self.send(200, gate_page("login").encode(), "text/html; charset=utf-8")
            return self.send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path == "/manifest.json":
            return self.send(200, MANIFEST, "application/manifest+json")
        if u.path == "/icon.svg":
            return self.send(200, ICON.encode(), "image/svg+xml")
        if not self.logged_in():
            return self.send(401, {"error": "已锁定，请重新输入密码"})
        if u.path == "/api/tree":
            return self.send(200, tree())
        if u.path == "/api/file":
            p = safe_path(qs.get("path", [""])[0])
            if not p or not p.exists():
                return self.send(404, {"error": "文件不存在"})
            return self.send(200, {"text": p.read_bytes().decode("utf-8", "replace"),
                                   "mtime": str(p.stat().st_mtime_ns)})
        if u.path == "/api/search":
            return self.send(200, search(qs.get("q", [""])[0]))
        if u.path == "/api/ai/config":
            return self.send(200, twin_ai.public_config())
        if u.path == "/api/home":
            return self.send(200, home())
        if u.path == "/api/news":
            return self.send(200, twin_ai.news_today(qs.get("date", [""])[0]))
        if u.path == "/api/news/starred":
            return self.send(200, {"starred": twin_ai.news_starred()})
        if u.path == "/api/home/links":
            return self.send(200, {"links": twin_ai.home_links()})
        if u.path == "/api/home/icon":
            # 首页图标的 SVG（存进来时已经清理过）。另加一层 CSP，就算直接打开也跑不了脚本
            try:
                f = twin_ai.icon_file(twin_ai._icon_host("https://" + (parse_qs(u.query).get("h") or [""])[0]))
            except RuntimeError:
                f = None
            if not f or not f.exists():
                return self.send(404, {"error": "没有这个图标"})
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.send_header("Cache-Control", "max-age=86400")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/api/profile":
            return self.send(200, twin_ai.profile())
        if u.path == "/api/lock":  # 自动锁定：设的分钟数、还剩几秒（网页按这个提前提醒、到点锁）
            return self.send(200, {"min": lock_min(), "left": max(0, int(SESSIONS.get(self.token(), 0) - time.time() - GRACE))})
        if u.path == "/api/geocode":
            try:
                return self.send(200, {"results": twin_ai.geocode(parse_qs(u.query).get("q", [""])[0])})
            except Exception:
                return self.send(200, {"results": [], "error": "查不到，检查一下网络，或者先跳过、以后在 _RULES/Weather_Rhythm.md 里填"})
        if u.path == "/api/weather":
            try:
                return self.send(200, {"weather": twin_ai.weather(), "rhythm": twin_ai.rhythm()})
            except RuntimeError as e:
                return self.send(200, {"weather": None, "error": str(e), "rhythm": twin_ai.rhythm()})
        if u.path == "/api/rhythm":
            return self.send(200, twin_ai.rhythm())
        if u.path == "/api/version":
            return self.send(200, {"version": VERSION})
        if u.path == "/api/ideas":
            return self.send(200, twin_ai.ideas())
        if u.path == "/api/project/parents":
            return self.send(200, twin_ai.project_parents())
        if u.path == "/api/projects":  # 项目库：所有项目，有板块的点开是待办，没有的点开是说明
            return self.send(200, [{"name": d.name, "group": "/".join(d.relative_to(PROJECTS).parts[:-1]), "board": (d / "board.md").exists(),
                                    "path": (d / ("board.md" if (d / "board.md").exists() else "index.md")).relative_to(ROOT).as_posix()} for d in project_dirs() if d != twin_ai.LOOSE.parent])
        if u.path == "/api/update":
            return self.send(200, twin_update.check(VERSION, qs.get("force", [""])[0] == "1"))
        if u.path == "/api/related":
            return self.send(200, INDEX.related(qs.get("path", [""])[0], tree()))
        if u.path == "/api/health":
            return self.send(200, twin_health.check(tree(), twin_inbox.count(), fresh=True))
        if u.path == "/api/history":
            scan_external()
            return self.send(200, twin_hist.entries())
        if u.path == "/api/history/diff":
            try:
                return self.send(200, twin_hist.diff(qs.get("id", [""])[0]))
            except RuntimeError as e:
                return self.send(404, {"error": str(e)})
        if u.path == "/api/cards":
            return self.send(*self.result_get(lambda: twin_cards.items(qs.get("kind", [""])[0])))
        if u.path == "/api/inbox":
            return self.send(200, {"items": twin_inbox.items(), "targets": twin_inbox.targets()})
        if u.path == "/api/board":
            try:
                return self.send(200, twin_ai.board(qs.get("path", [""])[0]))
            except RuntimeError as e:
                return self.send(404, {"error": str(e)})
        if u.path.startswith("/static/") and u.path[8:] in STATIC:
            return self.send_static(u.path[8:])
        if u.path == "/api/plugins":
            return self.send(200, twin_plugins.listing())
        if u.path.startswith("/plugin/") and u.path.endswith(".js"):  # 开着的插件的网页脚本
            js = twin_plugins.script(u.path[8:-3])
            return self.send(200, js, "application/javascript; charset=utf-8") if js else self.send(404, {"error": "not found"})
        if u.path.startswith("/api/p/"):
            return self.send(*self.result_get(lambda: twin_plugins.handle("get", u.path, {k: v[0] for k, v in qs.items()})))
        if u.path == "/api/chats":
            return self.send(200, list_chats())
        if u.path == "/api/chat":
            f = chat_file(qs.get("id", [""])[0])
            if not f or not f.exists():
                return self.send(404, {"error": "这段对话不存在了"})
            return self.send(200, json.loads(f.read_text(encoding="utf-8")))
        self.send(404, {"error": "not found"})

    def do_POST(self):
        twin_ai.LANG.v = self.cookie("twin_lang")
        # 自定义请求头只有本页面能带上，其他网站发不出这个请求
        if not self.host_ok() or self.headers.get("X-Twin") != "1":
            return self.send(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad json"})
        path = urlparse(self.path).path
        cookie_tpl = "twin_session={}; HttpOnly; SameSite=Strict; Path=/"

        if path == "/api/setup":
            if auth_configured():
                return self.send(403, {"error": "密码已经设置过了"})
            pw = body.get("password", "")
            if len(pw) < 8:
                return self.send(400, {"error": "密码至少 8 位"})
            set_password(pw)
            return self.send(200, {"ok": True}, cookie=cookie_tpl.format(new_session()))

        if path == "/api/login":
            now = time.time()
            if now < FAILS["until"]:
                return self.send(429, {"error": f"输错次数太多，请 {int(FAILS['until'] - now) + 1} 秒后再试"})
            if not check_password(body.get("password", "")):
                FAILS["count"] += 1
                if FAILS["count"] >= 5:
                    FAILS["count"], FAILS["until"] = 0, now + 60
                    return self.send(429, {"error": "连续输错 5 次，锁定 1 分钟"})
                return self.send(401, {"error": f"密码不对，还可以再试 {5 - FAILS['count']} 次"})
            FAILS["count"] = 0
            return self.send(200, {"ok": True}, cookie=cookie_tpl.format(new_session()))

        if path == "/api/logout":
            with LOCK:
                SESSIONS.pop(self.token(), None)
            return self.send(200, {"ok": True}, cookie="twin_session=; Max-Age=0; Path=/")

        if not self.logged_in():
            return self.send(401, {"error": "已锁定，请重新输入密码"})

        if path == "/api/password":
            if not check_password(body.get("old", "")):
                return self.send(401, {"error": "原密码不对"})
            if len(body.get("new", "")) < 8:
                return self.send(400, {"error": "新密码至少 8 位"})
            set_password(body["new"])
            with LOCK:
                SESSIONS.clear()
            return self.send(200, {"ok": True}, cookie=cookie_tpl.format(new_session()))
        if path in ("/api/lock", "/api/lock/touch"):  # 改自动锁定时间 / 网页上有人在操作：都从现在重新算
            if path == "/api/lock":
                set_lock_min(int(body.get("min", 30)))
            with LOCK:
                SESSIONS[self.token()] = expiry()
            return self.send(200, {"min": lock_min(), "left": lock_min() * 60})
        if path == "/api/ask/stream":
            return self.stream(twin_ai.ask_stream(body.get("messages", []), body.get("provider_id") or None, str(body.get("project") or "")))
        label, source = MUTATING.get(path, (None, None))
        if label is None:
            return self.send(*self.result(path, body))  # pyright: ignore[reportArgumentType]  # result 总是 (状态码, 内容)
        if path in ("/api/action", "/api/actions"):
            source = "AI" if body.get("via") == "ai" else "手动"
        with (contextlib.nullcontext() if path in SLOW_WRITES else WRITE_LOCK):
            scan_external()  # 先把别处的改动记下来，免得混进这次
            with twin_hist.group(label, source or "手动") as g:
                code, payload = self.result(path, body)
        TREE_CACHE["t"] = 0
        twin_health.clear()
        if code == 200 and g["id"] and isinstance(payload, dict):
            payload = {**payload, "undo_id": g["id"], "undo_label": g["label"]}
        return self.send(code, payload)

    def stream(self, gen):
        """逐字显示：一条条 “data: {json}” 推给网页，出错时推一条 error。"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        try:
            for ev in gen:
                self.wfile.write(b"data: " + json.dumps(ev, ensure_ascii=False).encode() + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return  # 网页那边关掉了
        except Exception as e:  # noqa: BLE001
            msg = str(e) if isinstance(e, RuntimeError) else f"出错了：{e}"
            try:
                self.wfile.write(b"data: " + json.dumps({"error": msg}, ensure_ascii=False).encode() + b"\n\n")
            except OSError:
                pass

    def result_get(self, fn):
        try:
            return 200, fn()
        except RuntimeError as e:
            return 400, {"error": str(e)}

    def result(self, path, body):
        """处理写操作以外的部分也走这里。返回 (状态码, 内容)。"""
        try:
            return self.post_result(path, body)
        except RuntimeError as e:
            return 400, {"error": str(e)}
        except Exception as e:  # AI 返回格式异常等，别让网页一直转圈
            return 500, {"error": f"出错了：{e}"}

    def post_result(self, path, body):
        pid = body.get("provider_id")
        if path == "/api/file":
            p = safe_path(body.get("path", ""))
            if not p:
                return 400, {"error": "路径不允许（只能是知识库里的 .md 文件）"}
            if p.exists():
                if str(body.get("mtime")) != str(p.stat().st_mtime_ns):
                    return 409, {"error": "文件在别处被改过，请刷新后再改"}
            elif not body.get("create"):
                return 404, {"error": "文件不存在"}
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body.get("text", "").replace("\r\n", "\n").encode("utf-8"))
            twin_hist.set_label(("新建 " if body.get("create") else "编辑 ") + p.relative_to(ROOT).as_posix())
            return 200, {"mtime": str(p.stat().st_mtime_ns)}
        if path == "/api/update/apply":
            return 200, twin_update.apply(VERSION)
        if path == "/api/update/local":
            return 200, twin_update.apply_local(body.get("name", ""), body.get("data", ""), VERSION)
        if path == "/api/run":
            return 200, {"output": run_tool(body.get("cmd", ""))}
        if path == "/api/ai/config":
            return 200, twin_ai.update_config(body)
        if path == "/api/ai/test":
            p = twin_ai.active_provider(pid)
            answer = twin_ai.call_model("你是连接测试。", [{"role": "user", "content": "只回复“连接正常”四个字。"}], p, 20)
            return 200, {"answer": answer.strip()[:60]}
        if path == "/api/ask":
            return 200, twin_ai.ask(body.get("messages", []), pid, str(body.get("project") or ""))
        if path == "/api/actions":  # 预览里一键应用：一条条按顺序写，算一条改动记录，一次就能撤销
            out = []
            for a in body.get("actions", [])[:40]:
                try:
                    out.append({"ok": True, "message": twin_ai.apply_action(a)})
                except (RuntimeError, ValueError, KeyError, OSError) as e:
                    out.append({"ok": False, "error": str(e)})
            n = sum(x["ok"] for x in out)
            twin_hist.set_label(f"AI 改动 {n} 处：" + "；".join(x["message"] for x in out if x["ok"])[:100])
            return 200, {"results": out}
        if path == "/api/board/find":
            try:
                rel, _ = twin_ai._find_board(body.get("project", ""))
                return 200, twin_ai.board(rel)
            except RuntimeError as e:
                return 200, {"error": str(e)}
        if path == "/api/action":
            msg = twin_ai.apply_action(body.get("action", {}))
            twin_hist.set_label(msg)
            return 200, {"message": msg}
        if path == "/api/chat/save":
            return 200, save_chat(body)
        if path == "/api/project/delete":
            return 200, delete_project(str(body.get("path", "")))
        if path == "/api/chat/title":
            return 200, {"title": twin_ai.chat_title(body.get("messages", []), body.get("provider_id") or None)}
        if path == "/api/chat/retitle":
            return 200, retitle_chat(body.get("id", ""), pid)
        if path == "/api/home/links":
            msg = twin_ai.edit_home_links(body.get("action", ""), body.get("name", ""), body.get("url", ""), int(body.get("i", -1)), int(body.get("to", -1)), body.get("layout"))
            twin_hist.set_label(msg)
            return 200, {"message": msg, "links": twin_ai.home_links()}
        if path == "/api/chat/rename":
            return 200, rename_chat(body.get("id", ""), body.get("title", ""))
        if path == "/api/chat/delete":
            f = chat_file(body.get("id", ""))
            if f and f.exists():
                f.unlink()
            return 200, {"ok": True}
        if path == "/api/export":
            return 200, {"text": twin_ai.export_text(body.get("question", ""))}
        if path == "/api/feedback":
            twin_ai.add_feedback(bool(body.get("useful")), body.get("question", ""), body.get("note", ""))
            return 200, {"ok": True}
        if path == "/api/job/score":
            return 200, twin_ai.local_score(body.get("job", {}))
        if path == "/api/job/ai":
            job = body.get("job", {})
            local = twin_ai.local_score(job)
            return 200, {"local": local, **twin_ai.ai_opinion(job, local, pid)}
        if path == "/api/job/save":
            job = body.get("job", {})
            path_ = twin_ai.save_job_decision(job, twin_ai.local_score(job), body.get("opinion"))
            return 200, {"path": path_}
        if path == "/api/brief":
            return 200, {"brief": twin_ai.make_brief(pid)}
        if path == "/api/suggest":
            return 200, twin_ai.make_suggest(pid)
        if path == "/api/suggest/mark":
            msg = twin_ai.mark_suggest(body.get("date", ""), int(body.get("i", -1)), "adopted" if body.get("adopt") else "skipped")
            twin_hist.set_label(msg)
            return 200, {"message": msg}
        if path == "/api/news":
            return 200, {**twin_ai.make_news(pid), **{k: v for k, v in twin_ai.news_today().items() if k in ("days", "starred")}}
        if path == "/api/news/star":
            return 200, twin_ai.news_star(str(body.get("date", "")), str(body.get("link", "")), bool(body.get("on")))
        if path == "/api/home/icon":
            # action: draw（让 AI 画）/ paste（粘贴 SVG 代码）/ reset（删掉，回到网站自己的图标）
            act, url = body.get("action", ""), str(body.get("url", ""))
            if act == "auto":  # 先找现成的 SVG，找不到且接了 AI 就让 AI 画
                out = twin_ai.find_icon(body.get("name", ""), url)
                if not out:
                    if not twin_ai.public_config().get("providers"):
                        raise RuntimeError("没找到现成的 SVG 图标。接入 AI 后可以让 AI 画，或者粘贴一个 SVG。")
                    out = {**twin_ai.draw_icon(body.get("name", ""), url, body.get("hint", ""), pid), "source": "没找到现成的，AI 画的"}
                twin_hist.set_label(f"首页图标：{out['source']}（{out['host']}）")
            elif act == "draw":
                out = {**twin_ai.draw_icon(body.get("name", ""), url, body.get("hint", ""), pid), "source": "AI 画的"}
                twin_hist.set_label(f"首页图标：AI 画了 {out['host']}")
            elif act == "paste":
                out = {"host": twin_ai.save_icon(url, body.get("svg", ""))}
                twin_hist.set_label(f"首页图标：换成自己的 SVG（{out['host']}）")
            elif act == "reset":
                f = twin_ai.icon_file(twin_ai._icon_host(url))
                if f.exists():
                    f.unlink()
                out = {"host": twin_ai._icon_host(url)}
                twin_hist.set_label(f"首页图标：恢复网站自己的图标（{out['host']}）")
            else:
                raise RuntimeError("不认识的操作。")
            return 200, {**out, "links": twin_ai.home_links()}
        if path == "/api/profile":
            return 200, twin_ai.save_profile(body.get("name", ""), body.get("place"), body.get("preset", ""), body.get("portrait"))
        if path == "/api/weather/tips":
            return 200, twin_ai.weather_tips(pid)
        if path == "/api/weekly":
            rel = twin_ai.make_weekly(twin_health.check(tree()), bool(body.get("ai")), pid)
            return 200, {"path": rel}
        if path == "/api/review":
            return 200, {"path": twin_ai.review_decision(body.get("path", ""), body.get("chosen", ""),
                                                          body.get("outcome", ""), body.get("who_right", ""))}
        if path == "/api/upgrade/preview":
            return 200, {"text": twin_ai.upgrade_payload()}
        if path == "/api/upgrade/run":
            return 200, twin_ai.upgrade_run(pid)
        if path == "/api/upgrade/apply":
            return 200, twin_ai.upgrade_apply(body.get("lessons", []), body.get("changes", []),
                                              body.get("removes", []), body.get("summary", ""))
        if path == "/api/history/undo":
            try:
                r = twin_hist.undo(str(body.get("id", "")), bool(body.get("force")))
            except RuntimeError as e:
                if str(e).startswith("CHANGED:"):
                    return 409, {"error": "这些文件在那之后又被改过：" + str(e)[8:], "changed": True}
                raise
            TREE_CACHE["t"] = 0
            twin_health.clear()
            return 200, r
        if path == "/api/health/ignore":
            twin_health.set_ignore(str(body.get("key", "")), bool(body.get("on", True)))
            return 200, {"ok": True}
        if path == "/api/inbox/note":
            return 200, twin_inbox.add_note(body.get("text", ""), body.get("title", ""))
        if path == "/api/inbox/upload":
            return 200, twin_inbox.upload(body.get("name", ""), body.get("data", ""))
        if path == "/api/inbox/move":
            return 200, twin_inbox.move(body.get("name", ""), body.get("dest", ""), body.get("new_name", ""), body.get("new_dir", ""))
        if path == "/api/inbox/delete":
            return 200, twin_inbox.delete(body.get("name", ""))
        if path == "/api/cards/save":
            return 200, twin_cards.save(body.get("kind", ""), body.get("path", ""), body.get("fields", {}), body.get("body"))
        if path == "/api/cards/log":
            return 200, twin_cards.add_log(body.get("kind", ""), body.get("path", ""), body.get("text", ""))
        if path == "/api/cards/delete":
            return 200, twin_cards.delete(body.get("kind", ""), body.get("path", ""))
        if path == "/api/cards/import":
            return 200, twin_cards.import_assets()
        if path == "/api/inbox/suggest":
            return 200, twin_inbox.suggest(body.get("name", ""), body.get("note", ""), pid)
        if path == "/api/plugins":
            return 200, twin_plugins.set_enabled(body.get("id", ""), bool(body.get("on")))
        if path == "/api/plugins/remove":
            return 200, twin_plugins.remove(body.get("id", ""))
        if path == "/api/plugins/install":
            return 200, twin_plugins.install(body.get("name", ""), body.get("data", ""))
        if path.startswith("/api/p/"):
            return 200, twin_plugins.handle("post", path, body)
        return 404, {"error": "not found"}


# 会写文件的请求：每次都记进改动历史（标签会被具体内容替换），可以撤销
MUTATING = {"/api/file": ("编辑文件", "手动"), "/api/action": ("改动", "手动"), "/api/actions": ("改动", "AI"), "/api/review": ("回看决定", "手动"),
            "/api/upgrade/apply": ("复盘升级", "手动"), "/api/brief": ("生成今日简报", "系统"), "/api/suggest": ("生成今日建议", "系统"),
            "/api/suggest/mark": ("采纳建议", "手动"), "/api/news": ("生成今日要闻", "系统"), "/api/news/star": ("收藏要闻", "手动"), "/api/home/links": ("首页网站", "手动"), "/api/weather/tips": ("天气提醒", "系统"), "/api/profile": ("个人设置", "手动"), "/api/home/icon": ("首页图标", "手动"),
            "/api/weekly": ("生成周报", "系统"), "/api/job/save": ("存接单决策", "手动"),
            "/api/feedback": ("记录回答反馈", "手动"), "/api/inbox/note": ("暂存箱", "手动"),
            "/api/inbox/upload": ("暂存箱", "手动"), "/api/inbox/move": ("归档", "手动"),
            "/api/inbox/delete": ("暂存箱", "手动"), "/api/cards/save": ("卡片", "手动"),
            "/api/cards/log": ("卡片", "手动"), "/api/cards/delete": ("卡片", "手动"), "/api/cards/import": ("导入资产", "手动"), "/api/project/delete": ("删除项目", "手动")}

# ---------- 页面 ----------
# 设计：左侧深林绿的“树干”导航，右侧浅色纸面阅读区；绿色只用于强调，状态用红黄灰药丸表示。
STYLE = r"""
:root{
  --ground:#f6f6f5; --paper:#ffffff; --ink:#1b1b1a; --ink-2:#55554f; --ink-3:#8d8d88;
  --rule:#e4e4e0; --accent:#1b1b1a; --on-accent:#ffffff; --p0:#c2412d;
  --f-body:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-mode=light]){
  --ground:#18191b; --paper:#232427; --ink:#e6e6e3; --ink-2:#b2b3b0; --ink-3:#7d7f7c;
  --rule:#33363a; --accent:#e6e6e3; --on-accent:#18191b; --p0:#ec7a66; color-scheme:dark}}
:root[data-mode=dark]{
  --ground:#18191b; --paper:#232427; --ink:#e6e6e3; --ink-2:#b2b3b0; --ink-3:#7d7f7c;
  --rule:#33363a; --accent:#e6e6e3; --on-accent:#18191b; --p0:#ec7a66; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.7 var(--f-body);-webkit-font-smoothing:antialiased}
button,input,select,textarea{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""

GATE = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TWIN</title><link rel="icon" href="/icon.svg" type="image/svg+xml">
<script>try{var m=localStorage.getItem('twin.mode');if(m==='dark'||m==='light')document.documentElement.dataset.mode=m}catch(e){}</script>
<style>__STYLE__
body{display:grid;place-items:center;min-height:100vh;padding:16px}
.card{width:100%;max-width:360px;background:var(--paper);border:1px solid var(--rule);border-radius:14px;padding:32px 28px 24px}
h1{font-size:22px;line-height:1.3;margin:0 0 6px}
p{margin:0 0 22px;color:var(--ink-2);font-size:14px}
label{display:block;font-size:12px;color:var(--ink-3);letter-spacing:.06em;margin:0 0 6px}
input{width:100%;padding:11px 12px;border:1px solid var(--rule);border-radius:8px;background:var(--ground);margin-bottom:14px;font-size:15px}
input:focus{border-color:var(--ink-3);outline:none}
button{width:100%;padding:11px;border:0;border-radius:8px;background:var(--accent);color:var(--on-accent);font-weight:600;cursor:pointer;margin-top:4px}
button:disabled{opacity:.6}
.err{color:var(--p0);font-size:13px;min-height:20px;margin-top:10px}
.foot{margin-top:18px;font-size:12px;color:var(--ink-3);line-height:1.6}
</style></head><body>
<form class="card" id="f" autocomplete="off">
<h1>__TITLE__</h1><p>__HINT__</p>
<label for="pw">密码</label><input id="pw" type="password" autofocus required>
__CONFIRM__
<button id="btn">__BTN__</button><div class="err" id="err"></div>
<div class="foot">__FOOT__</div></form>
<script>
const mode='__MODE__';
document.getElementById('f').onsubmit=async e=>{e.preventDefault();
  const pw=document.getElementById('pw').value,err=document.getElementById('err'),btn=document.getElementById('btn');
  if(mode==='setup'){if(pw.length<8)return err.textContent='密码至少 8 位';
    if(pw!==document.getElementById('pw2').value)return err.textContent='两次输入的密码不一样'}
  btn.disabled=true;err.textContent='';
  const r=await fetch('/api/'+mode,{method:'POST',headers:{'Content-Type':'application/json','X-Twin':'1'},body:JSON.stringify({password:pw})});
  const j=await r.json();btn.disabled=false;if(r.ok)location.reload();else err.textContent=j.error}
</script></body></html>"""


def gate_page(mode):
    if mode == "setup":
        parts = {"__TITLE__": "设置访问密码", "__HINT__": "第一次打开。以后每次进入、或 30 分钟没操作后，都要输入这个密码。",
                 "__CONFIRM__": '<label for="pw2">再输一遍</label><input id="pw2" type="password" required>',
                 "__BTN__": "设置并进入",
                 "__FOOT__": "至少 8 位。密码只保存加盐哈希，不保存原文。忘记了就删掉 tools\\.auth.json 重新设置。"}
    else:
        parts = {"__TITLE__": "TWIN 已锁定", "__HINT__": "输入密码继续。", "__CONFIRM__": "",
                 "__BTN__": "解锁", "__FOOT__": "连续输错 5 次会锁定 1 分钟。"}
    html = GATE.replace("__STYLE__", STYLE).replace("__MODE__", mode)
    for k, v in parts.items():
        html = html.replace(k, v)
    return html


WEB = TOOLS / "web"
STATIC_GZ = {}  # 压缩过的网页文件，按版本记住
# 前端 JS：app.js 是基础，其余按页面分开（index.html 里按顺序加载）
STATIC = {**{f"{n}.js": "application/javascript; charset=utf-8" for n in ("i18n", "en", "app", "chat", "day", "home", "todo", "pages", "ui", "preact-htm")},
          "app.css": "text/css; charset=utf-8"}
MANIFEST = {"name": "TWIN", "short_name": "TWIN", "start_url": "/", "display": "standalone",
            "background_color": "#ffffff", "theme_color": "#ffffff",
            "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]}
ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1b1b1a"/>'
        '<text x="32" y="45" font-family="Arial,sans-serif" font-size="38" font-weight="700" fill="#fff" text-anchor="middle">T</text></svg>')


# ---------- 版本：每次改动加一条 CHANGELOG.md；正式版之前都带 beta ----------
VERSION = "0.27.0-beta"


# ---------- 对话记录（存在知识库的 .chats/，不进 Git）----------
CHATS = ROOT / ".chats"
CHAT_ID = re.compile(r"^[0-9a-f]{16}$")


def chat_file(cid):
    return CHATS / f"{cid}.json" if CHAT_ID.match(cid or "") else None


def list_chats():
    out = []
    for f in CHATS.glob("*.json") if CHATS.exists() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": f.stem, "title": d.get("title", ""), "updated": d.get("updated", 0),
                    "project": d.get("project", ""), "auto": d.get("auto", ""), "titled": d.get("titled", ""),
                    "fresh": d.get("titled", "") == _title_mark(d), "fixed": bool(d.get("fixed")), "talked": any(m.get("role") == "assistant" for m in _sent(d))})
    return sorted(out, key=lambda c: -c["updated"])[:60]


def _sent(d):
    """真的和 AI 说过的消息（本地记账、还没回完的不算）。"""
    return [m for m in d.get("messages", []) if m.get("role") in ("user", "assistant") and not m.get("pending") and not m.get("local") and m.get("who") != "本地"]


def _title_mark(d):
    return f"n:{len(_sent(d))}"


def retitle_chat(cid, provider_id=None):
    """手动整理标题：标题整理过、之后又没聊新内容，就直接返回，不再花 token。"""
    f = chat_file(cid)
    if not f or not f.exists():
        raise RuntimeError("这段对话不存在了")
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("fixed") or d.get("titled") == _title_mark(d):
        return {"title": d.get("title", ""), "titled": d["titled"], "skipped": True}
    d["title"], d["titled"] = twin_ai.chat_title(_sent(d), provider_id), _title_mark(d)
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return {"title": d["title"], "titled": d["titled"], "skipped": False}


def rename_chat(cid, title):
    """手动改标题。算作已整理过，之后没聊新内容就不再提示用 AI 整理。"""
    f, title = chat_file(cid), str(title).strip()[:60]
    if not f or not f.exists():
        raise RuntimeError("这段对话不存在了")
    if not title:
        raise RuntimeError("标题不能空")
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("fixed"):
        raise RuntimeError("这个对话的标题是固定的，不能改")
    d["title"], d["titled"] = title, _title_mark(d)
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return {"title": title, "titled": d["titled"]}


def delete_project(rel):
    """删项目：整个文件夹（说明、板块、代码）挪到 .trash/项目/ 里，不真删；想恢复就把文件夹拖回 03_Projects。"""
    p = (ROOT / rel).resolve()
    d = p.parent if p.suffix == ".md" else p
    if d not in {x.resolve() for x in project_dirs()} or d == twin_ai.LOOSE.parent.resolve():
        raise RuntimeError("找不到这个项目。")
    dest = ROOT / ".trash" / "项目" / f"{d.name}_{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(dest))
    twin_hist.set_label(f"删除项目：{d.name}")
    return {"message": f"已删除“{d.name}”，文件夹在 {dest.relative_to(ROOT).as_posix()}，想恢复就拖回 03_Projects。"}


def save_chat(body):
    cid = body.get("id") or secrets.token_hex(8)
    f = chat_file(cid)
    if not f:
        raise RuntimeError("对话编号不对")
    CHATS.mkdir(exist_ok=True)
    try:
        old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        old = {}
    # fixed：插件建的专用对话（比如“雅思答疑”），标题固定，不能改名、不让 AI 整理
    fixed = bool(body["fixed"]) if "fixed" in body else bool(old.get("fixed"))
    data = {"id": cid, "title": str(old.get("title") if fixed and "fixed" not in body and old.get("title") else body.get("title", ""))[:60], "updated": time.time(),
            "project": str(body.get("project") or "")[:300], "auto": str(body.get("auto") or "")[:300],
            "titled": str(body.get("titled") or "")[:10], "messages": body.get("messages", [])[-200:], **({"fixed": True} if fixed else {})}
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"id": cid}


def tailscale_ip():
    """本机在 Tailscale 网络里的地址（100.x.x.x）。没装或没登录返回空。"""
    for exe in ("tailscale", r"C:\Program Files\Tailscale\tailscale.exe"):
        try:
            r = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        ip = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
        if ip.startswith("100."):
            return ip
    return ""


def main():
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    port = int(nums[0]) if nums else 8765
    twin_hist.install()
    try:
        twin_hist.prune()
    except OSError:
        pass
    threading.Thread(target=scan_loop, daemon=True).start()  # 每 2 分钟看一次有没有在别处改过的文件
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"TWIN 网页版已启动：{url}\n停止：右下角托盘图标右键“退出 TWIN”；在命令行里直接运行的，按 Ctrl+C 或关掉窗口。")
    if "--phone" in sys.argv:
        ip = tailscale_ip()
        if not ip:
            print("\n没找到 Tailscale：手机访问没有打开，电脑上照常可用。\n请先装 Tailscale 并登录（见 README 的“手机访问”）。")
        else:
            # 只监听 Tailscale 网卡：同一 Wi-Fi 的其他设备、公网都连不上，只有登录你账号的设备能连
            ALLOWED_HOSTS.add(ip)
            PHONE["on"] = True
            phone = ThreadingHTTPServer((ip, port), Handler)
            threading.Thread(target=phone.serve_forever, daemon=True).start()
            print(f"\n手机访问已打开：手机上打开 Tailscale，再用浏览器访问 http://{ip}:{port}")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
