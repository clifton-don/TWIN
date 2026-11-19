# twin_ai 的一部分：接单评估：本地规则打分 + AI 第二意见。
# 不单独 import：twin_ai.py 末尾把这个文件放进它自己的命名空间里执行，和写在 twin_ai.py 里完全一样，
# 直接用那里的函数和变量（ROOT、_write、call_model……），外面照旧用 twin_ai.xxx。
# flake8: noqa

# ---------- 接单评估：本地规则打分 ----------
def decision_rules():
    ensure_rule_files()
    m = re.search(r"```json\s*(\{.*?\})\s*```", RULES_FILE.read_text(encoding="utf-8"), re.S)
    try:
        return json.loads(m.group(1))
    except (AttributeError, ValueError):
        raise RuntimeError("_RULES/Decision_Rules.md 里的 json 格式有误，请检查。") from None


def open_tasks():
    """未完成的 P0/P1 零散待办数。"""
    return sum(1 for t in todos()[0] if not t["done"] and t["priority"] in ("P0", "P1"))


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def local_score(job):
    r = decision_rules()
    price, hours = _num(job.get("price")), _num(job.get("hours"))
    rating = {k: min(max(int(_num(job.get(k), 3)), 1), 5) for k in ("learning", "alignment", "clarity")}
    hourly = price / hours if hours > 0 else 0
    ratio = hourly / r["target_hourly"] if r["target_hourly"] else 0
    tasks = open_tasks()
    scores = {
        "pay": round(min(ratio, 1) * 100),
        "learning": (rating["learning"] - 1) * 25,
        "alignment": (rating["alignment"] - 1) * 25,
        "clarity": (rating["clarity"] - 1) * 25,
        "load": max(0, 100 - r["load_per_task"] * tasks),
    }
    w = r["weights"]
    total = round(sum(scores[k] * w[k] for k in scores) / sum(w.values()))
    flags = []
    if hours <= 0 or price <= 0:
        flags.append("报价或工时没填，报酬分按 0 算")
    elif hourly < r["min_hourly"]:
        flags.append(f"时薪只有底线的 {hourly / r['min_hourly']:.0%}")
    if not job.get("deposit") and not job.get("contract"):
        flags.append("没有定金也没有书面约定")
    if job.get("deadline") and hours > 0:
        try:
            days = (dt.date.fromisoformat(job["deadline"]) - dt.date.today()).days
            need = hours / r["hours_per_day"]
            if days < need:
                flags.append(f"工期紧：按每天 {r['hours_per_day']} 小时要 {need:.0f} 天，只剩 {days} 天")
        except ValueError:
            pass
    hard = rating["clarity"] <= 2 and scores["pay"] < 50
    if hard:
        flags.append("命中你的硬规则：需求不清且报酬低")
    verdict = "不接" if hard else ("接" if total >= r["accept"] else "谈条件后接" if total >= r["negotiate"] else "不接")
    return {"scores": scores, "weights": w, "total": total, "verdict": verdict, "flags": flags,
            "hourly_ratio": round(ratio, 2), "open_tasks": tasks}


# ---------- 接单评估：AI 第二意见 ----------
JOB_PROMPT = """下面是一个待评估的接单需求。请独立判断，然后只输出一个 json 代码块，字段如下：
{"verdict": "接 | 谈条件后接 | 不接",
 "hours_estimate": 你自己估的工时（数字，小时）,
 "hours_reason": "工时估算依据，一两句",
 "quote_adjust_pct": 建议报价相对当前报价上调或下调的百分比（数字，可为负）,
 "similar_projects": ["知识库项目索引里做过的类似项目名，没有就空"],
 "reusable": ["可复用的模块或经验"],
 "risks": ["风险"],
 "assumptions": ["你做的假设"],
 "missing_info": ["还需要向客户问清的问题"],
 "confidence": "高 | 中 | 低",
 "summary": "三句话以内的结论和理由"}

注意：为保护隐私，报价只给你“时薪相对他理想时薪的比例”，不给具体金额。

需求描述：
{desc}

他自己的估计：工时 {hours} 小时；时薪是理想时薪的 {ratio}；截止日期 {deadline}；
有定金：{deposit}；有书面约定：{contract}；
他自评（1–5 分）：学习价值 {learning}，方向对齐 {alignment}，需求清晰度 {clarity}。
他手上未完成的 P0/P1 待办：{tasks} 件。
本地规则打分：总分 {total}/100，建议“{verdict}”，提示：{flags}。"""


def parse_json_block(text):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise RuntimeError("AI 没有按格式返回，原文：" + text[:300])
    return json.loads(m.group(1))


def ai_opinion(job, local, provider_id=None):
    desc = job.get("desc", "").strip()
    check_outgoing(desc)
    fill = {"desc": desc or "（未提供）", "hours": job.get("hours") or "未填",
            "ratio": f"{local['hourly_ratio']:.0%}", "deadline": job.get("deadline") or "未填",
            "deposit": "是" if job.get("deposit") else "否", "contract": "是" if job.get("contract") else "否",
            "learning": job.get("learning", 3), "alignment": job.get("alignment", 3),
            "clarity": job.get("clarity", 3), "tasks": local["open_tasks"], "total": local["total"],
            "verdict": local["verdict"], "flags": "；".join(local["flags"]) or "无"}
    prompt = JOB_PROMPT
    for k, v in fill.items():  # 模板里有 json 花括号，不能用 str.format
        prompt = prompt.replace("{" + k + "}", str(v))
    raw = call_model(system_prompt(), [{"role": "user", "content": prompt}], active_provider(provider_id))
    ai = parse_json_block(raw)
    diffs = []
    if ai.get("verdict") and ai["verdict"] != local["verdict"]:
        diffs.append(f"结论不同：本地规则建议“{local['verdict']}”，AI 建议“{ai['verdict']}”")
    est, mine = _num(ai.get("hours_estimate")), _num(job.get("hours"))
    if est and mine and abs(est - mine) / mine > 0.4:
        diffs.append(f"工时估计差得多：你估 {mine:g} 小时，AI 估 {est:g} 小时")
    return {"ai": ai, "diffs": diffs}


LABELS = {"pay": "报酬", "learning": "学习价值", "alignment": "方向对齐", "clarity": "需求清晰", "load": "当前负荷"}


def save_job_decision(job, local, opinion):
    r = decision_rules()
    DECISIONS.mkdir(exist_ok=True)
    name = f"{today()}_Job.md"
    path = DECISIONS / name
    n = 2
    while path.exists():
        path = DECISIONS / name.replace(".md", f"_{n}.md")
        n += 1
    ai = (opinion or {}).get("ai", {})
    review = (dt.date.today() + dt.timedelta(days=r.get("review_days", 30))).isoformat()
    lines = lambda xs: "\n".join(f"- {x}" for x in xs) or "- 无"
    title = job.get("title") or "接单评估"
    text = f"""---
type: decision
title: {title}
date: {today()}
priority: P1
status: open
options: ["接", "谈条件后接", "不接"]
chosen: ""
local_verdict: {local['verdict']}
local_score: {local['total']}
ai_verdict: {ai.get('verdict', '')}
ai_confidence: {ai.get('confidence', '')}
review_date: {review}
outcome: ""
updated: {today()}
privacy: internal
---
# {title}

## 背景
{job.get('desc', '').strip() or '（未填）'}

<!-- private -->
- 报价：{job.get('price') or '未填'} 元；预计工时：{job.get('hours') or '未填'} 小时
<!-- /private -->
- 截止：{job.get('deadline') or '未填'}；定金：{'有' if job.get('deposit') else '无'}；书面约定：{'有' if job.get('contract') else '无'}

## 本地规则打分（不经过 AI）
总分 **{local['total']}/100**，建议 **{local['verdict']}**
| 项目 | 分数 | 权重 |
|---|---|---|
""" + "\n".join(f"| {LABELS[k]} | {v} | {local['weights'][k]} |" for k, v in local["scores"].items()) + f"""

提示：
{lines(local['flags'])}

## AI 第二意见
建议 **{ai.get('verdict', '未获取')}**，置信度 {ai.get('confidence', '-')}。{ai.get('summary', '')}
- AI 估工时：{ai.get('hours_estimate', '-')} 小时（{ai.get('hours_reason', '')}）
- 建议报价调整：{ai.get('quote_adjust_pct', '-')}%

类似项目：
{lines(ai.get('similar_projects', []))}

风险：
{lines(ai.get('risks', []))}

假设：
{lines(ai.get('assumptions', []))}

要问清的问题：
{lines(ai.get('missing_info', []))}

## 分歧
{lines((opinion or {}).get('diffs', []))}

## 最终决定和理由
（你来填：选了什么，为什么。）

## 事后回看（{review}）
（到期时填：结果如何，当时的判断对不对，本地规则和 AI 谁更准。）
"""
    path.write_text(text, encoding="utf-8")
    return path.relative_to(ROOT).as_posix()
