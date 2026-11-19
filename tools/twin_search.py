#!/usr/bin/env python3
"""本地相关度搜索（只用 Python 标准库，不联网，不装模型）。

用 BM25 给文档打分：中文按相邻两个字切词，英文和数字按单词切。
比“包含这几个字”准得多：词越少见、在文档里出现越多、文档越短，分数越高。
索引放在内存里，文件改过（修改时间变了）才重新读。
"""
import math
import os
import re
import threading
import time
from collections import Counter

from twin import PRIVATE_BLOCK, ROOT

K1, B = 1.4, 0.75
_CJK = re.compile(r"[一-鿿]+")
_WORD = re.compile(r"[a-z0-9][a-z0-9_.+-]*")
_FM = re.compile(r"^---\n.*?\n---\n?", re.S)
STOP = {"的", "了", "和", "是", "在", "也", "就", "都", "而", "及", "与", "或", "一个", "这个", "我们", "可以", "没有",
        "the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "md"}


def tokens(text):
    text = text.lower()
    out = [w for w in _WORD.findall(text) if len(w) > 1 and w not in STOP]
    for run in _CJK.findall(text):
        if len(run) == 1:
            out.append(run)
        out += [run[i:i + 2] for i in range(len(run) - 1) if run[i:i + 2] not in STOP]
    return out


class Index:
    def __init__(self):
        self.docs = {}  # rel -> {"mtime", "tf": Counter, "len", "text", "title"}
        self.df = Counter()
        self.checked = 0.0
        self.lock = threading.Lock()

    def refresh(self, items, max_age=30):
        """items: [{"path","title"}]（资料库目录）。最多每 max_age 秒检查一次修改时间。"""
        with self.lock:
            if time.time() - self.checked < max_age and len(items) == len(self.docs):
                return
            seen = set()
            for it in items:
                rel = it["path"]
                seen.add(rel)
                try:
                    m = os.stat(ROOT / rel).st_mtime_ns
                except OSError:
                    continue
                d = self.docs.get(rel)
                if d and d["mtime"] == m:
                    continue
                try:
                    raw = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                body = _FM.sub("", raw)
                # 标题和路径名算两遍，命中标题的文档排前面
                tf = Counter(tokens(body) + tokens(it.get("title", "")) * 2 + tokens(rel.replace("_", " ")) * 2)
                if d:
                    self.df.subtract(set(d["tf"]))
                self.df.update(set(tf))
                self.docs[rel] = {"mtime": m, "tf": tf, "len": sum(tf.values()) or 1, "text": body,
                                  "title": it.get("title", rel)}
            for rel in list(self.docs):
                if rel not in seen:
                    self.df.subtract(set(self.docs.pop(rel)["tf"]))
            self.checked = time.time()

    def score(self, q_terms, only=None):
        n = len(self.docs) or 1
        avg = sum(d["len"] for d in self.docs.values()) / n
        qc = Counter(q_terms)
        out = []
        for rel, d in self.docs.items():
            if only is not None and rel not in only:
                continue
            s = 0.0
            for t, w in qc.items():
                f = d["tf"].get(t)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                s += w * idf * f * (K1 + 1) / (f + K1 * (1 - B + B * d["len"] / avg))
            if s > 0:
                out.append((s, rel))
        out.sort(reverse=True)
        return out

    def snippet(self, rel, q_terms, width=90):
        text = PRIVATE_BLOCK.sub(" ", self.docs[rel]["text"])
        flat = re.sub(r"\s+", " ", text)
        low = flat.lower()
        best, pos = -1, 0
        for t in set(q_terms):
            i = low.find(t)
            while i >= 0:
                hits = sum(1 for x in set(q_terms) if x in low[i:i + width])
                if hits > best:
                    best, pos = hits, i
                i = low.find(t, i + 1)
                if i > 50000:
                    break
        start = max(pos - 20, 0)
        return ("…" if start else "") + flat[start:start + width] + "…"

    def search(self, q, items, limit=40):
        self.refresh(items)
        terms = tokens(q)
        if not terms:
            return []
        ql = q.lower().strip()
        res = []
        for s, rel in self.score(terms):
            d = self.docs[rel]
            if ql and (ql in d["title"].lower() or ql in rel.lower()):
                s *= 1.5  # 标题或文件名里有完整的搜索词
            elif ql and ql in d["text"].lower():
                s *= 1.2
            res.append((s, rel))
        res.sort(reverse=True)
        return [{"path": rel, "score": round(s, 2), "snippet": self.snippet(rel, terms)} for s, rel in res[:limit]]

    def related(self, rel, items, limit=6):
        """和这篇最像的几篇：用它最有代表性的 30 个词去搜。"""
        self.refresh(items)
        d = self.docs.get(rel)
        if not d:
            return []
        n = len(self.docs)
        weight = {t: f * math.log(1 + n / (1 + self.df[t])) for t, f in d["tf"].items()}
        top = [t for t, _ in sorted(weight.items(), key=lambda x: -x[1])[:30]]
        out = []
        for s, r in self.score(top):
            if r == rel:
                continue
            out.append({"path": r, "title": self.docs[r]["title"], "score": round(s, 1)})
            if len(out) >= limit:
                break
        return out


INDEX = Index()
