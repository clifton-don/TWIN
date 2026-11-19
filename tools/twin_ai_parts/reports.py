# twin_ai 的一部分：每日简报、周报、决策回看、复盘升级、待决策、每日建议。
# 不单独 import：twin_ai.py 末尾把这个文件放进它自己的命名空间里执行，和写在 twin_ai.py 里完全一样，
# 直接用那里的函数和变量（ROOT、_write、call_model……），外面照旧用 twin_ai.xxx。
# flake8: noqa

# ---------- 每日简报 ----------
BRIEF_PROMPT = """请给我写今天（{today}）的简报。下面“本地计算的事实”是程序从我的文件里直接算出来的，准确，优先采用。

=== 本地计算的事实 ===
{facts}

输出格式（Markdown，总共不超过 300 字）：
## 今天最该做的 3 件事
每件一行：做什么 —— 为什么是今天（对应哪个目标或截止）
## 风险提醒
最多 3 条，没有就写“暂无”
## 需要你决定的一件事
一个问题，附你的倾向和理由
## 目标差距
一句话：离最近的目标还差多少，这周要做到什么程度
最后单独一行写：置信度：高/中/低；缺少的信息：……"""


def brief_facts():
    gl = [g for g in goals() if not g["private"]]  # 私密目标不发给 AI
    lines = [board_facts()]  # 只发项目级摘要，不发具体任务
    lines += [f"- 未完成的 P0/P1 零散待办：{open_tasks()} 件"]
    lines += [f"- 截止：{d['task']}，{d['due']}，还剩 {d['days']} 天" for d in deadlines()[:6]]
    lines += [f"- 到期待回看的决定：{d['title']}（{d['review_date']}）" for d in due_reviews()]
    lines += [f"- 目标：{g['name']} {g['current']}/{g['target']} {g['unit']}，截止 {g['due']}" for g in gl]
    return "\n".join(lines)


TITLE_PROMPT = """给下面这段对话起一个标题，方便以后在列表里找到。
要求：中文，4 到 14 个字，说清楚聊的是什么事（项目名、动作），不要标点、引号和“关于”“讨论”这类空话。只输出标题本身。

{talk}"""


def chat_title(messages, provider_id=None):
    """按对话内容起标题。只用发给过 AI 的消息（本地记账那类不算），每条截短。"""
    talk = []
    msgs = messages if len(messages) <= 10 else messages[:4] + messages[-6:]  # 开头定主题，结尾看后来聊到哪
    for m in msgs:
        c = re.sub(r"\n*\[(?:上一条回答的)?确认卡结果.*", "", str(m.get("content", "")), flags=re.S).strip()
        if c:
            talk.append(("我：" if m.get("role") == "user" else "AI：") + c[:300])
    if not talk:
        raise RuntimeError("对话还是空的")
    text = TITLE_PROMPT.replace("{talk}", "\n".join(talk))
    check_outgoing(text)
    raw = call_model("你只负责给对话起简短的标题。", [{"role": "user", "content": text}], active_provider(provider_id), 60)
    t = re.sub(r"^(标题[:：])", "", raw.strip().splitlines()[0] if raw.strip() else "").strip(" \"'“”‘’《》「」。.,，:：#*")
    if not t:
        raise RuntimeError("AI 没给出标题")
    return t[:20]


def make_brief(provider_id=None):
    text = call_model(system_prompt(), [{"role": "user", "content": BRIEF_PROMPT.replace("{today}", today()).replace("{facts}", brief_facts())}],
                      active_provider(provider_id), 1500)
    BRIEFS.mkdir(exist_ok=True)
    brief_path().write_text(f"---\ntype: brief\ndate: {today()}\nupdated: {today()}\nprivacy: internal\n---\n{text.strip()}\n", encoding="utf-8")
    return text



# ---------- 每周周报：先在本地把上周的事实算好，AI 点评可选 ----------
WEEKLY = BRIEFS / "Weekly"
WEEKLY_PROMPT = """这是我上周（{start} 到 {end}）的周报统计，程序从我的文件里直接算出来的，准确。

{facts}

请写一段周报点评（Markdown，不超过 350 字）：
## 这周做成了什么
一两句，具体到项目
## 哪里落后了
对照截止和优先级，最多 3 条，每条写一个下周可执行的补救
## 下周最该做的 3 件事
每件一行：做什么 —— 为什么
## 一个值得调整的习惯
基于数据（比如 AI 改动多、手动少，或者某项目一直没动），没有就写“暂无”
最后单独一行：置信度：高/中/低"""


def week_of(day=None):
    """返回 (年, 第几周, 周一, 周日)。默认是上一个完整的周。"""
    d = day or (dt.date.today() - dt.timedelta(days=7))
    y, w, _ = d.isocalendar()
    mon = d - dt.timedelta(days=d.weekday())
    return y, w, mon, mon + dt.timedelta(days=6)


def weekly_path(y, w):
    return WEEKLY / f"{y}-W{w:02d}.md"


def weekly_facts(start, end, health=None):
    import twin_hist  # 只在网页进程里有历史记录
    s, e = start.isoformat(), end.isoformat()
    inr = lambda x: bool(x) and s <= x[:10] <= e
    done, nxt, late = [], [], []
    for f in _board_files():
        try:
            if not re.search(r"^board:\s*P[0-3]", f.read_text(encoding="utf-8")[:1500], re.M):
                continue
            b = board(f.relative_to(ROOT).as_posix())
        except (OSError, RuntimeError):
            continue
        name = re.split(r"[（(]", b["name"])[0].strip()
        for t in b["tasks"]:
            if t["status"] == DONE and inr(t["done_on"]):
                done.append(f"- {name}：{t['task']}（{t['done_on'][5:]}）")
            elif t["status"] != DONE and t["days"] is not None:
                if t["days"] < 0:
                    late.append(f"- {name}：{t['task']}（过期 {-t['days']} 天）")
                elif t["days"] <= 7:
                    nxt.append(f"- {name}：{t['task']}（{t['due']}）")
    try:
        dash = DASHBOARD.read_text(encoding="utf-8")
    except OSError:
        dash = ""
    events = [f"- {c[0]} {c[1]}" for c in _table_rows(dash, "| 事件 |") if len(c) > 1 and inr(c[0])]
    fb = [r for r in _feedback_rows((start - dt.timedelta(days=1)).isoformat()) if r[0][:10] <= e]
    hist = [h for h in twin_hist.since((dt.date.today() - start).days + 1) if inr(h["time"])]
    by = {}
    for h in hist:
        by[h["source"]] = by.get(h["source"], 0) + 1
    lines = [f"### 完成了 {len(done)} 件", *(done or ["- （没有记录到完成的任务）"]),
             f"\n### 记下的事 {len(events)} 件", *(events or ["- （没有）"]),
             f"\n### 现在过期的 {len(late)} 件", *(late or ["- （没有）"]),
             f"\n### 接下来 7 天到期 {len(nxt)} 件", *(nxt or ["- （没有）"]),
             "\n### 其他",
             f"- 改动文件 {len(hist)} 次：" + ("、".join(f"{k} {v}" for k, v in by.items()) or "无"),
             f"- AI 回答反馈：有用 {sum(1 for r in fb if '有用' in r[1])}，没用 {sum(1 for r in fb if '没用' in r[1])}"]
    if health:
        lines.append(f"- 体检：红 {health['red']}、黄 {health['amber']}、灰 {health['grey']}")
    return "\n".join(lines)


def make_weekly(health=None, ai=False, provider_id=None, day=None):
    y, w, start, end = week_of(day)
    facts = weekly_facts(start, end, health)
    md = (f"---\ntype: weekly\nweek: {y}-W{w:02d}\nupdated: {today()}\nprivacy: internal\n---\n"
          f"# 周报 {y} 第 {w} 周（{start:%m-%d} – {end:%m-%d}）\n\n## 本地统计（程序算的，准确）\n\n{facts}\n")
    if ai:
        clean = "\n".join(l for l in facts.splitlines() if not find_sensitive(l))
        text = call_model(system_prompt(), [{"role": "user", "content": WEEKLY_PROMPT.format(start=start, end=end, facts=clean)}],
                          active_provider(provider_id), 1500)
        md += f"\n## AI 点评\n\n{text.strip()}\n"
    WEEKLY.mkdir(parents=True, exist_ok=True)
    p = weekly_path(y, w)
    p.write_text(md, encoding="utf-8")
    return p.relative_to(ROOT).as_posix()


def ensure_weekly(health=None):
    """进入新的一周后第一次打开，自动把上周的周报（本地统计部分）生成好。"""
    y, w, _, _ = week_of()
    if not weekly_path(y, w).exists():
        return make_weekly(health)
    return ""


def latest_weekly():
    fs = sorted(WEEKLY.glob("*-W*.md")) if WEEKLY.exists() else []
    if not fs:
        return None
    text = fs[-1].read_text(encoding="utf-8")
    return {"path": fs[-1].relative_to(ROOT).as_posix(), "title": title_line(text, fs[-1].stem), "has_ai": "## AI 点评" in text}


def title_line(text, fallback):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else fallback

# ---------- 决策回看 ----------
def _set_fm(text, key, value):
    value = str(value).replace("\n", " ")
    if re.search(rf"^{key}:.*$", text, re.M):
        return re.sub(rf"^{key}:.*$", f"{key}: {value}", text, count=1, flags=re.M)
    return text.replace("\nprivacy:", f"\n{key}: {value}\nprivacy:", 1)


def review_decision(rel, chosen, outcome, who_right):
    p = (ROOT / rel).resolve()
    if DECISIONS.resolve() not in p.parents or p.suffix != ".md":
        raise RuntimeError("只能回看 07_Decisions 里的决策记录")
    text = p.read_text(encoding="utf-8")
    for k, v in (("status", "reviewed"), ("chosen", chosen), ("outcome", outcome), ("who_right", who_right), ("updated", today())):
        text = _set_fm(text, k, v)
    text = text.rstrip() + f"\n\n### {today()} 回看\n- 最后选择：{chosen}\n- 结果：{outcome}\n- 谁判断得准：{who_right}\n"
    p.write_text(text, encoding="utf-8")
    return rel


# ---------- 每周复盘升级（自我优化）----------
# 只允许 AI 建议调整这些规则；时薪等金额不发给 AI，也不让 AI 改
TUNABLE = {"weights.pay", "weights.learning", "weights.alignment", "weights.clarity", "weights.load",
           "accept", "negotiate", "load_per_task", "hours_per_day", "review_days"}

UPGRADE_PROMPT = """这是我过去一段时间对你的回答的评价，以及我回看过的决定的结果。请据此帮我优化决策方式。

=== 回答反馈 ===
{feedback}

=== 回看过的决定 ===
{reviews}

=== 当前本地打分规则（可调的部分）===
{rules}

=== 当前经验教训 ===
{lessons}

只输出一个 json 代码块：
{"lessons": [{"text": "一条新经验教训，一句话，可执行", "reason": "从哪条反馈或结果得出"}],
 "rule_changes": [{"key": "例如 weights.pay", "to": 新数值, "reason": "为什么调"}],
 "remove_lessons": ["已经不成立、应该删掉的旧经验原文"],
 "summary": "两三句话：这段时间我的判断有什么规律"}
要求：证据不足就少给甚至不给，不要为了给而给；rule_changes 只能用这些 key：""" + "、".join(sorted(TUNABLE))


def _rules_md():
    ensure_rule_files()
    return RULES_FILE.read_text(encoding="utf-8")


def last_upgrade():
    m = re.findall(r"^- (\d{4}-\d{2}-\d{2}) 升级", _rules_md(), re.M)
    return m[-1] if m else ""


def _feedback_rows(since=""):
    try:
        text = FEEDBACK_FILE.read_text(encoding="utf-8")
    except OSError:
        return []
    return [c for c in _table_rows(text, "评价") if len(c) >= 4 and c[0] > since]


def upgrade_status():
    since = last_upgrade()
    reviewed = [d for d in decisions() if d["status"] == "reviewed"]
    return {"last": since, "feedback": len(_feedback_rows(since)), "reviewed": len(reviewed)}


def upgrade_payload():
    since = last_upgrade()
    fb = "\n".join(f"- {c[0]} {c[1]}：{c[2]}" + (f"（备注：{c[3]}）" if c[3] else "") for c in _feedback_rows(since)) or "（没有）"
    rv = "\n".join(f"- {d['title']}：本地规则建议{d['local_verdict'] or '-'}，AI 建议{d['ai_verdict'] or '-'}，"
                   f"最后选{d['chosen'] or '-'}；结果：{d['outcome'] or '-'}；谁更准：{d['who_right'] or '-'}"
                   for d in decisions() if d["status"] == "reviewed") or "（没有）"
    r = decision_rules()
    tunable = {k: r[k] for k in ("accept", "negotiate", "load_per_task", "hours_per_day", "review_days") if k in r}
    tunable["weights"] = r["weights"]
    lessons = PRIVATE_BLOCK.sub("", LESSONS_FILE.read_text(encoding="utf-8")) if LESSONS_FILE.exists() else ""
    lessons = re.sub(r"^---\n.*?\n---\n", "", lessons, flags=re.S)
    text = (UPGRADE_PROMPT.replace("{feedback}", fb).replace("{reviews}", rv)
            .replace("{rules}", json.dumps(tunable, ensure_ascii=False)).replace("{lessons}", lessons.strip()))
    check_outgoing(text)
    return text


def upgrade_run(provider_id=None):
    raw = call_model(system_prompt(), [{"role": "user", "content": upgrade_payload()}], active_provider(provider_id))
    out = parse_json_block(raw)
    r = decision_rules()
    changes = []
    for c in out.get("rule_changes", []):
        k = c.get("key", "")
        if k not in TUNABLE:
            continue
        cur = r["weights"].get(k.split(".", 1)[1]) if k.startswith("weights.") else r.get(k)
        changes.append({"key": k, "from": cur, "to": c.get("to"), "reason": c.get("reason", "")})
    out["rule_changes"] = changes
    return out


def upgrade_apply(lessons, changes, removes, summary=""):
    decision_rules()  # 规则文件格式坏了先报错，免得经验写进去了、规则却没改
    # 经验教训
    text = LESSONS_FILE.read_text(encoding="utf-8")
    text = text.replace("- （还没有。做几次决定、回看几次结果后，这里会慢慢积累。）\n", "")
    for old in removes:
        text = text.replace(f"- {old}\n", "")
    for l in lessons:
        check_outgoing(l)
        text = text.rstrip("\n") + f"\n- {l.strip()}（{today()}）\n"
    LESSONS_FILE.write_text(_set_fm(text, "updated", today()), encoding="utf-8")
    # 打分规则
    md = _rules_md()
    m = re.search(r"```json\s*(\{.*?\})\s*```", md, re.S)
    r = json.loads(m.group(1))
    applied = []
    for c in changes:
        k, v = c["key"], _num(c["to"], None)
        if k not in TUNABLE or v is None:
            continue
        v = int(v) if v == int(v) else v
        if k.startswith("weights."):
            r["weights"][k.split(".", 1)[1]] = v
        else:
            r[k] = v
        applied.append(f"{k} → {v:g}")
    md = md[:m.start(1)] + json.dumps(r, ensure_ascii=False, indent=2) + md[m.end(1):]
    if "## 升级记录" not in md:
        md = md.rstrip() + "\n\n## 升级记录\n"
    note = "；".join(applied) or "规则未改"
    md = md.rstrip() + f"\n- {today()} 升级：新增经验 {len(lessons)} 条，删除 {len(removes)} 条；{note}。{summary}\n"
    RULES_FILE.write_text(_set_fm(md, "updated", today()), encoding="utf-8")
    return {"lessons": len(lessons), "rules": applied}


# ---------- 待决策：定了就移走（记进近期事件），不想要了就删 ----------
def close_decision(match, result="", exact=False):
    key = re.sub(r"^建议：", "", _cell(match))
    if not key:
        raise RuntimeError("没说是哪条待决策。")
    text = DASHBOARD.read_text(encoding="utf-8")
    lines = text.splitlines()
    head = next((i for i, l in enumerate(lines) if l.startswith("|") and "| 决策 |" in l), None)
    if head is None:
        raise RuntimeError("决策端里没找到待决策表。")
    hits = []
    for j in range(head + 2, len(lines)):
        if not lines[j].startswith("|"):
            break
        c = [x.strip() for x in lines[j].strip().strip("|").split("|")]
        name = re.sub(r"^建议：", "", c[1]) if len(c) > 1 else ""
        if name and (name == key if exact else key in name):
            hits.append((j, c))
    if len(hits) != 1:
        raise RuntimeError(f"含“{key}”的待决策有 {len(hits)} 条，没法确定是哪条。")
    j, c = hits[0]
    name = re.sub(r"^建议：", "", c[1])
    lines.pop(j)
    text = "\n".join(lines) + "\n"
    result = _cell(result)
    if result:
        link = c[3] if len(c) > 3 else ""
        text = _insert_row(text, "| 事件 |", f"| {today()} | 定了：{name[:60]} → {result} |  | {link} |")
    _write(DASHBOARD, _set_fm(text, "updated", today()))
    return f"待决策{'定了' if result else '删掉了'}：{name[:40]}"


# ---------- 每日建议：AI 结合进度、目标和长期方向，给几条能直接采纳的建议 ----------
SUGGEST_DIR = BRIEFS / "Suggest"
SUGGEST_PROMPT = """今天是 {today}。请结合我的情况，给我一份今天的建议报告。

除了眼前的任务，也想想我可能感兴趣、或者对我长期有利的方向（学业、技能、收入、人脉、健康），从知识库里的目标和经历推断，推断的要说明是推断。
不要重复我已经在做的任务；每条都要具体到这周能开始做。

=== 本地计算的事实 ===
{facts}

只输出一个 JSON，不要别的文字：
{{"summary":"一两句话：今天整体该怎么安排",
 "items":[{{"title":"建议做什么，一句话，20 字以内","why":"为什么对我有利，依据哪份资料，一两句","kind":"todo 或 decision 或 idea","priority":"P0|P1|P2|P3","area":"学业|项目|收入|技能|人脉|生活"}}]}}
items 给 3 到 5 条。kind：马上能做的小事是 todo，要我拍板的是 decision，值得记下以后再看的是 idea。"""


def suggest_today():
    f = SUGGEST_DIR / f"{today()}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except ValueError:
        return None


def make_suggest(provider_id=None):
    text = SUGGEST_PROMPT.format(today=today(), facts=brief_facts())
    check_outgoing(text)
    out = parse_json_block(call_model(system_prompt(), [{"role": "user", "content": text}], active_provider(provider_id), 1500))
    items = [{"title": _cell(x.get("title"))[:60], "why": _cell(x.get("why"))[:200],
              "kind": x.get("kind") if x.get("kind") in ("todo", "decision", "idea") else "idea",
              "priority": x.get("priority") if x.get("priority") in ("P0", "P1", "P2", "P3") else "P2",
              "area": _cell(x.get("area"))[:6], "state": ""} for x in (out.get("items") or []) if isinstance(x, dict) and x.get("title")][:6]
    if not items:
        raise RuntimeError("AI 没给出建议，再试一次。")
    data = {"date": today(), "summary": _cell(out.get("summary"))[:300], "items": items}
    SUGGEST_DIR.mkdir(parents=True, exist_ok=True)
    (SUGGEST_DIR / f"{today()}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def mark_suggest(day, i, state):
    """采纳：按种类写进待办 / 待决策（想法按 P3 进零散待办）；不要：只记下来。"""
    f = SUGGEST_DIR / f"{day}.json"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(day)) or not f.exists():
        raise RuntimeError("找不到这天的建议。")
    data = json.loads(f.read_text(encoding="utf-8"))
    if not 0 <= i < len(data["items"]):
        raise RuntimeError("建议已经变了，请刷新。")
    x = data["items"][i]
    msg = "不采纳：" + x["title"]
    if state == "adopted":
        t = "add_decision" if x["kind"] == "decision" else "add_todo"  # 以后再看的想法：按 P3 放进零散待办
        msg = apply_action({"type": t, "text": x["title"], "priority": "P3" if x["kind"] == "idea" else x["priority"]})
    x["state"] = state
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return msg
