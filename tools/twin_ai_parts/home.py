# twin_ai 的一部分：首页常用网站、网站图标、小组件。
# 不单独 import：twin_ai.py 末尾把这个文件放进它自己的命名空间里执行，和写在 twin_ai.py 里完全一样，
# 直接用那里的函数和变量（ROOT、_write、call_model……），外面照旧用 twin_ai.xxx。
# flake8: noqa

# ---------- 首页：常用网站（_RULES/Home_Links.md，一张表，网页上也能加减）----------
HOME_LINKS = ROOT / "_RULES" / "Home_Links.md"
DEFAULT_LINKS_MD = """---
type: rules
updated: {today}
privacy: public
---
# 首页常用网站

> 首页上的图标，按表里的顺序排。可以直接改这张表，也可以在首页点“添加”加、点“×”删、按住拖动换位置。
> 拖到另一个图标正中间会放进同一个文件夹，“文件夹”一列就是文件夹的名字，空着就是不放文件夹。
> 一开始只有小组件，常用网站在首页“添加”里选或者自己填。
> `twin:` 开头的是首页小组件（天气、今天、要闻等），删掉这一行就是从首页移走，在首页“添加”的“小组件”里能加回来。只放网址，不放账号密码。

| 名称 | 地址 | 文件夹 |
|---|---|---|
| 天气 | twin:weather | |
| 今天 | twin:today | |
| 要闻 | twin:news | |
| 今日建议 | twin:sug | |
"""


# 首页图标的 SVG：AI 画的或自己粘贴的，按网站域名存在 _RULES/Home_Icons/ 里；只留画图用的标签和属性，脚本、外链一律去掉
HOME_ICONS = ROOT / "_RULES" / "Home_Icons"
SVG_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "lineargradient",
            "radialgradient", "stop", "clippath", "mask", "use", "title", "text", "tspan"}
SVG_BAD_ATTR = re.compile(r"^(on|style$|xml:base)", re.I)
ICON_PROMPT = """给一个网站画首页图标，输出一个 SVG。
网站名称：{name}
网址：{url}
{site}{hint}
先回想你对这个网站的了解：它是做什么的、品牌主色、标志性的图形或 logo 长什么样；不认识就根据名称和网页信息设计一个贴切的。然后再画。
要求：
- viewBox="0 0 64 64"，不写 width 和 height；画满整个方块，背景是一个圆角矩形（rx 约 14），配色要好看、和这个网站的品牌气质相符。
- 扁平简洁，一眼能认出来；可以用网站的标志性图形、首字母或一两个汉字。
- 只用 path、circle、rect、polygon、g、linearGradient、text 这些基础元素；不要 script、image、外部链接、style 标签、动画。
- 只输出 SVG 代码本身，不要解释，不要代码块标记。"""


def _icon_host(url):
    h = urlparse(url).hostname or ""
    h = re.sub(r"^www\.", "", h.lower())
    if not re.match(r"^[a-z0-9.-]{1,100}$", h):
        raise RuntimeError("网址不对，取不到域名。")
    return h


def clean_svg(text):
    """只留安全的 SVG：解析成 XML，按白名单保留标签，去掉事件、样式和外部链接。返回整理后的 SVG 文本。"""
    import xml.etree.ElementTree as ET
    m = re.search(r"<svg[\s\S]*</svg>", str(text or ""), re.I)
    if not m:
        raise RuntimeError("里面没有找到 <svg>…</svg>。")
    src = re.sub(r"<!DOCTYPE[^>]*>|<\?xml[^>]*\?>|<!--[\s\S]*?-->", "", m.group(0))
    if len(src) > 60000:
        raise RuntimeError("这个 SVG 太大了（超过 60 KB）。")
    try:
        root = ET.fromstring(src)
    except ET.ParseError as e:
        raise RuntimeError(f"SVG 格式有问题：{e}")

    def local(t):
        return t.split("}")[-1].lower()

    def walk(el):
        for k in list(el.attrib):
            v = el.attrib[k]
            if SVG_BAD_ATTR.match(local(k)) or ("href" in k.lower() and not v.startswith("#")) or re.search(r"url\(\s*['\"]?(?!#)", v, re.I) or "javascript:" in v.lower():
                del el.attrib[k]
        for ch in list(el):
            if local(ch.tag) not in SVG_TAGS:
                el.remove(ch)
            else:
                walk(ch)
    if local(root.tag) != "svg":
        raise RuntimeError("最外层不是 <svg>。")
    walk(root)
    for k in ("width", "height"):
        root.attrib.pop(k, None)
    if "viewBox" not in root.attrib:
        root.set("viewBox", "0 0 64 64")
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    out = ET.tostring(root, encoding="unicode")
    if "xmlns=" not in out[:200]:
        out = out.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return out


def icon_file(host):
    return HOME_ICONS / f"{host}.svg"


def save_icon(url, svg):
    h = _icon_host(url)
    _write(icon_file(h), clean_svg(svg))
    return h


def _site_meta(host):
    """本机打开网站首页，取标题、简介和主题色（都是网站公开的信息），帮 AI 认出这个网站。取不到就算了。"""
    try:
        req = urllib.request.Request(f"https://{host}", headers={"User-Agent": "Mozilla/5.0 TWIN"})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read(200000).decode(r.headers.get_content_charset() or "utf-8", "ignore")
    except Exception:
        return ""
    def meta(*names):
        for n in names:
            m = re.search(r'<meta[^>]+(?:name|property)=["\']' + re.escape(n) + r'["\'][^>]*content=["\']([^"\']{1,300})', raw, re.I) \
                or re.search(r'<meta[^>]+content=["\']([^"\']{1,300})["\'][^>]*(?:name|property)=["\']' + re.escape(n) + r'["\']', raw, re.I)
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip()
        return ""
    t = re.search(r"<title[^>]*>([^<]{1,200})", raw, re.I)
    parts = [("网页标题", re.sub(r"\s+", " ", t.group(1)).strip() if t else ""), ("网页简介", meta("description", "og:description")[:200]),
             ("主题色", meta("theme-color", "msapplication-TileColor"))]
    return "".join(f"{k}：{_cell(v)}\n" for k, v in parts if v)


# ---- 先找现成的 SVG：① 网站自己在首页声明的 SVG 图标 ② Simple Icons（开源品牌图标库，CC0）；都没有再让 AI 画 ----
SI_VER = "13.21.0"
SI_MIRRORS = ["https://registry.npmmirror.com/simple-icons/{v}/files/{p}", "https://cdn.jsdelivr.net/npm/simple-icons@{v}/{p}",
              "https://unpkg.com/simple-icons@{v}/{p}"]
SI_CACHE = Path(__file__).resolve().parent / ".cache" / f"simple-icons-{SI_VER}.json"


def _get(url, limit=400000, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 TWIN"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit), r.geturl(), r.headers.get_content_charset() or "utf-8"


def _si_get(path):
    for m in SI_MIRRORS:
        try:
            return _get(m.format(v=SI_VER, p=path), 2000000)[0]
        except Exception:
            continue
    return None


def _si_slug(title):
    t = title.lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    for a, b in (("đ", "d"), ("ħ", "h"), ("ı", "i"), ("ĸ", "k"), ("ŀ", "l"), ("ł", "l"), ("ß", "ss"), ("ŧ", "t")):
        t = t.replace(a, b)
    import unicodedata
    t = unicodedata.normalize("NFD", t)
    return re.sub(r"[^a-z0-9]", "", t)


def _si_index():
    """Simple Icons 的目录（名称、颜色、官网域名），第一次用时下载一份存在 tools/.cache，之后都读本地。"""
    if SI_CACHE.exists():
        return json.loads(SI_CACHE.read_text(encoding="utf-8"))
    raw = _si_get("_data/simple-icons.json")
    if not raw:
        return []
    out = []
    for x in json.loads(raw).get("icons", []):
        names = [x["title"]] + (x.get("aliases") or {}).get("aka", []) + list(((x.get("aliases") or {}).get("loc") or {}).values())
        out.append({"slug": x.get("slug") or _si_slug(x["title"]), "hex": x.get("hex", "333333"),
                    "host": re.sub(r"^www\.", "", urlparse(x.get("source", "")).hostname or ""), "names": names})
    SI_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SI_CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _norm_name(t):
    return re.sub(r"[\s\-_.·]", "", str(t).lower())


def _si_find(name, host):
    idx = _si_index()
    n, label = _norm_name(name), host.split(".")[-2] if host.count(".") else host
    for test in (lambda x: any(_norm_name(a) == n for a in x["names"]),   # 名称对上（含中文别名，比如“小红书”）
                 lambda x: x["host"] and (host == x["host"] or host.endswith("." + x["host"])),  # 官网域名对上
                 lambda x: x["slug"] == _si_slug(label)):  # 域名主体对上，比如 bilibili.com → bilibili
        hit = next((x for x in idx if test(x)), None)
        if hit:
            return hit
    return None


def _tile(inner_svg, bg, pad=14):
    """把一个图形放进 64×64 的圆角方块里：bg 是底色，图形缩放到中间。"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(clean_svg(inner_svg))
    vb = root.get("viewBox", "0 0 24 24")
    body = "".join(ET.tostring(ch, encoding="unicode") for ch in root if not ch.tag.endswith("title"))
    body = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", body)
    s = 64 - 2 * pad
    fill = f' fill="{root.get("fill")}"' if root.get("fill") else ""
    return clean_svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{bg}"/>'
                     f'<svg x="{pad}" y="{pad}" width="{s}" height="{s}" viewBox="{vb}"{fill}>{body}</svg></svg>')


def _site_svg(host):
    """网站首页里声明的 SVG 图标（<link rel="icon" href="….svg"> 或 mask-icon）。"""
    try:
        raw, final, cs = _get(f"https://{host}", 300000, 6)
    except Exception:
        return None
    html = raw.decode(cs, "ignore")
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        rel = (re.search(r'rel=["\']([^"\']+)', tag, re.I) or [None, ""])[1].lower()
        href = (re.search(r'href=["\']([^"\']+)', tag, re.I) or [None, ""])[1]
        typ = (re.search(r'type=["\']([^"\']+)', tag, re.I) or [None, ""])[1].lower()
        if "icon" not in rel or not href or not (href.split("?")[0].lower().endswith(".svg") or "svg" in typ):
            continue
        try:
            from urllib.parse import urljoin
            svg = _get(urljoin(final, href), 200000, 6)[0].decode("utf-8", "ignore")
            color = (re.search(r'color=["\'](#[0-9a-fA-F]{3,8})', tag) or [None, ""])[1]
            if "mask-icon" in rel:  # 单色图形，按声明的颜色上色
                return _tile(svg.replace("<svg", f'<svg fill="{color or "#333"}"', 1), "#ffffff")
            return _tile(svg, "#ffffff", 10)
        except Exception:
            continue
    return None


# 国内团队的开源图标库：Remix Icon（Apache-2.0，国内品牌最全：知乎、淘宝、支付宝、微信、钉钉、豆瓣、码云……）和字节的 IconPark。
# 通过 Iconify 的公开接口取单个 SVG；接口连不上就从 npmmirror 下载整套图标存进 tools/.cache 再取
CN_SETS = [("ri", "{}-fill", "1.2.10"), ("icon-park-solid", "{}", "1.2.4"), ("icon-park-outline", "{}", "1.2.4")]
ICONIFY_HOSTS = ["https://api.iconify.design", "https://api.unisvg.com", "https://api.simplesvg.com"]
CN_ALIAS = {"知乎": "zhihu", "淘宝": "taobao", "天猫": "taobao", "支付宝": "alipay", "微信": "wechat", "微信支付": "wechat-pay", "微博": "weibo",
            "抖音": "tiktok", "钉钉": "dingding", "豆瓣": "douban", "码云": "gitee", "网易云音乐": "netease-cloud-music", "百度": "baidu",
            "百度网盘": "baidu", "b站": "bilibili", "哔哩哔哩": "bilibili", "qq": "qq", "qq邮箱": "qq", "腾讯qq": "tencent-qq"}
CN_HOSTS = {"music.163.com": "netease-cloud-music", "pan.baidu.com": "baidu", "mail.qq.com": "qq", "weixin.qq.com": "wechat",
            "tmall.com": "taobao", "dingtalk.com": "dingding", "douyin.com": "tiktok"}
CN_COLOR = {"zhihu": "#0084FF", "bilibili": "#00A1D6", "taobao": "#FF5000", "alipay": "#1677FF", "wechat": "#07C160", "wechat-pay": "#07C160",
            "weibo": "#E6162D", "tiktok": "#111111", "qq": "#12B7F5", "tencent-qq": "#12B7F5", "baidu": "#2932E1", "dingding": "#3296FA",
            "douban": "#2E963D", "gitee": "#C71D23", "netease-cloud-music": "#E60026", "github": "#181717"}


def _iconify_set(prefix, ver):
    f = SI_CACHE.parent / f"iconify-{prefix}-{ver}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    for m in ("https://registry.npmmirror.com/@iconify-json/{p}/{v}/files/icons.json", "https://cdn.jsdelivr.net/npm/@iconify-json/{p}@{v}/icons.json"):
        try:
            raw = _get(m.format(p=prefix, v=ver), 8000000, 15)[0]
            d = json.loads(raw)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            return d
        except Exception:
            continue
    return None


def _iconify_svg(prefix, name, ver):
    for h in ICONIFY_HOSTS:
        try:
            raw = _get(f"{h}/{prefix}/{name}.svg", 100000, 5)[0].decode("utf-8", "ignore")
            if raw.lstrip().startswith("<svg"):
                return raw
            if raw.strip() == "404":
                return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            continue
    d = _iconify_set(prefix, ver)  # 接口都连不上，用整套图标
    if not d:
        return None
    ic = d.get("icons", {}).get(name) or d.get("icons", {}).get((d.get("aliases", {}).get(name) or {}).get("parent", ""))
    if not ic:
        return None
    w, hh = ic.get("width", d.get("width", 24)), ic.get("height", d.get("height", 24))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {hh}">{ic["body"]}</svg>'


def _cn_find(name, host):
    keys = []
    n = _norm_name(name)
    for k, v in CN_ALIAS.items():
        if _norm_name(k) == n:
            keys.append(v)
    for k, v in CN_HOSTS.items():
        if host == k or host.endswith("." + k):
            keys.append(v)
    label = host.split(".")[-2] if host.count(".") else host
    keys += [_si_slug(name), label]
    seen = []
    for k in keys:
        k = re.sub(r"[^a-z0-9-]", "", k.lower())
        if k and k not in seen:
            seen.append(k)
    for k in seen:
        for prefix, pat, ver in CN_SETS:
            svg = _iconify_svg(prefix, pat.format(k), ver)
            if svg:
                return k, svg, prefix
    return None


def find_icon(name, url):
    """先找现成的：网站自己的 SVG → Simple Icons。找到就存下并返回 {host, svg, source}，找不到返回 None。"""
    h = _icon_host(url)
    svg = _site_svg(h)
    if svg:
        _write(icon_file(h), svg)
        return {"host": h, "svg": svg, "source": "网站自己的 SVG 图标"}
    hit = _si_find(name, h)
    if hit:
        raw = _si_get(f"icons/{hit['slug']}.svg")
        if raw:
            hx = hit["hex"]
            lum = sum(int(hx[i:i + 2], 16) * w for i, w in ((0, .299), (2, .587), (4, .114))) if len(hx) == 6 else 0
            glyph = raw.decode("utf-8", "ignore").replace("<svg", f'<svg fill="{"#1b1b1b" if lum > 186 else "#ffffff"}"', 1)
            svg = _tile(glyph, f"#{hx}")
            _write(icon_file(h), svg)
            return {"host": h, "svg": svg, "source": "Simple Icons 开源图标库"}
    hit = _cn_find(name, h)
    if hit:
        k, raw, prefix = hit
        bg = CN_COLOR.get(k)
        glyph = re.sub(r'(stroke|fill)="currentColor"', lambda m: f'{m.group(1)}="{"#ffffff" if bg else "#333333"}"', raw)
        if "currentColor" not in raw and 'fill="' not in raw[:raw.find(">")]:
            glyph = glyph.replace("<svg", f'<svg fill="{"#ffffff" if bg else "#333333"}"', 1)
        svg = _tile(glyph, bg or "#ffffff")
        _write(icon_file(h), svg)
        return {"host": h, "svg": svg, "source": "Remix Icon 开源图标库" if prefix == "ri" else "IconPark 开源图标库（字节跳动）"}
    return None


def draw_icon(name, url, hint="", provider_id=None):
    """让 AI 给网站画一个 SVG 图标。发出去的只有网站名称、网址和网站首页的公开标题 / 简介 / 主题色，手动点了才调用。"""
    h = _icon_host(url)
    text = ICON_PROMPT.format(name=_cell(name)[:20], url=f"https://{h}", site=_site_meta(h),
                              hint=f"额外要求：{_cell(hint)[:200]}\n" if str(hint or "").strip() else "")
    check_outgoing(text)
    out = call_model("你是图标设计师，只输出干净的 SVG 代码。", [{"role": "user", "content": text}], active_provider(provider_id), 3000)
    svg = clean_svg(out)
    _write(icon_file(h), svg)
    return {"host": h, "svg": svg}


# 首页小组件：表里 twin:名字 这种地址就是小组件，画法在 web/home.js 的 WIDGETS 里
_is_wid = lambda u: bool(re.match(r"^twin:[a-z0-9]+$", u or ""))


def home_links():
    """首页图标：[{name, url, folder}]。"""
    text = _rules_file(HOME_LINKS, DEFAULT_LINKS_MD)
    out = [{"name": c[0], "url": c[1], "folder": "" if _is_wid(c[1]) else (c[2] if len(c) >= 3 else "")}
           for c in _table_rows(text, "地址") if len(c) >= 2 and (re.match(r"^https?://", c[1]) or _is_wid(c[1]))]
    for x in out:  # 有自己的 SVG 图标就带上修改时间，网页用它刷新缓存
        try:
            f = icon_file(_icon_host(x["url"])) if x["url"].startswith("http") else None
            if f and f.exists():
                x["icon"] = int(f.stat().st_mtime)
        except RuntimeError:
            pass
    return out


def edit_home_links(action, name="", url="", i=-1, to=-1, layout=None):
    links = home_links()
    if action == "add" and _is_wid(url):  # 把移走的自带小组件加回来
        name = _cell(name).strip()[:20] or url[5:]
        if any(x["url"] == url for x in links):
            raise RuntimeError("这个小组件已经在首页了。")
        links.append({"name": name, "url": url, "folder": ""})
        msg = f"首页加小组件：{name}"
    elif action == "add":
        name, url = _cell(name).strip()[:20], str(url or "").strip()
        if not re.match(r"^https?://", url):
            url = "https://" + url
        if not name or not re.match(r"^https?://[^\s|]+$", url):
            raise RuntimeError("名称和网址都要填对。")
        links.append({"name": name, "url": url, "folder": ""})
        msg = f"首页加网站：{name}"
    elif action == "del" and 0 <= int(i) < len(links):
        msg = f"首页删网站：{links.pop(int(i))['name']}"
    elif action == "move" and 0 <= int(i) < len(links) and 0 <= int(to) < len(links):
        x = links.pop(int(i)); links.insert(int(to), x)
        msg = f"首页挪网站：{x['name']}"
    elif action == "layout" and isinstance(layout, list):
        # 首页拖动、建文件夹、改名、移出、删除都把整张表发回来；这里只认网址和小组件，别的丢掉
        new = []
        for x in layout[:300]:
            if not isinstance(x, dict):
                continue
            u = str(x.get("url") or "").strip()
            n = _cell(x.get("name")).strip()[:20]
            if not n or not (_is_wid(u) or re.match(r"^https?://[^\s|]+$", u)):
                continue
            new.append({"name": n, "url": u, "folder": "" if _is_wid(u) else _cell(x.get("folder")).strip()[:12]})
        if len(new) < len(links) - 1:  # 一次最多少一个（删一个），防止误把整张表清空
            raise RuntimeError("首页图标已经变了，刷新一下。")
        links = new
        msg = "首页整理图标"
    else:
        raise RuntimeError("首页图标已经变了，刷新一下。")
    text = HOME_LINKS.read_text(encoding="utf-8")
    table = "| 名称 | 地址 | 文件夹 |\n|---|---|---|\n" + "".join(f"| {x['name']} | {x['url']} | {x['folder']} |\n" for x in links)
    text = re.sub(r"\| 名称 \| 地址 \|(?: 文件夹 \|)?\n\|[-| ]+\|\n(?:\|.*\|\n?)*", table, text, count=1)
    _write(HOME_LINKS, text)
    return msg
