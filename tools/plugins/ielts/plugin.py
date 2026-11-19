"""雅思小练习：在零碎时间里出一张卡片（单词读写、同义替换、写作句型、阅读题型），按遗忘曲线安排复习。

  - 单词：words.csv（ECDICT 里标了 ielts 的词，MIT 许可）；句型 patterns.json、同义替换 synonyms.csv 都是自己编的。
  - 阅读：自带 reading.json（42 篇原创文章、252 道题，照真题题型和设陷阱的方式写）；点“备阅读题”时请 AI 现写一篇原创文章和 6 道题（判断、选择、填空），带中文解析；
    或者“导入阅读题”：把自己手上的真题粘贴进来，AI 整理成卡片、补解析。都是手动触发，一次一次调用。
  - 进度存在知识库 01_Skills/03_Language/IELTS/：progress.json（每张卡在第几格、哪天再出）、reading.json（题库），
    还有一页 雅思练习.md 给自己和 AI 看进度。
"""
import csv
import datetime as dt
import json
import random
from pathlib import Path

import twin_ai
from twin import ROOT

NAME = "雅思小练习"
DESC = "零碎时间出一道题：单词、写作句型、阅读题型，答错有解析，按遗忘曲线复习。"
HERE = Path(__file__).resolve().parent
DATA = ROOT / "01_Skills" / "03_Language" / "IELTS"
PROG, BANK, NOTE = DATA / "progress.json", DATA / "reading.json", DATA / "雅思练习.md"
GAPS = [0, 1, 2, 4, 7, 15, 30, 60]  # 第 n 格隔几天再出：答对进一格；答错回到第 0 格，过 20 分钟再出
NEW = {"w": 8, "p": 2, "r": 6, "s": 6}  # 每天最多学几个新的：单词、句型、阅读题、同义替换
TOPICS = ["城市热岛", "蜜蜂和授粉", "海水淡化", "珊瑚礁", "候鸟迁徙", "丝绸之路贸易", "印刷术的传播", "睡眠与记忆", "双语儿童的大脑",
          "塑料回收", "风力发电", "古埃及建筑", "茶的历史", "城市绿地", "抗生素耐药性", "沙漠化", "远程办公", "博物馆的未来",
          "电动汽车电池", "垂直农场", "章鱼的智力", "冰川消融", "儿童阅读习惯", "旅游业与当地文化", "人工智能翻译", "竹子建筑",
          "地铁的发展", "咖啡种植", "噪音污染", "古代航海", "可可和巧克力", "大熊猫保护", "海洋酸化", "音乐与学习", "火山监测"]
_W = _S = None
LOG0 = [0, 0, 0, 0, 0, 0]  # 答了几题、对了几题、新单词、新句型、新阅读、新同义替换


def _words():
    global _W
    if _W is None:
        with open(HERE / "words.csv", encoding="utf-8") as f:
            _W = [r for r in csv.DictReader(f)]
    return _W


def _syns():
    global _S
    if _S is None:
        with open(HERE / "synonyms.csv", encoding="utf-8") as f:
            _S = [r for r in csv.DictReader(f)]
    return _S


def _bank():
    """自带的原创题 + 自己备的、导入的题。"""
    return _load(HERE / "reading.json", []) + _load(BANK, [])


def _patterns():
    return json.loads((HERE / "patterns.json").read_text(encoding="utf-8"))


def _load(f, default):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(f, data):
    DATA.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")


def _prog():
    p = _load(PROG, {})
    p.setdefault("cards", {})
    p.setdefault("log", {})  # 日期 → LOG0
    for v in p["log"].values():
        v += [0] * (len(LOG0) - len(v))
    return p


def _today():
    return dt.date.today().isoformat()


def _now():
    """到期时间用“日期”或“日期T时:分”，字符串直接比大小就行。"""
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M")


def _new_card(p, bank, skip=()):
    """今天还能学的新卡：单词按词频顺序、句型按顺序、阅读按题库顺序。今天点 ✕ 跳过的不算。"""
    day = p["log"].get(_today(), LOG0)
    c = {**p["cards"], **dict.fromkeys(skip)}
    out = []
    if day[2] < NEW["w"]:
        w = next((x["word"] for x in _words() if f"wr:{x['word']}" not in c), None)
        if w:
            out.append((0.4, f"wr:{w}"))
    if day[3] < NEW["p"]:
        i = next((x["id"] for x in _patterns() if f"p:{x['id']}" not in c), None)
        if i:
            out.append((0.15, f"p:{i}"))
    if day[4] < NEW["r"]:
        r = next((f"r:{s['id']}:{k}" for s in bank for k in range(len(s["questions"])) if f"r:{s['id']}:{k}" not in c), None)
        if r:
            out.append((0.3, r))
    if day[5] < NEW["s"]:
        s = next((x["word"] for x in _syns() if f"s:{x['word']}" not in c), None)
        if s:
            out.append((0.15, f"s:{s}"))
    return random.choices([x for _, x in out], [w for w, _ in out])[0] if out else None


def _card(cid, bank):
    kind, _, key = cid.partition(":")
    if kind in ("wr", "ww"):
        ws = _words()
        w = next((x for x in ws if x["word"] == key), None)
        if not w:
            return None
        if kind == "ww":
            return {"kind": "ww", "meaning": w["meaning"], "phonetic": w["phonetic"], "hint": f"{w['word'][0]}{'_' * (len(w['word']) - 1)}", "answer": w["word"]}
        opts = [w["meaning"]] + [x["meaning"] for x in random.sample(ws, 3) if x["word"] != w["word"]][:3]
        random.shuffle(opts)
        return {"kind": "wr", "word": w["word"], "phonetic": w["phonetic"], "options": opts, "answer": opts.index(w["meaning"])}
    if kind == "s":
        ss = _syns()
        s = next((x for x in ss if x["word"] == key), None)
        if not s:
            return None
        opts = [s["syn"]] + [x["syn"] for x in random.sample(ss, 4) if x["word"] != key and x["syn"] != s["syn"]][:3]
        random.shuffle(opts)
        return {"kind": "s", "word": s["word"], "zh": s["zh"], "options": opts, "answer": opts.index(s["syn"])}
    if kind == "p":
        return next(({"kind": "p", **{k: v for k, v in x.items() if k != "id"}} for x in _patterns() if str(x["id"]) == key), None)
    if kind == "r":
        sid, _, k = key.partition(":")
        s = next((x for x in bank if x["id"] == sid), None)
        if not s or not k.isdigit() or int(k) >= len(s["questions"]):
            return None
        q = dict(s["questions"][int(k)])
        if q.get("type") in ("tfng", "ynng"):  # 判断题的三个选项固定，题库里可以不写
            q["options"] = ["TRUE", "FALSE", "NOT GIVEN"] if q["type"] == "tfng" else ["YES", "NO", "NOT GIVEN"]
        return {"kind": "r", "title": s["title"], "text": s["text"], "vocab": s.get("vocab", []), "n": int(k) + 1, "of": len(s["questions"]), **q}
    return None


def get(path, qs):
    if path == "stats":
        return stats()
    if path != "next":
        raise RuntimeError("没有这个功能。")
    p, bank, skip = _prog(), _bank(), set(filter(None, str(qs.get("skip", "")).split(",")))
    due = [k for k, (_, d) in p["cards"].items() if d <= _now() and k not in skip]
    new = _new_card(p, bank, skip) if (not due or random.random() < 0.3) else None
    for cid in ([new] if new else []) + random.sample(due, len(due)):
        c = _card(cid, bank)
        if c:
            return {**c, "id": cid, "new": cid == new}
    return {"empty": True, "bank": sum(len(s["questions"]) for s in bank), "hasAi": bool(twin_ai.load_config().get("providers"))}


def _answer(cid, ok):
    p = _prog()
    c, day = p["cards"], p["log"].setdefault(_today(), list(LOG0))
    if cid not in c:  # 第一次答：算今天学的新卡
        day[{"wr": 2, "ww": 2, "p": 3, "r": 4, "s": 5}.get(cid.split(":")[0], 2)] += 1
    box = min(c.get(cid, [0])[0] + 1, len(GAPS) - 1) if ok else 0
    # 下次出现从答题这一刻算（答对隔 1、2、4… 天，答错 20 分钟），不按日历日期：半夜 23:50 学的不会 00:05 又出来
    at = lambda **k: (dt.datetime.now() + dt.timedelta(**k)).strftime("%Y-%m-%dT%H:%M")
    c[cid] = [box, at(days=GAPS[box]) if ok else at(minutes=20)]
    if cid.startswith("wr:") and ok and f"ww:{cid[3:]}" not in c:  # 认得了，过一天开始练拼写
        c[f"ww:{cid[3:]}"] = [0, at(days=1)]
    day[0] += 1
    day[1] += bool(ok)
    _save(PROG, p)
    _write_note(p)
    return stats(p)


def stats(p=None):
    p = p or _prog()
    c, bank = p["cards"], _bank()
    k = lambda pre: sum(1 for x in c if x.startswith(pre))
    last7 = [v for d, v in p["log"].items() if d >= (dt.date.today() - dt.timedelta(days=6)).isoformat()]
    a, r = sum(v[0] for v in last7), sum(v[1] for v in last7)
    return {"words": k("wr:"), "patterns": k("p:"), "syns": k("s:"), "reading": k("r:"), "due": sum(1 for _, d in c.values() if d[:10] <= _today()),
            "bank": sum(len(s["questions"]) for s in bank), "left": sum(len(s["questions"]) for s in bank) - k("r:"),
            "week": a, "rate": round(r * 100 / a) if a else None, "today": p["log"].get(_today(), [0, 0])[0]}


def _write_note(p):
    s = stats(p)
    NOTE.write_text(f"""---
type: life
updated: {_today()}
privacy: internal
---
# 雅思练习进度

> TWIN 的“雅思小练习”插件自动更新这一页，不用手改。

- 学过的单词：{s['words']} 个；同义替换：{s['syns']} 组；写作句型：{s['patterns']} 个；做过的阅读题：{s['reading']} 道
- 最近 7 天：答了 {s['week']} 题，正确率 {s['rate'] if s['rate'] is not None else '-'}%
- 今天到期要复习：{s['due']} 张
""", encoding="utf-8")


READ_PROMPT = """写一篇原创的雅思学术类阅读文章，题材：{topic}。
要求：英文，学术类文风，350–450 词，4–5 段，每段开头标 A、B、C…，难度接近雅思 6–7 分；有具体信息（数字、年份、研究者的观点）；完全原创，不要照搬任何已出版的真题或文章。
然后照真题出 6 道题：2 道 TRUE / FALSE / NOT GIVEN（至少 1 道是 NOT GIVEN：原文提到了这件事，但没说题干问的那一点），1 道段落标题配对（"Choose the correct heading for paragraph X."，5 个罗马数字选项 i–v，干扰项用别的段的内容或段里的细节），1 道信息配对（"Which paragraph mentions ...?"，选项 A、B、C、D…），1 道四选一，1 道填空（答案取原文，不超过两个词）。
题干一律用同义改写，不要照抄原文的词，就像真题那样。
每题给中文解析：答案在哪一段哪句、用了哪组同义替换、其他选项为什么错；最后用一句话讲这种题型的做题技巧。我是零基础，解析写得通俗。
再列出文中 5 个值得记的词或短语（英文 + 中文）。
只输出一个 json 代码块：
{{"title":"英文标题","text":"正文，段落之间空一行","vocab":[["word","中文"]],
 "questions":[{{"type":"tfng|mc|fill","q":"题干，填空题用 ____ 表示空","options":["A ...","B ...","C ...","D ..."],"answer":"TRUE / FALSE / NOT GIVEN，或选项字母、罗马数字，或填空答案（几种都对就用 / 隔开）","explain":"中文解析"}}]}}
判断题和填空题不要 options。"""


IMPORT_PROMPT = """下面是我粘贴的一套雅思阅读材料（文章和题目，可能带答案，格式可能很乱）。帮我整理成练习卡片。
要求：
- 文章原样保留（只去掉页码、广告这类杂物），不要改写、不要删段。
- 每道题按题型归类：TRUE/FALSE/NOT GIVEN 用 tfng；YES/NO/NOT GIVEN 用 ynng；单选、段落标题配对、信息配对这类有固定选项的用 mc（把选项列全，每个选项以字母或罗马数字开头）；填空、句子完成、摘要填空、简答用 fill。
- 材料里给了答案就以它为准；没给的你自己作答，并在解析开头写“（答案为 AI 推断）”。
- 每题写中文解析：答案在哪一段哪句、为什么对、容易错在哪；我是零基础，写得通俗。
- 再列 5–8 个文中值得记的词（英文 + 中文）。
只输出一个 json 代码块：
{{"title":"文章标题","text":"文章正文，段落之间空一行","vocab":[["word","中文"]],
 "questions":[{{"type":"tfng|ynng|mc|fill","q":"题干","options":["A ...","B ..."],"answer":"答案（几种都对就用 / 隔开）","explain":"中文解析"}}]}}
tfng、ynng、fill 不要 options。

=== 材料 ===
{text}"""


def _add(bank, d, topic):
    qs = [q for q in d.get("questions", []) if isinstance(q, dict) and q.get("q") and q.get("answer") and q.get("type") in ("tfng", "ynng", "mc", "fill")]
    if not d.get("text") or len(qs) < 1:
        raise RuntimeError("AI 这次没整理出题目，检查一下粘贴的内容，或者再试一次。")
    for q in qs:
        if q["type"] in ("tfng", "ynng"):
            q["options"] = ["TRUE", "FALSE", "NOT GIVEN"] if q["type"] == "tfng" else ["YES", "NO", "NOT GIVEN"]
        elif q["type"] == "fill":
            q.pop("options", None)
    bank.append({"id": f"{_today()}-{len(bank) + 1}", "topic": topic, "title": str(d.get("title", topic))[:120], "text": str(d["text"]),
                 "vocab": [v for v in d.get("vocab", []) if isinstance(v, list) and len(v) == 2][:8], "questions": qs})
    _save(BANK, bank)
    return len(qs)


def import_set(text):
    """把自己手上的真题（文章 + 题目 + 答案）粘贴进来，AI 整理成卡片并补解析。只存在自己的知识库里。"""
    text = str(text or "").strip()
    if len(text) < 200:
        raise RuntimeError("内容太短了：把文章、题目（有答案的话连答案）一起粘贴进来。")
    if len(text) > 30000:
        raise RuntimeError("一次只导入一篇文章和它的题目（3 万字以内）。")
    twin_ai.check_outgoing(text)
    ans = twin_ai.call_model("你是有经验的雅思阅读老师，只按要求输出 json。", [{"role": "user", "content": IMPORT_PROMPT.format(text=text)}],
                             twin_ai.active_provider(), 8000)
    n = _add(_load(BANK, []), twin_ai.parse_json_block(ans) or {}, "导入")
    return {**stats(), "added": n}


def prepare():
    """请 AI 写一篇阅读和 6 道题，加进题库。一次一次调用。"""
    bank = _load(BANK, [])
    used = {s.get("topic") for s in _bank()}
    topic = random.choice([t for t in TOPICS if t not in used] or TOPICS)
    ans = twin_ai.call_model("你是有经验的雅思阅读老师，只按要求输出 json。", [{"role": "user", "content": READ_PROMPT.format(topic=topic)}],
                             twin_ai.active_provider(), 4000)
    _add(bank, twin_ai.parse_json_block(ans) or {}, topic)
    return stats()


def post(path, body):
    if path == "answer":
        return _answer(str(body.get("id", "")), bool(body.get("ok")))
    if path == "prepare":
        return prepare()
    if path == "import":
        return import_set(body.get("text", ""))
    raise RuntimeError("没有这个功能。")

