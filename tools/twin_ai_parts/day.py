# twin_ai 的一部分：天气和作息、个人设置。
# 不单独 import：twin_ai.py 末尾把这个文件放进它自己的命名空间里执行，和写在 twin_ai.py 里完全一样，
# 直接用那里的函数和变量（ROOT、_write、call_model……），外面照旧用 twin_ai.xxx。
# flake8: noqa

# ---------- 天气和作息：本机从 Open-Meteo 取天气（免费、不用注册）；AI 只看到城市名、天气数字和作息时段 ----------
WEATHER_DIR = BRIEFS / "Weather"
WEATHER_RULES = ROOT / "_RULES" / "Weather_Rhythm.md"
DEFAULT_WEATHER_MD = """---
type: rules
updated: {today}
privacy: public
---
# 天气地点和作息

> “今天”页的天气按下面的地点取（Open-Meteo，免费，不用注册）。只填到城市或学校，不填住址。
> 作息表用来画“今天”页的时段条，并在每个时段提醒你该做什么。都可以直接改。
> 发给 AI 的只有：地点名、天气数字、作息时段。

## 地点
| 地点 | 纬度 | 经度 |
|---|---|---|
| 北京 | 39.90 | 116.40 |

## 作息
| 时段 | 开始 | 结束 | 做什么 |
|---|---|---|---|
| 上午 | 09:00 | 12:00 | 精力最好，做最难的事 |
| 下午 | 13:30 | 18:00 | 主力时段：工作、学习 |
| 晚上 | 19:00 | 22:30 | 自己的事：副业、学习、整理资料 |
| 睡前 | 22:30 | 23:30 | 放松，别熬太晚 |

## 时间分配目标
工作 5 成，学习 3 成，休闲 2 成。

## 碎片时间提醒
- 想刷视频的时候，先看一眼“今天要做”还剩几件
- 休息几分钟：起来走走，喝口水
- 通勤路上：想想今天最难的那件事怎么做
"""
# 天气代码 → （中文，图标名）。图标用 Lucide（ISC 开源协议），前端按名字画
WX = {0: ("晴", "sun"), 1: ("大致晴", "sun"), 2: ("多云", "cloud-sun"), 3: ("阴", "cloud"), 45: ("雾", "cloud-fog"), 48: ("雾凇", "cloud-fog"),
      51: ("小毛毛雨", "cloud-drizzle"), 53: ("毛毛雨", "cloud-drizzle"), 55: ("大毛毛雨", "cloud-drizzle"), 61: ("小雨", "cloud-rain"), 63: ("中雨", "cloud-rain"),
      65: ("大雨", "cloud-rain"), 66: ("冻雨", "cloud-rain"), 67: ("冻雨", "cloud-rain"), 71: ("小雪", "cloud-snow"), 73: ("中雪", "cloud-snow"), 75: ("大雪", "snowflake"),
      77: ("雪粒", "cloud-snow"), 80: ("阵雨", "cloud-rain"), 81: ("阵雨", "cloud-rain"), 82: ("强阵雨", "cloud-lightning"), 85: ("阵雪", "cloud-snow"),
      86: ("强阵雪", "snowflake"), 95: ("雷阵雨", "cloud-lightning"), 96: ("雷阵雨伴冰雹", "cloud-lightning"), 99: ("强雷阵雨伴冰雹", "cloud-lightning")}
WEATHER_PROMPT = """今天是 {today}，我在{place}。下面是今天的天气和我的作息，请给我 3 条今天的注意事项。
要具体到时段和动作（比如“11 点出门时有雨，带伞”“晚上降到 8 度，23 点回去加外套”），结合我的作息，不要说空话。
天气：
{wx}
作息：
{rhythm}
只输出一个 JSON：{{"tips":["一句话","一句话","一句话"]}}"""


def _hm(s):
    try:
        h, m = str(s).strip().split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def rhythm():
    """作息时段、碎片提醒、地点，都从 _RULES/Weather_Rhythm.md 读。"""
    text = _rules_file(WEATHER_RULES, DEFAULT_WEATHER_MD)
    blocks = []
    for c in _table_rows(text, "做什么"):
        if len(c) >= 4 and _hm(c[1]) is not None and _hm(c[2]) is not None:
            blocks.append({"name": c[0], "start": c[1], "end": c[2], "what": c[3]})
    place = None
    for c in _table_rows(text, "纬度"):
        try:
            place = {"name": c[0], "lat": float(c[1]), "lon": float(c[2])}
            break
        except (ValueError, IndexError):
            continue
    m = re.search(r"## 碎片时间提醒\n(.*?)(?:\n## |\Z)", text, re.S)
    nudges = [x.strip()[2:].strip() for x in (m.group(1) if m else "").splitlines() if x.strip().startswith("- ")]
    m = re.search(r"## 时间分配目标\n(.*?)(?:\n## |\Z)", text, re.S)
    return {"blocks": blocks, "place": place, "nudges": nudges, "split": (m.group(1).strip() if m else "")}


# ---------- 个人设置：第一次打开时的向导填的（称呼、地点、作息模板），以后在设置里改 ----------
PROFILE = ROOT / "_RULES" / "Profile.md"
PROFILE_MD = """---
type: rules
updated: {today}
privacy: internal
---
# 个人设置

> 第一次打开时填的，可以直接改，也可以在网页“设置”里改。
> 地点和作息在 `_RULES/Weather_Rhythm.md`。身份证号、资产这些敏感信息不放这里。

| 项 | 内容 |
|---|---|
| 称呼 | {name} |
"""
RHYTHM_PRESETS = {
    "上学": [("上午", "08:00", "12:00", "上课或自习，最难的功课放这里"), ("下午", "14:00", "18:00", "上课、实验、作业"),
             ("晚上", "19:00", "22:30", "复习、自己的项目"), ("睡前", "22:30", "23:30", "放松，别熬太晚")],
    "上班": [("早上", "07:30", "09:00", "通勤：听点东西，想想今天最难的事"), ("上午", "09:00", "12:00", "工作：最难的事放这里"),
             ("下午", "13:30", "18:00", "工作、开会"), ("晚上", "19:30", "22:30", "自己的事：副业、学习"), ("睡前", "22:30", "23:30", "放松，别熬太晚")],
    "自由": [("上午", "09:00", "12:00", "精力最好，做最难的事"), ("下午", "13:30", "18:00", "主力时段"),
             ("晚上", "19:00", "23:00", "第二主力或休闲"), ("深夜", "23:00", "00:30", "放松，别熬太晚")],
}


# 个人画像：向导里分几步填，写进 00_Crown/Profile.md 的“- **项：** 内容”行，都能空着以后补。(步骤, 说明, [(项, 例子)])
CROWN_PROFILE = ROOT / "00_Crown" / "Profile.md"
CROWN_MD = """---
type: crown
updated: {today}
privacy: public
---
# Me（一页纸画像）

> 每次找 AI 做决策时，第一个给它的文件，会作为摘要发出去：别写身份证号、电话、住址、金额。
> 没填的项以后在“设置 → 个人画像”里补，也可以直接改这个文件，一项下面可以加缩进的小点。

"""
PORTRAIT = [
    ("你是谁", "让 AI 知道在跟谁说话。", [("当前身份", "比如：大三学生 / 嵌入式工程师 / 自由职业"), ("所在领域", "专业或行业，比如：电子信息、设计、财务")]),
    ("你会什么", "判断一件事你接不接得住，推荐学什么。", [("核心技能", "最拿得出手的两三样，逗号隔开"), ("代表经历", "一两件最能说明你的事"), ("想学的", "接下来想补的能力")]),
    ("你要去哪", "排优先级、给建议时对照用。", [("当前焦点", "这一两个月最重要的事"), ("长期方向", "3 到 5 年想成为什么样"), ("不做的事", "明确不碰的方向或活")]),
    ("你怎么过", "安排一天、提醒休息用。", [("作息（大概）", "比如：8 点起，12 点睡，下午效率最高"), ("兴趣爱好", "运动、音乐、游戏……"), ("时间分配目标", "比如：学习 50%、项目 30%、休息 20%")]),
    ("想让 AI 怎么帮你", "AI 回答的口吻和重点。", [("想让 AI 帮的事", "比如：拆任务、找机会、督促我"), ("说话方式", "比如：直接说结论、多给理由、别太客气")]),
]
_PITEM = re.compile(r"^- \*\*(.+?)：\*\*[ \t]*(.*)$", re.M)


def profile():
    name = ""
    if PROFILE.exists():
        rows = {c[0]: c[1] for c in _table_rows(PROFILE.read_text(encoding="utf-8"), "内容") if len(c) >= 2}
        name = rows.get("称呼", "")
    have = dict(_PITEM.findall(CROWN_PROFILE.read_text(encoding="utf-8"))) if CROWN_PROFILE.exists() else {}
    return {"done": PROFILE.exists(), "name": name, "place": rhythm()["place"], "presets": list(RHYTHM_PRESETS),
            "fields": PORTRAIT, "portrait": {k: have.get(k, "") for _, _, fs in PORTRAIT for k, _ in fs}}


def _save_portrait(name, data):
    """只改传进来的项：有这一行就换掉冒号后面的内容（下面的小点不动），没有且填了就加在最后。"""
    keys = [k for _, _, fs in PORTRAIT for k, _ in fs]
    # 画像是一行行的列表，不是表格：竖线原样留着（[[文件|显示名]] 这种链接要用），只把换行压成空格
    vals = {"称呼": name, **{k: re.sub(r"\s*\n\s*", " ", str(data.get(k) or "")).strip()[:200] for k in keys if k in data}}
    text = CROWN_PROFILE.read_text(encoding="utf-8") if CROWN_PROFILE.exists() else CROWN_MD.format(today=today())
    for k, v in vals.items():
        line = f"- **{k}：** {v}".rstrip()
        m = re.search(rf"^- \*\*{re.escape(k)}：\*\*.*$", text, re.M)
        if m:
            text = text[:m.start()] + line + text[m.end():]
        elif v:
            text = text.rstrip("\n")
            text += ("\n\n" if text.splitlines()[-1].startswith(">") else "\n") + line + "\n"
    text = re.sub(r"^updated: .*$", f"updated: {today()}", text, count=1, flags=re.M)
    CROWN_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    CROWN_PROFILE.write_text(text, encoding="utf-8")


def rules_text():
    return RATIONAL_RULES.replace("{name}", profile()["name"] or "用户")


def _replace_table(text, head, rows):
    """把以 head 这一行开头的表格换成 rows（保留表头和分隔线）。"""
    i = text.index(head) + len(head) + 1
    i = text.index("\n", i) + 1  # 跳过分隔线
    j = i
    while text.startswith("|", j):
        j = text.index("\n", j) + 1 if "\n" in text[j:] else len(text)
    return text[:i] + "".join("| " + " | ".join(_cell(x) for x in r) + " |\n" for r in rows) + text[j:]


def save_profile(name, place=None, preset="", portrait=None):
    name = _cell(name)[:20]
    if not name:
        raise RuntimeError("先写一个称呼。")
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(PROFILE_MD.format(today=today(), name=name), encoding="utf-8")
    _save_portrait(name, portrait or {})
    text = _rules_file(WEATHER_RULES, DEFAULT_WEATHER_MD)
    if place:
        lat, lon = float(place["lat"]), float(place["lon"])
        text = _replace_table(text, "| 地点 | 纬度 | 经度 |", [(place["name"], f"{lat:.2f}", f"{lon:.2f}")])
        (WEATHER_DIR / f"{today()}.json").unlink(missing_ok=True)  # 换了地方，今天的天气缓存作废
    if preset in RHYTHM_PRESETS:
        text = _replace_table(text, "| 时段 | 开始 | 结束 | 做什么 |", RHYTHM_PRESETS[preset])
    WEATHER_RULES.write_text(text, encoding="utf-8")
    return profile()


def geocode(q):
    """城市名 → 坐标（Open-Meteo 地名搜索，免费，只发城市名）。"""
    q = str(q or "").strip()[:40]
    if not q:
        return []
    url = "https://geocoding-api.open-meteo.com/v1/search?count=6&language=zh&name=" + quote(q)
    j = json.loads(_get(url)[0].decode())
    return [{"name": " · ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country")) if x), "lat": r["latitude"], "lon": r["longitude"]}
            for r in j.get("results") or []]


def _local_tips(w):
    """不用 AI 也能给的提醒：出门、回去时段有没有雨，温差，紫外线。"""
    tips, hrs = [], {x["h"]: x for x in w["hours"]}
    for h, what in ((11, "11 点左右出门"), (23, "23 点左右回去")):
        x = hrs.get(h)
        if x and x["rain"] >= 50:
            tips.append(f"{what}降雨概率 {x['rain']}%，带伞。")
    d = w["today"]
    if d["max"] - d["min"] >= 8:
        tips.append(f"今天温差 {round(d['max'] - d['min'])} 度，晚上带件外套。")
    if d.get("uv", 0) >= 6:
        tips.append("紫外线强，中午注意防晒。")
    if d["min"] <= 5:
        tips.append(f"最低 {round(d['min'])} 度，深夜回去穿厚点。")
    return tips


def weather(force=False):
    """一小时内取过就用缓存。取不到就返回上次的，标上 stale。"""
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    f = WEATHER_DIR / f"{today()}.json"
    old = None
    try:
        old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except ValueError:
        old = None
    r = rhythm()
    fresh = old and max((x["h"] for x in old.get("hours", [])), default=0) > 26  # 旧缓存只到凌晨 2 点，重新取
    if fresh and not force and time.time() - old.get("ts", 0) < 3600:
        return old
    p = r["place"]
    if not p:
        raise RuntimeError("_RULES/Weather_Rhythm.md 里没写地点。")
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=Asia%%2FShanghai&forecast_days=2"
           "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m"
           "&hourly=temperature_2m,precipitation_probability,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,uv_index_max") % (p["lat"], p["lon"])
    j = None
    for wait in (10, 20):  # 天气服务器在国外，偶尔握手超时：再等久一点试一次
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "TWIN"}), timeout=wait) as resp:
                j = json.loads(resp.read().decode())
            break
        except (OSError, ValueError):
            pass
    if j is None:
        if old:
            old["stale"] = True
            return old
        y = WEATHER_DIR / f"{(dt.date.today() - dt.timedelta(days=1)).isoformat()}.json"
        try:  # 过了零点还没取到今天的：用昨天取的“明天”顶上
            o = json.loads(y.read_text(encoding="utf-8"))
            return {**o, "date": today(), "today": o["tomorrow"], "hours": [{**x, "h": x["h"] - 24} for x in o["hours"] if x["h"] >= 24], "stale": True}
        except (OSError, ValueError, KeyError):
            raise RuntimeError("天气暂时取不到：连不上天气服务器（open-meteo.com），可能是网络或代理的问题，过一会儿会自动再试。")
    c, dl, hl = j["current"], j["daily"], j["hourly"]
    day = lambda i: {"max": dl["temperature_2m_max"][i], "min": dl["temperature_2m_min"][i], "rain": dl["precipitation_probability_max"][i] or 0,
                     "uv": dl["uv_index_max"][i] or 0, "text": WX.get(dl["weather_code"][i], ("", ""))[0], "icon": WX.get(dl["weather_code"][i], ("", "cloud"))[1]}
    hours = []
    for i, t in enumerate(hl["time"]):  # 今天 8 点到明天晚上，深夜点开也能看到接下来十几个小时
        hh = int(t[11:13]) + (0 if t.startswith(today()) else 24)
        if 8 <= hh <= 47:
            hours.append({"h": hh, "t": hl["temperature_2m"][i], "rain": hl["precipitation_probability"][i] or 0, "icon": WX.get(hl["weather_code"][i], ("", ""))[1]})
    w = {"date": today(), "ts": time.time(), "time": dt.datetime.now().strftime("%H:%M"), "place": p["name"],
         "now": {"t": c["temperature_2m"], "feel": c["apparent_temperature"], "wind": c["wind_speed_10m"], "hum": c["relative_humidity_2m"],
                 "text": WX.get(c["weather_code"], ("", ""))[0], "icon": WX.get(c["weather_code"], ("", "cloud"))[1]},
         "today": day(0), "tomorrow": day(1), "hours": hours}
    w["local_tips"] = _local_tips(w)
    if old and old.get("ai_tips"):
        w["ai_tips"] = old["ai_tips"]
    f.write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
    return w


def weather_tips(provider_id=None):
    w = weather()
    r = rhythm()
    wx = (f"现在 {w['now']['t']}°C（体感 {w['now']['feel']}°C），{w['now']['text']}；今天 {w['today']['min']}～{w['today']['max']}°C，"
          f"{w['today']['text']}，最大降雨概率 {w['today']['rain']}%，紫外线 {w['today']['uv']}\n逐小时（时 温度 降雨概率）："
          + "，".join(f"{x['h'] % 24}点 {round(x['t'])}° {x['rain']}%" for x in [y for y in w["hours"] if y["h"] <= 26][::2]))  # 发给 AI 的只到今晚，省 token
    rh = "\n".join(f"{b['start']}-{b['end']} {b['name']}：{b['what']}" for b in r["blocks"])
    text = WEATHER_PROMPT.format(today=today(), place=w["place"], wx=wx, rhythm=rh)
    check_outgoing(text)
    out = parse_json_block(call_model("你是贴心又务实的生活助理，只依据给出的天气和作息说话。", [{"role": "user", "content": text}],
                                      active_provider(provider_id), 600))
    tips = [_cell(x)[:80] for x in (out.get("tips") or []) if isinstance(x, str) and x.strip()][:4]
    if not tips:
        raise RuntimeError("AI 没给出提醒，再试一次。")
    w["ai_tips"] = tips
    (WEATHER_DIR / f"{today()}.json").write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
    return w
