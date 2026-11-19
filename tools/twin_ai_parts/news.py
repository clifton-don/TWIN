# twin_ai 的一部分：每日要闻。
# 不单独 import：twin_ai.py 末尾把这个文件放进它自己的命名空间里执行，和写在 twin_ai.py 里完全一样，
# 直接用那里的函数和变量（ROOT、_write、call_model……），外面照旧用 twin_ai.xxx。
# flake8: noqa

# ---------- 每日要闻：本机从各家 RSS 取标题；AI 按“对他个人影响大不大、能不能赚钱”挑，不按领域 ----------
NEWS_DIR = BRIEFS / "News"
NEWS_SOURCES = ROOT / "_RULES" / "News_Sources.md"
NEWS_PROFILE = ROOT / "_RULES" / "News_Profile.md"
PROFILE_FILE = ROOT / "00_Crown" / "Profile.md"
DEFAULT_NEWS_MD = """---
type: rules
updated: {today}
privacy: public
---
# 每日要闻的来源

> TWIN 每天从下面这些地址取最新标题（本机直接取），再让 AI 按 [[News_Profile]] 挑出对你影响最大的几条。
> 来源越杂越好，挑的事交给 AI。想加减来源直接改这张表；连不上的来源会在要闻页底部列出来。

| 来源 | 地址 |
|---|---|
| 36氪 | https://36kr.com/feed |
| IT之家 | https://www.ithome.com/rss/ |
| 少数派 | https://sspai.com/feed |
| FT 中文网 | https://www.ftchinese.com/rss/news |
| Hacker News 热门 | https://hnrss.org/frontpage |
| TechCrunch | https://techcrunch.com/feed/ |
| Hackaday | https://hackaday.com/blog/feed/ |
| CNX Software（嵌入式） | https://www.cnx-software.com/feed/ |
| IEEE Spectrum | https://spectrum.ieee.org/feeds/feed.rss |
| MIT Technology Review | https://www.technologyreview.com/feed/ |
| Nature | https://www.nature.com/nature.rss |
| The Economist 财经 | https://www.economist.com/finance-and-economics/rss.xml |
| BBC 国际 | https://feeds.bbci.co.uk/news/world/rss.xml |
"""
DEFAULT_PROFILE_MD = """---
type: rules
updated: {today}
privacy: public
---
# 要闻怎么挑：对我影响大的才推

> 这一页会和新闻标题一起发给 AI，用来判断每条新闻对我的影响。只写方向，不写敏感信息。随时改。

## 我想看到的
- 能帮我赚钱的风口：新出现的需求、平台、补贴、比赛、外包机会，尤其是我现在的技能能接得住的
- 会影响我收入或计划的变化：政策、汇率、行业变动、平台规则
- 和我的方向直接相关的大事：（比如升学、找工作、考证，按自己的情况改）

## 我手里有什么（判断“接不接得住”用）
- （写你会的技能、在做的副业或项目，一行一条）

## 不要推
- 纯娱乐、体育、八卦；和我没关系的地方新闻
- 只是“值得了解”但对我没影响的大新闻
"""
NEWS_PROMPT = """今天是 {today}。下面是我的情况，以及今天从各家媒体取到的最新标题和摘要。
请挑出对我个人影响最大的几条（最多 8 条，宁缺毋滥；没有就少给）。影响大的意思是：能帮我赚钱的风口，或者会实实在在改变我的收入、计划、申请、项目的事。领域不限。

=== 我的情况 ===
{me}

=== 今天的新闻 ===
{items}

只依据给出的新闻内容，不要补充材料里没有的事实；对我的影响是推断，要说得具体。
只输出一个 JSON，不要别的文字：
{{"overview":"一句话：今天对我最要紧的是什么",
 "items":[{{"n":原编号,"tag":"两到四个字的标签，比如 风口、政策、行业、申请、风险","title":"中文标题，20 字以内","summary":"两句话讲清楚发生了什么","impact":"对我的影响，一两句，具体到我的哪项技能、项目或计划","action":"我可以怎么用，一句话，能马上开始的动作；没有就留空","score":1到5的整数，对我的影响因子，5 最大}}]}}
score 低于 3 的不要放进来。"""


def _rules_file(path, default):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default.format(today=today()), encoding="utf-8")
    return path.read_text(encoding="utf-8")


def news_sources():
    text = _rules_file(NEWS_SOURCES, DEFAULT_NEWS_MD)
    if "类别写 经济 / 科研 / 政治 / 科技" in text:  # 上一版自动生成、没改过的来源表，换成新的
        NEWS_SOURCES.write_text(DEFAULT_NEWS_MD.format(today=today()), encoding="utf-8")
        text = NEWS_SOURCES.read_text(encoding="utf-8")
    return [{"name": c[0], "url": next(x for x in c if x.startswith("http"))}
            for c in _table_rows(text, "地址") if any(x.startswith("http") for x in c)]


def news_me():
    """发给 AI 的“我的情况”：一页纸画像 + 要闻挑选规则，都是公开层，去掉私密段落。"""
    parts = []
    for f, default in ((PROFILE_FILE, None), (NEWS_PROFILE, DEFAULT_PROFILE_MD)):
        try:
            t = _rules_file(f, default) if default else f.read_text(encoding="utf-8")
        except OSError:
            continue
        if privacy_of(t) not in (None, "public"):
            continue
        parts.append(PRIVATE_BLOCK.sub("", re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)).strip())
    return "\n\n".join(parts)


def _fetch_feed(src, per=10):
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0 TWIN-news"})
    with urllib.request.urlopen(req, timeout=12) as r:
        root = ET.fromstring(r.read())
    strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()
    out = []
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        get = lambda *names: next((c for c in it if c.tag.split("}")[-1] in names), None)
        t, d, l, p = get("title"), get("description", "summary", "content"), get("link"), get("pubDate", "published", "updated", "date")
        link = (l.get("href") or l.text or "").strip() if l is not None else ""
        when = None
        if p is not None and p.text:
            try:
                when = parsedate_to_datetime(p.text.strip())
            except (TypeError, ValueError):
                try:
                    when = dt.datetime.fromisoformat(p.text.strip().replace("Z", "+00:00"))
                except ValueError:
                    when = None
        if when is not None and when.tzinfo and (dt.datetime.now(when.tzinfo) - when).days > 2:
            continue  # 只要最近两天的
        title = strip(t.text if t is not None else "")
        if title:
            out.append({"src": src["name"], "title": title[:200], "desc": strip(d.text if d is not None else "")[:240], "link": link})
        if len(out) >= per:
            break
    return out


def make_news(provider_id=None):
    from concurrent.futures import ThreadPoolExecutor
    srcs, raw, failed = news_sources(), [], []

    def one(s):
        try:
            return s, _fetch_feed(s), ""
        except Exception as e:  # noqa: BLE001  一个来源连不上不影响别的
            return s, [], str(e)[:80]
    with ThreadPoolExecutor(8) as ex:
        for s, items, err in ex.map(one, srcs):
            raw += items
            if err or not items:
                failed.append({"name": s["name"], "error": err or "最近两天没有新内容"})
    if not raw:
        raise RuntimeError("所有来源都连不上，检查一下网络或代理。")
    me = news_me()
    check_outgoing(me)
    listing = "\n".join(f"[{n}] （{x['src']}）{x['title']} —— {x['desc']}" for n, x in enumerate(raw))
    out = parse_json_block(call_model("你是只为一个人服务的情报编辑：从大量新闻里挑出对他影响最大的，用中文讲清楚对他意味着什么。",
                                      [{"role": "user", "content": NEWS_PROMPT.format(today=today(), me=me, items=listing)}],
                                      active_provider(provider_id), 2500))
    items = []
    for x in out.get("items") or []:
        try:
            src = raw[int(x.get("n"))]
            score = max(1, min(5, int(x.get("score") or 3)))
        except (TypeError, ValueError, IndexError):
            continue
        if score < 3:
            continue
        items.append({"tag": _cell(x.get("tag"))[:6] or "要闻", "title": _cell(x.get("title"))[:40], "summary": _cell(x.get("summary"))[:300],
                      "impact": _cell(x.get("impact"))[:200], "action": _cell(x.get("action"))[:120], "score": score,
                      "source": src["src"], "link": src["link"], "orig": src["title"]})
    data = {"date": today(), "time": dt.datetime.now().strftime("%H:%M"), "overview": _cell(out.get("overview"))[:200],
            "items": sorted(items, key=lambda x: -x["score"]), "failed": failed, "fetched": len(raw), "sources": len(srcs)}
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    (NEWS_DIR / f"{today()}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def news_today(date=""):
    """某一天的要闻（默认今天），带上有记录的日期（新的在前）和收藏了哪些。"""
    date = date if re.match(r"^\d{4}-\d{2}-\d{2}$", date or "") else today()
    f = NEWS_DIR / f"{date}.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        d = {}
    days = sorted((p.stem for p in NEWS_DIR.glob("????-??-??.json")), reverse=True) if NEWS_DIR.exists() else []
    return {**d, "date": d.get("date") or date, "days": days[:90], "starred": [x["link"] for x in news_starred()]}


# ---------- 收藏：每天的要闻都留着；想细看的点星收藏，存在 News/收藏.json，另写一页 要闻收藏.md 方便在 Obsidian 里看 ----------
STAR_FILE, STAR_MD = NEWS_DIR / "收藏.json", NEWS_DIR / "要闻收藏.md"


def news_starred():
    try:
        return json.loads(STAR_FILE.read_text(encoding="utf-8")) if STAR_FILE.exists() else []
    except ValueError:
        return []


def news_star(date, link, on):
    """收藏 / 取消收藏某天的一条要闻（按原文链接认）。"""
    xs = [x for x in news_starred() if x.get("link") != link]
    if on:
        day = news_today(date)
        it = next((x for x in day.get("items") or [] if x.get("link") == link), None)
        if not it:
            raise RuntimeError("这一天的要闻里没有这一条了。")
        xs.insert(0, {**it, "date": day["date"]})
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    STAR_FILE.write_text(json.dumps(xs, ensure_ascii=False, indent=1), encoding="utf-8")
    md = "".join(f"\n## {x.get('title', '')}\n\n{x.get('date', '')} · {x.get('source', '')} · [原文]({x.get('link', '')})\n\n{x.get('summary', '')}\n"
                 + (f"\n**对你**：{x['impact']}\n" if x.get("impact") else "") for x in xs)
    STAR_MD.write_text(f"---\ntype: brief\nupdated: {today()}\nprivacy: internal\n---\n# 要闻收藏\n\n> 在 TWIN 要闻页点星收藏的，自动更新这一页。\n{md}", encoding="utf-8")
    return {"starred": xs}
