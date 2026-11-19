#!/usr/bin/env python3
"""知识库的 AI 部分（只用 Python 标准库）。被 twin_web.py 调用。

设计原则：AI 全面参与，但不替你做决定。
  - 能用规则算的先在本地算（不经过 AI），AI 只给第二意见。
  - AI 必须写出依据、假设、置信度和缺少的信息；和本地规则对不上时标出分歧。
  - 发给云端的只有 public 摘要层（同 twin.py pack），金额只发比例不发数值。
  - API key 存在电脑用户目录 ~/.twin/ai.json，不在知识库里，读知识库的 AI 看不到。
"""
import datetime as dt
import json
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

from twin import (SENSITIVE, SKIP_SUBDIRS, project_dirs, PACK_HEADER, PRIVATE_BLOCK, ROOT, find_sensitive, mask, md_files, privacy_of,
                  public_context)

CONFIG_FILE = Path.home() / ".twin" / "ai.json"
RULES_FILE = ROOT / "_RULES" / "Decision_Rules.md"
LESSONS_FILE = ROOT / "_RULES" / "Lessons.md"
DECISIONS = ROOT / "07_Decisions"
FEEDBACK_FILE = DECISIONS / "Feedback_Log.md"
DASHBOARD = ROOT / "00_Crown" / "Dashboard.md"

# 常用服务商。模型名可以在设置页改；大多数家都兼容 OpenAI 的接口格式。
PRESETS = [
    {"name": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    {"name": "Kimi（月之暗面）", "kind": "openai", "base_url": "https://api.moonshot.cn/v1", "model": "kimi-latest"},
    {"name": "通义千问", "kind": "openai", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    {"name": "智谱 GLM", "kind": "openai", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-plus"},
    {"name": "豆包（火山方舟）", "kind": "openai", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "填你的接入点 ID"},
    {"name": "OpenAI", "kind": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4.1"},
    {"name": "Claude", "kind": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-5-5"},
    {"name": "Gemini", "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash"},
    {"name": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-chat"},
    {"name": "本地 Ollama", "kind": "openai", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b"},
]

RATIONAL_RULES = """你是{name}的决策参谋，不是决策者。最终由{name}拍板。
回答时必须遵守：
1. 只依据下面提供的知识库资料和他本次给的信息。资料里没有的，直接写“资料中没有”，不要编造。
2. 每个结论都写出依据，引用资料的文件名。
3. 写出你做了哪些假设、置信度（高 / 中 / 低）、还缺哪些信息才能更确定。
4. 不迎合。如果他的倾向和资料、他自己定的原则或过去的经验教训矛盾，直接指出来。
5. 遵守知识库里的 AI 访问规则：私密段落不推测；看到 {{VAULT:名称}} 占位符只当作“这里有一个敏感值”，不索取真实值。
6. 用中文，先给结论，再给理由。简洁，不说客套话。
例外：他明确让你加、改、记、存某样东西（链接、任务、资产、笔记等）时，以上 2、3 条格式不用，按后面“动作”规则直接附上对应动作，一两句话说明即可。链接、文件位置是他自己的资料，不用提醒共享范围。"""

DEFAULT_RULES_MD = """---
type: rule
updated: {today}
privacy: internal
---
# 决策规则（本地打分用）

> 网页的接单评估按这里的数值在本地打分，不经过 AI。改数值就能改评分标准。
> 每周“复盘升级”时，AI 会根据你的反馈和决策结果建议怎么调，你同意后才会改。
> 本文件是 internal，不上传云端。

```json
{{
  "target_hourly": 150,
  "min_hourly": 60,
  "hours_per_day": 4,
  "load_per_task": 12,
  "weights": {{"pay": 30, "learning": 25, "alignment": 20, "clarity": 15, "load": 10}},
  "accept": 70,
  "negotiate": 50,
  "review_days": 30
}}
```

## 字段说明
- `target_hourly`：理想时薪（元/小时）。达到它，报酬分就是满分。**请改成你自己的数。**
- `min_hourly`：底线时薪，低于它直接标红。
- `hours_per_day`：副业每天大约能投入几小时，用来判断工期紧不紧。
- `load_per_task`：手上每多一件未完成的 P0/P1 待办，负荷分扣多少。
- `weights`：五项的权重。报酬、学习价值、方向对齐、需求清晰度、当前负荷。
- `accept` / `negotiate`：总分到多少建议接、到多少建议谈条件后再接，低于就不接。
- `review_days`：决定做出后多少天提醒你回看结果。

## 硬规则（来自 [[Vision]] 的原则，命中直接建议不接）
- 需求不清（清晰度 ≤ 2）并且报酬分低于 50。
"""

DEFAULT_LESSONS_MD = """---
type: rule
updated: {today}
privacy: public
---
# 经验教训（AI 每次给建议前都会读）

> 来自决策复盘和你对 AI 回答的反馈。每周“复盘升级”时由 AI 提出新增或修改，你同意后写入。
> 只写结论，不写金额、客户名等细节。

- （还没有。做几次决定、回看几次结果后，这里会慢慢积累。）
"""


def today():
    return dt.date.today().isoformat()


# ---------- 配置 ----------
def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"providers": [], "active": ""}


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def public_config():
    """给网页看的配置：key 只显示首尾几位。"""
    cfg = load_config()
    providers = [{**p, "api_key": mask(p["api_key"]) if p.get("api_key") else ""} for p in cfg["providers"]]
    return {"providers": providers, "active": cfg.get("active", ""), "presets": PRESETS,
            "config_path": str(CONFIG_FILE)}


def update_config(body):
    cfg = load_config()
    old = {p["id"]: p for p in cfg["providers"]}
    providers = []
    for p in body.get("providers", []):
        pid = p.get("id") or f"p{dt.datetime.now().strftime('%H%M%S%f')}"
        key = p.get("api_key", "")
        if pid in old and ("*" in key or not key):
            key = old[pid].get("api_key", "")  # 网页上显示的是打码值，没改就保留原 key
        providers.append({"id": pid, "name": p.get("name", ""), "kind": p.get("kind", "openai"),
                          "base_url": p.get("base_url", "").rstrip("/"), "model": p.get("model", ""),
                          "api_key": key})
    cfg = {"providers": providers, "active": body.get("active") or (providers[0]["id"] if providers else "")}
    save_config(cfg)
    return public_config()


def active_provider(pid=None):
    cfg = load_config()
    pid = pid or cfg.get("active")
    for p in cfg["providers"]:
        if p["id"] == pid:
            return p
    raise RuntimeError("还没有设置 AI。请到“设置”里添加一家服务商并填 API key。")


# ---------- 调用模型 ----------
def _post(url, headers, payload, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"AI 服务返回错误 {e.code}：{detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"连不上 AI 服务：{e.reason}。检查网络或服务地址。") from None


LANG = threading.local()  # 界面语言，每个请求由 twin_web 设置


def _lang(system):
    if getattr(LANG, "v", "") != "en":
        return system
    return system + "\n\nThe user's interface is in English. Write every user-facing sentence (replies, task names, notes, summaries) in English. Keep JSON keys, action types, file paths and code exactly as specified above."


def call_model(system, messages, provider=None, max_tokens=4000):
    p, system = provider or active_provider(), _lang(system)
    if p["kind"] == "anthropic":
        data = _post(p["base_url"] + "/v1/messages",
                     {"x-api-key": p["api_key"], "anthropic-version": "2023-06-01"},
                     {"model": p["model"], "max_tokens": max_tokens, "system": system, "messages": messages})
        return "".join(b.get("text", "") for b in data.get("content", []))
    headers = {"Authorization": f"Bearer {p['api_key']}"} if p.get("api_key") else {}
    data = _post(p["base_url"] + "/chat/completions", headers,
                 {"model": p["model"], "temperature": 0.3, "max_tokens": max_tokens,
                  "messages": [{"role": "system", "content": system}] + messages})
    return data["choices"][0]["message"]["content"]


def call_model_stream(system, messages, provider=None, max_tokens=4000):
    """边生成边返回（逐字显示用）。服务商不支持流式时退回一次性返回。"""
    p, system = provider or active_provider(), _lang(system)
    if p["kind"] == "anthropic":
        url, headers = p["base_url"] + "/v1/messages", {"x-api-key": p["api_key"], "anthropic-version": "2023-06-01"}
        payload = {"model": p["model"], "max_tokens": max_tokens, "system": system, "messages": messages, "stream": True}
    else:
        url = p["base_url"] + "/chat/completions"
        headers = {"Authorization": f"Bearer {p['api_key']}"} if p.get("api_key") else {}
        payload = {"model": p["model"], "temperature": 0.3, "max_tokens": max_tokens, "stream": True,
                   "messages": [{"role": "system", "content": system}] + messages}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "text/event-stream", **headers})
    try:
        r = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        if e.code in (400, 404, 405, 422):  # 不支持 stream 参数的服务
            yield call_model(system, messages, p, max_tokens)
            return
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"AI 服务返回错误 {e.code}：{detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"连不上 AI 服务：{e.reason}。检查网络或服务地址。") from None
    with r:
        if "event-stream" not in (r.headers.get("Content-Type") or ""):
            data = json.loads(r.read().decode("utf-8"))  # 服务没理会 stream，直接给了整段
            yield ("".join(b.get("text", "") for b in data.get("content", [])) if p["kind"] == "anthropic"
                   else data["choices"][0]["message"]["content"])
            return
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                ev = json.loads(body)
            except ValueError:
                continue
            if p["kind"] == "anthropic":
                if ev.get("type") == "content_block_delta":
                    yield ev.get("delta", {}).get("text", "")
                elif ev.get("type") == "error":
                    raise RuntimeError(f"AI 服务出错：{ev.get('error', {}).get('message', '')}")
            else:
                for ch in ev.get("choices", []):
                    t = (ch.get("delta") or {}).get("content")
                    if t:
                        yield t


# ---------- 上下文 ----------
def ensure_rule_files():
    if not RULES_FILE.exists():
        RULES_FILE.write_text(DEFAULT_RULES_MD.format(today=today()), encoding="utf-8")
    if not LESSONS_FILE.exists():
        LESSONS_FILE.write_text(DEFAULT_LESSONS_MD.format(today=today()), encoding="utf-8")


def context_text():
    """可以上云的知识库内容。有被拦截的文件时直接报错，不带病上传。"""
    out, blocked = public_context()
    if blocked:
        names = "、".join(str(rel) for rel, _ in blocked)
        raise RuntimeError(f"这些公开文件里有疑似敏感值，已停止发送：{names}。请先点“隐私检查”处理。")
    return PACK_HEADER + "".join(out)


def board_facts():
    """各项目的进度摘要，本地算好再发：项目名、完成数、过期件数、截止，加上过期和最近 2 件任务的名字。备注、原因不发。"""
    out = []
    for b in boards():
        nd = "未定" if b["next_days"] is None else (f"已过期 {-b['next_days']} 天" if b["next_days"] < 0 else f"还剩 {b['next_days']} 天")
        out.append(f"- {re.split(r'[（(]', b['name'])[0].strip()}（{b['priority']}）：完成 {b['done']}/{b['total']}，"
                   f"过期 {b['overdue']} 件，最近一步截止 {nd}，最终截止 {b['due'] or '未定'}")
        # 用户同意（2026-10-21）：过期任务和最近 2 件任务的名字、截止可以发；备注和原因不发
        late = [t for t in b["open"] if t["days"] is not None and t["days"] < 0]
        soon = sorted([t for t in b["open"] if t not in late], key=lambda t: t["days"] if t["days"] is not None else 999)[:2]
        pushed = [t for t in b["open"] if len(t["pushes"]) >= 2 and t not in late + soon]  # 截止一再往后推的，也让 AI 知道
        for t in late + soon + pushed:
            if find_sensitive(t["task"]):
                continue  # 任务名里像有敏感值就不发
            when = "未定" if t["days"] is None else (f"过期 {-t['days']} 天" if t["days"] < 0 else f"还剩 {t['days']} 天")
            out.append(f"  - {t['task']}（{t['status']}，{when}" + (f"，截止已往后推 {len(t['pushes'])} 次" if len(t["pushes"]) >= 2 else "") + "）")
    return "\n".join(out)


def system_prompt():
    try:
        facts = board_facts()
    except Exception:  # noqa: BLE001  进度算不出来不影响对话
        facts = ""
    try:
        import twin_cards
        people = twin_cards.people_for_ai()
    except Exception:  # noqa: BLE001
        people = ""
    return (rules_text() + f"\n\n今天是 {today()}。\n\n=== 各项目进度（本地计算，准确；含过期和最近要做的任务名）===\n"
            + (facts or "（没有）")
            + ("\n\n=== 人脉摘要（他选了给你看的人；联系方式你没有，别编。找人合作、问谁能帮忙时可以点名推荐）===\n" + people if people else "")
            + "\n\n=== 知识库资料（摘要层）===\n" + context_text())


def check_outgoing(text):
    hits = find_sensitive(PRIVATE_BLOCK.sub("", text))
    if hits:
        raise RuntimeError("你输入的内容里有疑似敏感信息（" + "、".join(f"{n} {mask(v)}" for n, v in hits)
                           + "），没有发送。请删掉或换成 {{VAULT:名称}}。")


CHAT_RULES = """
补充：先判断问题类型。
- 闲聊或一般问题（推荐游戏、查知识、写段文字等）：像普通 AI 助手一样自然回答，不用上面的结论/依据/置信度格式，也不用硬扯知识库。可以结合他的爱好和情况推荐。
- 和他的工作、学习、项目、钱、时间安排有关的决定：严格按上面 1–6 条回答。

他也会直接说发生了什么（比如“那个单子交付了”“明天要交初稿”）。如果需要写进知识库，在回答最后附一个代码块，语言标记为 twin-actions，内容是 JSON 数组，每项一个动作。网页会让他逐条确认后才写入，所以只在确实需要时提出，不要重复已有的条目。可用动作：
- {"type":"add_todo","text":"事项","priority":"P0|P1|P2|P3","due":"YYYY-MM-DD 或空","link":"关联，可空"}
- {"type":"complete_todo","match":"待办里能唯一定位的几个字"}
- {"type":"reopen_todo","match":"已打钩待办里的几个字"}
- {"type":"todo_rename","match":"待办里的几个字","text":"新的内容"}
- {"type":"todo_due","match":"待办里的几个字","due":"YYYY-MM-DD 或空"}
- {"type":"todo_priority","match":"待办里的几个字","priority":"P0|P1|P2|P3"}
- {"type":"todo_delete","match":"待办里的几个字"}
- {"type":"add_event","text":"事件","impact":"对决策的影响","link":"可空"}
- {"type":"add_idea","text":"对 TWIN 这个工具本身的改进建议，一句话：缺什么功能、哪里不顺手"}（只在他抱怨 TWIN 不好用，或者你想帮他做某件事却发现没有对应动作时用。记进建议池，不是待办；他自己生活、项目上的想法用 add_todo，优先级 P3）
- {"type":"idea_remove","match":"建议池里某一条的关键词"}（汇总建议池时，重复的、已经做了的、过时的，从建议池拿掉）
- {"type":"add_decision","text":"要做的决定","priority":"P0|P1|P2","due":"可空"}
- {"type":"decision_close","match":"待决策里的几个字","result":"怎么定的，一句话；只是不想要了就留空"}  （他说某件事定了或不用决定了。定了的会记进“近期事件”，留空就直接删掉）
- {"type":"update_goal","match":"目标名里的几个字","current":"新的当前值"}
- {"type":"task_done","project":"项目名里的几个字","match":"任务里能唯一定位的几个字"}  （项目板块里的任务做完了）
- {"type":"task_add","project":"项目名","text":"新任务","priority":"P0|P1|P2","due":"YYYY-MM-DD 或空","note":"细节，可空"}
- {"type":"task_due","project":"项目名","match":"任务里的几个字","due":"YYYY-MM-DD 或空"}
- {"type":"project_priority","project":"项目名","priority":"P0|P1|P2|P3"}  （调整整个项目的优先级）
- {"type":"project_due","project":"项目名","due":"YYYY-MM-DD 或空"}  （改项目的最终截止）
- {"type":"project_status","project":"项目名","status":"active|paused|done|dropped|archived"}  （开始、暂停、做完、放弃、归档。不是 active 的项目不进“接下来”，也从总览表拿掉。他说项目结束了、做完了才用；只是任务全打完勾时不要自己加，在回答里问一句要不要标成已完成）
- {"type":"project_link","project":"项目名","name":"链接叫什么，比如 在线进度表","url":"https://…"}  （给项目存一个常用链接：在线进度表、仓库、网盘、提交地址。存进 board.md 的“## 链接”，项目页顶上一点就能打开。同一个地址再提一次就是改名字）
- {"type":"project_create","parent":"放在哪个目录（从目录列表里选，比如 03_Projects 下面的某个分类）","folder":"文件夹名，英文或拼音加下划线","name":"项目名","priority":"P0|P1|P2","due":"YYYY-MM-DD 或空","goal":"一句话目标","why":"为什么这个优先级","tasks":[{"text":"任务","priority":"P1","due":""}]}
  （新建项目板块。03_Projects 里的项目会一起建 index.md 和 01_code / 02_docs / 03_materials）
- {"type":"task_reopen","project":"项目名","match":"已完成任务里的几个字"}  （做完的任务改回没做完）
- {"type":"task_priority","project":"项目名","match":"任务里的几个字","priority":"P0|P1|P2|P3"}
- {"type":"task_rename","project":"项目名","match":"任务里的几个字","text":"新的任务名","note":"新备注，不改就不写这个字段"}
- {"type":"task_delete","project":"项目名","match":"任务里的几个字"}  （任务不要了、重复了）
- {"type":"task_merge","project":"项目名","matches":["任务A里的几个字","任务B里的几个字"],"text":"合并后的任务名"}  （几条同一件事的任务合成一条：原来的变成子任务，进度不丢，优先级取最高、截止取最早。他说“整合、合并、归成一条”就用这个，不要用改名+删除）
- {"type":"subtask_add","project":"项目名","match":"任务里的几个字","items":["子任务1","子任务2"]}  （给一条任务拆小步骤）
- {"type":"project_profile","project":"项目名","section":"场景|需求|现状|硬件与参数|决定","items":["一句话一条，写事实"]}  （把聊天里确认的项目真实情况记进项目画像，越聊越清楚。只记他说的真实情况和新需求，不记猜测和你的建议）
- {"type":"subtask_done","project":"项目名","match":"任务里的几个字","sub":"子任务里的几个字"}  （做完了其中一步。子任务全做完任务自动完成，做了一部分自动变进行中）
  他说某个项目的进展时，优先用这几个动作更新对应项目的任务，而不是只记一件事。
- {"type":"job_eval","title":"标题","desc":"需求摘要，不含联系方式","deadline":"YYYY-MM-DD 或空","learning":1-5,"alignment":1-5,"clarity":1-5}
  （他发来一个接单需求时用。报价和工时他会在本地卡片里自己填，不要问。）

他也可以让你帮忙整理文件和资料（下面会给你目录列表、暂存箱里的文件、资产清单的分类）。用这几个动作，同样要他确认：
- {"type":"file_move","from":"暂存箱里的文件名，或知识库里的相对路径","to_dir":"目录（只能从目录列表里选）","name":"新文件名，保留扩展名，可空"}
  项目相关的图片、PDF、资料放那个项目的 03_materials，文档放 02_docs，代码放 01_code；不是项目的按内容放到对应分支。
- {"type":"note_create","dir":"目录（只能从列表里选）","name":"文件名.md","title":"标题","text":"正文 markdown"}
  他让你“记下来”“整理成一篇”时用。正文写整理好的内容，不要编他没说过的事实。
- {"type":"note_append","path":"已有文档的相对路径","text":"要加的内容","heading":"小标题，可空"}
  往已有的非私密文档末尾补内容，比如项目的 02_docs 里的笔记。
- {"type":"add_asset","category":"资产分类的英文","name":"名称","model":"型号/配置，可空","acquired":"购入或起租时间，可空","status":"in_use|idle|lent|broken|sold","qty":"数量，可空","location":"放在哪 / 地址到区，可空","expires":"到期日 YYYY-MM-DD（租约、订阅、保修），可空","party":"对方：房东、卖家、服务商的称呼，可空","note":"用途或备注，会记进卡片的“记录”，可空"}
  他说买了、有了、租了什么时用。租房就用 category=lease，起租写 acquired，到期写 expires。价格、租金、押金都不要写，他会在本地卡片里自己填区间。
- {"type":"asset_update","match":"资产名字里的几个字","status":"in_use|idle|lent|broken|sold，可空","qty":"可空","location":"可空","expires":"可空","party":"可空","note":"发生了什么，可空"}
  他说东西卖了、坏了、借出去了、换地方了、续租了时用。资产内容你看不到，match 用他说的名字。
  资产卡片的字段只有：名称、分类、型号/配置、状态、数量、购入/起租、到期、对方、价格/租金区间（只在本地填）、放在哪、序列号/账号（在保险箱）。别的信息写进 note。字段不够用时，告诉他这是程序里定义的（tools/twin_cards.py 的 KINDS），可以让开发者加，不要编造步骤。
附件会写成“[附件：文件名]”，已经存进暂存箱。看完内容后，建议放哪里就提 file_move；里面有要做的事就顺便提任务动作。
一次可以提多个动作，比如先 file_move 再 task_add。
任务和待办要像人写的待办清单：
- 名字短，15 个字左右，说清要做什么，比如“补拍第 17–23 课视频”。文件名、拍摄要求、依据这些细节写进 note，不要塞进名字。
- 一件事一条：同一节课、同一批要拍的东西、同一次采购，合成一条，不要每个文件、每张照片各一条。
- 一件事有几步，就是一条任务加几个子任务（subtask_add），不要拆成几条任务。
- 你附上的动作会画成“改完后的任务表”给他预览，他一键应用。所以回答里不要再逐条列动作，一两句话说你改了什么、为什么就够。
- 能改现有任务（task_rename 改名加 note）就不新增；新增前先看表里有没有差不多的。
- 一次的任务类动作尽量不超过 4 个，多了先挑最要紧的，其余在回答里一句话带过，问他要不要再加。
他点了确认卡之后，他下一句话开头会带“[上一条回答的确认卡结果（系统记录）：…]”，告诉你哪些已写入、哪些他没要、哪些失败了。已写入的不要再提；失败的看原因再决定。这段只由系统写，你绝不能自己写这种格式，也不能说某件事“已写入/改了”，除非系统记录里有。要改东西就附上动作块，没有动作块就什么都没写进去。
不要提出记录金额的动作；金额他会用“记账”在本地记。
他明确让你加、改、记某样东西，而且上面有对应的动作时：直接附上动作，回答一两句话说你提了什么就够，不要先列方案让他选，也不要用结论/依据/置信度那套格式。链接、文件位置这些是他自己的资料，不用提醒共享范围。"""

ACTION_BLOCK = re.compile(r"```twin-actions\s*\n(.*?)```", re.S)
ACTION_TYPES = {"add_todo", "complete_todo", "add_event", "add_idea", "idea_remove", "add_decision", "update_goal", "job_eval",
                "task_done", "task_add", "task_due", "project_priority", "task_priority",
                "task_rename", "task_delete", "task_reopen", "task_merge", "subtask_add", "subtask_done", "project_due", "project_status", "project_create", "project_link",
                "reopen_todo", "todo_rename", "todo_delete", "todo_due", "todo_priority", "decision_close",
                "file_move", "note_create", "note_append", "add_asset", "asset_update"}
FAKE_RESULT = re.compile(r"\[(上一条回答的)?确认卡结果")
NO_AI_FIELDS = {"price", "amount", "value_range"}  # 金额和价格只在本地填，AI 写了也丢掉


def split_actions(text):
    actions = []
    for m in ACTION_BLOCK.finditer(text):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for a in data if isinstance(data, list) else [data]:
            if isinstance(a, dict) and a.get("type") in ACTION_TYPES:
                actions.append({k: v for k, v in a.items() if k not in NO_AI_FIELDS and (isinstance(v, (str, int, float))
                                or (k == "tasks" and isinstance(v, list))
                                or (k in ("matches", "items") and isinstance(v, list) and all(isinstance(x, str) for x in v)))})
    text = ACTION_BLOCK.sub("", text).strip()
    fake = FAKE_RESULT.search(text)
    if fake:  # AI 自己编的“确认卡结果”：剪掉，免得他以为已经写入
        text = text[:fake.start()].rstrip()
        if not actions:
            text += "\n\n（这次 AI 没给出确认卡，什么都没写入。可以说“把上面的动作提出来”让它重提。）"
    return text, actions


# ---------- 对话时附带的细节资料（用户 2026-10-21 同意：敏感信息以外的都可以给 AI）----------
DETAIL_BUDGET, FILE_CAP = 24000, 8000


def _clean(text):
    """去掉私密段落，把疑似身份证号、手机号、银行卡号、邮箱换成占位。"""
    text = PRIVATE_BLOCK.sub("[私密段落已移除]", text)
    for pat in SENSITIVE.values():
        text = pat.sub("[已隐藏]", text)
    return text


def detail_files():
    """可以随对话发出的细节文件：internal 级别的叶子 + 每个项目的板块、说明和文档。
    private / secret、人脉卡、模板、规则文件（含时薪）不发。"""
    out = []
    for p, rel in md_files():
        if rel.parts[0] in ("_TEMPLATES", "_RULES", "05_Network", "06_Assets"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if privacy_of(text) == "internal":
            out.append((rel.as_posix(), text))
    seen = {r for r, _ in out}
    for d in project_dirs():  # 所有项目（包括做完的）：板块、说明、文档，对话时按相关度挑，方便找相似项目、参考报价
        vers = [v for v in sorted(d.glob("V[0-9]*_*")) if v.is_dir()]  # 版本文件夹（V1_2024原版…）：各版的说明、总结和文档也读
        for f in [d / "board.md", d / "index.md", *sorted(d.glob("[0-9][0-9]_docs/*.md")),
                  *(f for v in vers for f in [*sorted(v.glob("*.md")), *sorted(v.glob("[0-9][0-9]_docs/*.md"))])]:
            if not f.exists() or f.relative_to(ROOT).as_posix() in seen:
                continue
            text = f.read_text(encoding="utf-8")
            pv = privacy_of(text)  # 没写密级的按 secret 算，只有你声明过的项目库（SKIP_SUBDIRS，比如 diy_mk）例外
            if pv in ("private", "secret") or (pv is None and not SKIP_SUBDIRS & set(f.relative_to(ROOT).parts)):
                continue
            out.append((f.relative_to(ROOT).as_posix(), text))
    return out


DETAIL_INDEX = None


def detail_context(messages):
    """任务板块全部带上；其余文件用本地相关度（BM25）挑和最近几句话最相关的，总量有上限。"""
    global DETAIL_INDEX
    from twin_search import Index, tokens
    recent = " ".join(m.get("content", "") for m in messages[-6:] if m.get("role") == "user")
    files_ = detail_files()
    bp = {b["path"] for b in boards()}
    texts = dict(files_)
    always = [r for r, _ in files_ if r in bp]
    rest = []
    q = tokens(recent)
    if q:
        DETAIL_INDEX = DETAIL_INDEX or Index()
        DETAIL_INDEX.refresh([{"path": r, "title": r} for r, _ in files_], max_age=0)
        scored = [(sc, r) for sc, r in DETAIL_INDEX.score(q, only=set(texts) - bp)]
        top = scored[0][0] if scored else 0
        # 只要明显相关的：分数够高，且不低于最相关那篇的三分之一
        rest = [r for sc, r in scored if sc >= 2.0 and sc >= top / 3][:8]
    out, used = [], 0
    for rel in always + rest:
        if used >= DETAIL_BUDGET:
            break
        body = _clean(re.sub(r"^---\n.*?\n---\n", "", texts[rel], flags=re.S)).strip()
        body = body[:FILE_CAP] + ("\n…（后面省略）" if len(body) > FILE_CAP else "")
        out.append(f"\n\n<!-- 文件：{rel} -->\n{body}")
        used += len(body)
    return "".join(out)


# ---------- 对话关联项目：手动选，或者在本地按对话内容自动匹配（不问 AI）----------
BOARD_INDEX = None


def _name_terms(name):
    """项目名里能用来认项目的词：比如“智能台灯 v2（客户单）”里的台灯、v2……"""
    short = re.split(r"[（(]", name)[0]
    out = set()
    for w in re.findall(r"[A-Za-z0-9]+|[一-鿿]+", short):
        if re.search(r"[一-鿿]", w):
            out.update(w[i:] for i in range(len(w) - 1))  # 中文取整段和后半截：万圣节南瓜 → 南瓜；天气站不会因“天气”误认
        elif len(w) >= 3 or re.search(r"\d", w) and len(w) >= 2:
            out.add(w.lower())
    return out - {"项目", "套件", "计划", "课程", "目标"}


def match_project(messages):
    """从最近几句话里认出说的是哪个项目。点名的（项目名里的词）优先，其次看和任务内容的相关度。认不准就返回空。"""
    global BOARD_INDEX
    from twin_search import Index, tokens
    bs = boards()
    users = [m.get("content", "") for m in messages if m.get("role") == "user"]
    for text in (users[-1] if users else "", " ".join(users[-3:])):
        if not text:
            continue
        low = text.lower()
        hits = sorted(((sum(len(t) for t in _name_terms(b["name"]) if t in low), b["path"]) for b in bs), reverse=True)
        if hits and hits[0][0] and (len(hits) == 1 or hits[0][0] > hits[1][0]):
            return hits[0][1]
        q = tokens(text)
        if not q:
            continue
        BOARD_INDEX = BOARD_INDEX or Index()
        BOARD_INDEX.refresh([{"path": b["path"], "title": b["name"]} for b in bs], max_age=0)
        sc = BOARD_INDEX.score(q, only={b["path"] for b in bs})
        if sc and sc[0][0] >= 3.0 and (len(sc) == 1 or sc[0][0] >= 1.6 * sc[1][0]):
            return sc[0][1]
    return ""


def project_context(rel, auto):
    """关联项目的未完成任务（任务名里像有敏感值的不发）和怎么用任务动作。"""
    b = board(rel)
    short = re.split(r"[（(]", b["name"])[0].strip()
    lines = []
    for t in b["tasks"]:
        if t["status"] == DONE or find_sensitive(t["task"]):
            continue
        when = "" if t["days"] is None else (f"，过期 {-t['days']} 天" if t["days"] < 0 else f"，还剩 {t['days']} 天")
        subs = [x for x in t["subs"] if not find_sensitive(x["text"])]
        sub = f"\n    子任务 {t['sub_done']}/{len(t['subs'])}：" + "；".join(("☑ " if x["done"] else "☐ ") + x["text"] for x in subs) if subs else ""
        lines.append(f"- [{t['status']}] {t['task']}（{t['priority'] or '无优先级'}{when}）{sub}")
    how = "按对话内容自动匹配的，不一定对：他明显在说别的项目时，以他说的为准" if auto else "他自己选的"
    prof = profile_text(rel)
    return (f"\n\n=== 这次对话关联的项目：{short}（{how}）===\n完成 {b['done']}/{b['total']}。未完成的任务：\n"
            + ("\n".join(lines) or "（没有）")
            + "\n项目画像（之前聊天里确认过的真实情况）：\n" + (prof or "（还没有）")
            + "\n他聊到这个项目真实存在的情况、新需求、定下来的做法、用的硬件和参数、使用场景，而画像里还没有或者变了的，附一个 project_profile 动作补进去；"
            "随口的设想、你自己的建议、已经写过的都不要提。"
            + f"\n他说的事没点名项目时，就是这个项目，任务动作的 project 填“{short}”。"
            "从他的话里判断任务进展并直接附上动作：说某件做完了、搞定了 → task_done；"
            "说到要做的新事而上面没有 → task_add（给合理的优先级，截止能推出来就填）。match 用任务名里能唯一定位的几个字。"
            "对不上具体任务就问一句，不要硬凑；只是随口聊到的不提动作。")


def resolve_project(messages, project):
    """project：空 = 自动匹配；"none" = 不关联；其余是项目板块的路径。返回 (路径, 是否自动)。"""
    if project == "none":
        return "", False
    if project:
        return (project, False) if project in {b["path"] for b in boards(True)} else ("", False)
    try:
        return match_project(messages), True
    except Exception:  # noqa: BLE001  认不出来就不关联
        return "", True


def _prepare(messages, project="", auto=False):
    for m in messages:
        if m.get("role") == "user":
            check_outgoing(m.get("content", ""))
    msgs = [{"role": m["role"], "content": m.get("content", "")} for m in messages[-30:] if m.get("role") in ("user", "assistant")]
    detail = detail_context(messages)
    import twin_org
    sys_ = system_prompt() + ("\n\n=== 项目细节资料（任务板块全部，加上和这次对话相关的文档；私密内容已移除）===" + detail if detail else "")
    sys_ += twin_org.context(messages)
    if project:
        sys_ += project_context(project, auto)
    return sys_ + CHAT_RULES, msgs


def ask(messages, provider_id=None, project=""):
    rel, auto = resolve_project(messages, project)
    sys_, msgs = _prepare(messages, rel, auto)
    answer, actions = split_actions(call_model(sys_, msgs, active_provider(provider_id)))
    return {"answer": answer, "actions": actions, "project": rel, "auto": auto}


def ask_stream(messages, provider_id=None, project=""):
    """逐字返回：先告诉网页关联了哪个项目，再一段段给文字，最后给整理好的 {answer, actions}。"""
    rel, auto = resolve_project(messages, project)
    yield {"project": rel, "auto": auto}
    sys_, msgs = _prepare(messages, rel, auto)
    full = ""
    for piece in call_model_stream(sys_, msgs, active_provider(provider_id)):
        full += piece
        yield {"delta": piece}
    answer, actions = split_actions(full)
    yield {"done": True, "answer": answer, "actions": actions}


# ---------- 对话里提出的写入动作（用户确认后才执行）----------
INCOME_LOG = ROOT / "06_Assets" / "03_Finance" / "Income_Log.md"
INCOME_MD = """---
type: finance
updated: {today}
privacy: private
---
# 收入记录

> 网页对话里用“记账”记的收入。只在本地，不发给 AI。

| 日期 | 金额（元） | 来源 | 备注 |
|---|---|---|---|
"""


def _cell(v):
    return str(v or "").replace("|", "／").replace("\n", " ").strip()


def _insert_row(text, header_word, row):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and header_word in line and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            # 去掉只有空格的占位行
            if j - 1 >= i + 2 and not lines[j - 1].strip("| \t"):
                lines.pop(j - 1)
                j -= 1
            lines.insert(j, row)
            return "\n".join(lines) + "\n"
    raise RuntimeError(f"没找到表头含“{header_word}”的表格，没有写入。")


def _touch(text):
    return _set_fm(text, "updated", today())


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


# 零散待办就是“零散待办”这个项目里的任务；AI 和按钮发来的旧待办动作都转成任务动作
TODO_ACTS = {"add_todo": "task_add", "complete_todo": "task_done", "reopen_todo": "task_reopen", "todo_rename": "task_rename",
             "todo_delete": "task_delete", "todo_due": "task_due", "todo_priority": "task_priority"}


def _as_list(v, fallback):
    """AI 给的字段是列表就用它，否则用 fallback。"""
    return v if isinstance(v, list) else fallback


def apply_action(a):
    t = a.get("type")
    if t in TODO_ACTS:
        ensure_loose()
        t = TODO_ACTS[t]
        a = {**a, "type": t, "project": LOOSE_NAME, "note": a.get("note") or a.get("link", ""),
             "priority": a.get("priority") or ("P2" if t == "task_add" else "")}
    if t in ("add_event", "add_decision"):
        text = DASHBOARD.read_text(encoding="utf-8")
    if t == "decision_close":
        return close_decision(a.get("match", ""), a.get("result", ""), bool(a.get("exact")))
    if t == "add_decision":
        pr = a.get("priority") if a.get("priority") in ("P0", "P1", "P2") else "P1"
        text = _insert_row(text, "| 决策 |", f"| {pr} | {_cell(a.get('text'))} | {_cell(a.get('due'))} |  |")
        msg = f"决策端待决策：{_cell(a.get('text'))}"
    elif t == "add_event":
        text = _insert_row(text, "| 事件 |", f"| {today()} | {_cell(a.get('text'))} | {_cell(a.get('impact'))} | {_cell(a.get('link'))} |")
        msg = f"决策端近期事件：{_cell(a.get('text'))}"
    elif t == "add_idea":
        return idea_add(a.get("text", ""))
    elif t == "update_goal":
        text, key = GOALS.read_text(encoding="utf-8"), _cell(a.get("match"))
        lines = text.splitlines()
        hits = [i for i, l in enumerate(lines) if l.startswith("|") and key and key in (l.split("|")[1] if l.count("|") > 2 else "")]
        if len(hits) != 1:
            raise RuntimeError(f"名字含“{key}”的目标有 {len(hits)} 个，没有修改。")
        cells = lines[hits[0]].split("|")
        cells[2] = f" {_cell(a.get('current'))} "
        lines[hits[0]] = "|".join(cells)
        _write(GOALS, _touch("\n".join(lines) + "\n"))
        return f"目标“{cells[1].strip()}”当前改为 {_cell(a.get('current'))}"
    elif t == "set_task":
        return set_task(str(a.get("path", "")), int(a.get("i", -1)), str(a.get("status", "")))
    elif t == "set_board_priority":
        return set_board_priority(str(a.get("path", "")), a.get("priority", ""))
    elif t == "set_task_priority":
        return set_task_priority(str(a.get("path", "")), int(a.get("i", -1)), a.get("priority", ""))
    elif t == "project_create":
        tasks = a.get("tasks") if isinstance(a.get("tasks"), list) else []
        rel = create_board(a.get("parent", ""), a.get("folder", ""), a.get("name", ""), a.get("priority", ""),
                           _iso(a.get("due", "")) if a.get("due") else "", a.get("goal", ""), a.get("why", ""), tasks)
        return f"新建了项目：{rel}"
    elif t in ("task_done", "task_add", "task_due", "project_priority", "task_priority", "task_rename", "task_delete",
               "task_reopen", "project_due", "project_status", "project_link", "task_merge", "subtask_add", "subtask_done", "project_profile"):
        rel, name = _find_board(a.get("project", ""))
        if t == "project_profile":
            items = [str(x).strip() for x in _as_list(a.get("items"), [a.get("text", "")]) if str(x).strip()]
            return f"{name}：" + add_profile(rel, a.get("section", ""), items)
        if t == "project_link":
            return f"{name}：" + set_board_link(rel, a.get("name", ""), a.get("url", ""))
        if t == "project_priority":
            return f"{name}：" + set_board_priority(rel, a.get("priority", ""))
        if t == "project_due":
            return f"{name}：" + set_board_due(rel, a.get("due", ""))
        if t == "project_status":
            return f"{name}：" + set_board_status(rel, a.get("status", ""))
        if t == "task_reopen":
            return f"{name}：" + set_task(rel, _find_task(rel, a.get("match", ""), done=True)["i"], TODO)
        if t == "task_add":
            return f"{name}：" + add_task(rel, a.get("text", ""), a.get("priority", ""), _iso(a.get("due", "")) if a.get("due") else "", a.get("note", ""))
        if t == "task_merge":
            ms = _as_list(a.get("matches"), [])
            return f"{name}：" + merge_tasks(rel, [str(x) for x in ms], a.get("text", ""), a.get("note") if "note" in a else None)
        tk = _find_task(rel, a.get("match", ""))
        if t == "subtask_add":
            items = [str(x).strip() for x in _as_list(a.get("items"), []) if str(x).strip()]
            have = {x["text"] for x in tk["subs"]}
            return f"{name}：" + set_subtasks(rel, tk["i"], tk["subs"] + [{"text": x, "done": False} for x in items if x not in have])
        if t == "subtask_done":
            subs = tk["subs"]
            subs[_sub_hit(subs, a.get("sub", ""))]["done"] = True
            return f"{name}：" + set_subtasks(rel, tk["i"], subs)
        if t == "task_rename":
            return f"{name}：" + rename_task(rel, tk["i"], a.get("text", ""), a.get("note") if "note" in a else None)
        if t == "task_delete":
            return f"{name}：" + delete_task(rel, tk["i"])
        if t == "task_priority":
            return f"{name}：" + set_task_priority(rel, tk["i"], a.get("priority", ""))
        if t == "task_due":
            return f"{name}：" + set_task_due(rel, tk["i"], a.get("due", ""))
        return f"{name}：" + set_task(rel, tk["i"], DONE)
    elif t == "set_subtasks":
        return set_subtasks(str(a.get("path", "")), int(a.get("i", -1)), a.get("subs") if isinstance(a.get("subs"), list) else [])
    elif t == "set_task_due":
        return set_task_due(str(a.get("path", "")), int(a.get("i", -1)), a.get("due", ""))
    elif t == "edit_task":  # 项目页右键：改任务名和备注
        return rename_task(str(a.get("path", "")), int(a.get("i", -1)), a.get("text", ""), a.get("note") if "note" in a else None)
    elif t == "task_review":
        return set_task_review(str(a.get("path", "")), int(a.get("i", -1)), a.get("text", ""))
    elif t == "move_task":
        return move_task(str(a.get("path", "")), int(a.get("i", -1)), str(a.get("to", "")))
    elif t == "del_task":
        return delete_task(str(a.get("path", "")), int(a.get("i", -1)))
    elif t == "set_board_status":
        return set_board_status(str(a.get("path", "")), a.get("status", ""))
    elif t == "set_board_link":
        return set_board_link(str(a.get("path", "")), a.get("name", ""), a.get("url", ""), a.get("old_url"))
    elif t == "del_board_link":
        return del_board_link(str(a.get("path", "")), str(a.get("url", "")))
    elif t == "set_board_due":
        return set_board_due(str(a.get("path", "")), a.get("due", ""))
    elif t == "idea_remove":  # AI 汇总时用：按关键词找唯一一条
        key = _cell(a.get("match"))
        hits = [x for x in ideas() if key and key in x["text"]]
        if len(hits) != 1:
            raise RuntimeError(f"建议池里含“{key}”的有 {len(hits)} 条，没有删。")
        return "建议池拿掉：" + idea_remove(hits[0]["i"], hits[0]["text"])
    elif t == "idea_del":
        return "建议池删掉：" + idea_remove(int(a.get("i", -1)), str(a.get("text", "")))
    elif t == "set_board_name":
        return set_board_name(str(a.get("path", "")), a.get("name", ""))
    elif t == "add_task":
        return add_task(str(a.get("path", "")), a.get("text", ""), a.get("priority", ""), a.get("due", ""), a.get("note", ""))
    elif t == "add_income":
        try:
            amount = float(str(a.get("amount")))
        except (TypeError, ValueError):
            raise RuntimeError("金额不是数字，没有记。") from None
        text = INCOME_LOG.read_text(encoding="utf-8") if INCOME_LOG.exists() else INCOME_MD.format(today=today())
        text = _insert_row(text, "金额", f"| {_cell(a.get('date')) or today()} | {amount:g} | {_cell(a.get('source'))} | {_cell(a.get('note'))} |")
        _write(INCOME_LOG, _touch(text))
        return f"已记到 {INCOME_LOG.relative_to(ROOT).as_posix()}（私密）"
    elif t in ("file_move", "note_create", "note_append", "add_asset", "asset_update"):
        import twin_org
        return twin_org.ACTIONS[t](a)
    else:
        raise RuntimeError(f"不认识的动作：{t}")
    _write(DASHBOARD, _touch(text))
    return msg


def export_text(question=""):
    """给任何 AI 网页用：规则 + 知识库摘要 + 问题，复制粘贴即可。"""
    q = question.strip() or "（在这里写你的问题）"
    check_outgoing(q)
    return (f"请先读完下面的规则和资料，再回答最后的问题。\n\n=== 回答规则 ===\n{rules_text()}\n\n"
            f"今天是 {today()}。\n\n=== 知识库资料（摘要层）===\n{context_text()}\n\n=== 我的问题 ===\n{q}\n")



# ---------- 反馈 ----------
def add_feedback(useful, question, note=""):
    if not FEEDBACK_FILE.exists():
        FEEDBACK_FILE.write_text(f"""---
type: log
updated: {today()}
privacy: internal
---
# AI 回答反馈记录

> 每条 AI 回答下点“有用 / 没用”会记在这里。每周复盘升级时，AI 根据它总结经验教训。

| 日期 | 评价 | 问题摘要 | 备注 |
|---|---|---|---|
""", encoding="utf-8")
    q = re.sub(r"[\r\n|]+", " ", question)[:60]
    note = re.sub(r"[\r\n|]+", " ", note)[:120]
    with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(f"| {today()} | {'有用' if useful else '没用'} | {q} | {note} |\n")


# ---------- 决策端首页：本地提醒（不经过 AI）----------
GOALS = ROOT / "00_Crown" / "Goals.md"
BRIEFS = ROOT / "00_Crown" / "Briefs"


def _table_rows(text, header_word):
    """取表头含 header_word 的所有表格的数据行（含私密段落里的，本地显示用）。"""
    rows, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and header_word in line and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
    return rows


def goals():
    try:
        text = GOALS.read_text(encoding="utf-8")
    except OSError:
        return []
    private = "".join(m.group(0) for m in PRIVATE_BLOCK.finditer(text))
    out = []
    for cells in _table_rows(text, "目标值"):
        if len(cells) < 5:
            continue
        name, cur, target, unit, due = cells[:5]
        c, t = _num_or_none(cur), _num_or_none(target)
        pct = round(min(c / t, 1) * 100) if c is not None and t else None
        out.append({"name": name, "current": cur, "target": target, "unit": unit, "due": due, "pct": pct,
                    "private": f"| {name} |" in private})
    return out


def _parse_due(s):
    """把“10-31 前”“2026-11-05”“11/5”这类截止写法转成日期。"""
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s) or re.search(r"(\d{1,2})[-/.月](\d{1,2})", s)
    if not m:
        return None
    try:
        if len(m.groups()) == 3:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        d = dt.date(dt.date.today().year, int(m.group(1)), int(m.group(2)))
        return d if (dt.date.today() - d).days < 180 else d.replace(year=d.year + 1)
    except ValueError:
        return None


def deadlines():
    try:
        text = DASHBOARD.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for cells in _table_rows(text, "截止"):
        if len(cells) < 3 or "☑" in "".join(cells):
            continue
        d = _parse_due(cells[2])
        if d:
            out.append({"task": re.sub(r"\[\[|\]\]", "", cells[1]), "due": d.isoformat(), "days": (d - dt.date.today()).days})
    return sorted(out, key=lambda x: x["days"])


def todos():
    """零散待办（来自“零散待办”项目）和决策端的待决策。"""
    ensure_loose()
    tasks = [{"priority": t["priority"], "text": t["task"], "due": t["due"], "days": t["days"], "link": t["note"], "done": t["status"] == DONE}
             for t in board(LOOSE_REL)["tasks"]] if LOOSE.exists() else []
    try:
        text = DASHBOARD.read_text(encoding="utf-8")
    except OSError:
        text = ""
    decs = [{"priority": c[0], "text": re.sub(r"^建议：", "", c[1]), "due": c[2] if len(c) > 2 else ""}
            for c in _table_rows(text, "| 决策 |") if len(c) >= 2 and c[1]]
    return tasks, decs


# ---------- 其余功能在 twin_ai_parts/ 里，一个功能一个文件 ----------
# 放在末尾 import：各部分要用上面定义的核心函数。这里导入核心自己用到的、和外面通过 twin_ai.xxx 用到的名字。
from twin_ai_parts.jobs import (
    _num_or_none, ai_opinion as ai_opinion, local_score as local_score, parse_json_block as parse_json_block, save_job_decision as save_job_decision)
from twin_ai_parts.boards import (
    _find_board, _find_task, _iso, _sub_hit, add_profile, add_task, board, boards, create_board, del_board_link, delete_task, DONE,
    due_reviews as due_reviews, ensure_loose, frontmatter as frontmatter, home as home, idea_add, idea_remove, ideas, LOOSE, LOOSE_NAME, LOOSE_REL,
    merge_tasks, move_task, profile_text, project_parents as project_parents, rename_task, set_board_due, set_board_link, set_board_name,
    set_board_priority, set_board_status, set_subtasks, set_task, set_task_due, set_task_priority, set_task_review, TODO)
from twin_ai_parts.reports import (
    _set_fm, chat_title as chat_title, close_decision, ensure_weekly as ensure_weekly, latest_weekly as latest_weekly, make_brief as make_brief,
    make_suggest as make_suggest, make_weekly as make_weekly, mark_suggest as mark_suggest, review_decision as review_decision,
    upgrade_apply as upgrade_apply, upgrade_payload as upgrade_payload, upgrade_run as upgrade_run)
from twin_ai_parts.news import make_news as make_news, news_star as news_star, news_starred as news_starred, news_today as news_today
from twin_ai_parts.day import (
    geocode as geocode, profile as profile, rhythm as rhythm, rules_text, save_profile as save_profile, weather as weather,
    weather_tips as weather_tips)
from twin_ai_parts.home import (
    _icon_host as _icon_host, draw_icon as draw_icon, edit_home_links as edit_home_links, find_icon as find_icon, home_links as home_links,
    icon_file as icon_file, save_icon as save_icon)
