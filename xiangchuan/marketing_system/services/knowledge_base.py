import json
import logging
from ..database import fetch, execute

logger = logging.getLogger(__name__)


import re


import re


def get_kb_reply(text: str, lang: str = "zh-TW") -> str | None:
    rows = fetch("SELECT keywords, answer FROM kb_entries WHERE language=?", [lang])
    if not rows:
        rows = fetch("SELECT keywords, answer, language FROM kb_entries")
    lower = text.lower()
    best = None
    best_kw = ""
    for row in rows:
        try:
            keywords = json.loads(row["keywords"])
        except Exception:
            continue
        for kw in keywords:
            lkw = kw.lower()
            idx = lower.find(lkw)
            if idx == -1:
                continue
            if re.search(r"[a-zA-Z]", kw):
                before = lower[idx - 1] if idx > 0 else " "
                after = lower[idx + len(kw)] if idx + len(kw) < len(lower) else " "
                if (before.isascii() and before.isalnum()) or (after.isascii() and after.isalnum()):
                    continue
            if len(kw) > len(best_kw):
                best = row["answer"]
                best_kw = kw
    if best and (len(best_kw) >= 3 or len(best_kw) / max(len(text), 1) >= 0.3):
        return best
    for row in rows:
        try:
            keywords = json.loads(row["keywords"])
        except Exception:
            continue
        matches = [kw for kw in keywords if kw.lower() in lower]
        if len(matches) >= 2:
            return row["answer"]
    return None


def save_unanswered(question: str, lang: str = "zh-TW"):
    existing = fetch(
        "SELECT id, count FROM kb_pending WHERE question=? AND status='pending'",
        [question],
    )
    if existing:
        execute("UPDATE kb_pending SET count=?, updated_at=datetime('now') WHERE id=?", [existing[0]["count"] + 1, existing[0]["id"]])
        return existing[0]["id"]
    else:
        cid = execute(
            "INSERT INTO kb_pending (question, language, count) VALUES (?, ?, 1)",
            [question, lang],
        )
        return cid


def get_pending(page: int = 1, per_page: int = 50):
    offset = (page - 1) * per_page
    items = fetch(
        "SELECT * FROM kb_pending ORDER BY count DESC, created_at DESC LIMIT ? OFFSET ?",
        [per_page, offset],
    )
    total = fetch("SELECT COUNT(*) as c FROM kb_pending WHERE status='pending'")[0]["c"]
    return {"items": items, "total": total, "page": page}


def auto_learn():
    rows = fetch("SELECT * FROM kb_pending WHERE status='pending' AND count>=3")
    from ..ai.generator import AIContentGenerator
    gen = AIContentGenerator()
    for row in rows:
        try:
            prompt = f"根據以下問題，產生一個簡短的回答（50字以內）：{row['question']}"
            answer = gen.generate("custom", {"prompt": prompt})
            if answer and len(answer) > 5:
                lang = row["language"]
                keywords = _guess_keywords(row["question"])
                execute(
                    "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
                    [json.dumps(keywords, ensure_ascii=False), answer.strip(), lang],
                )
                execute("UPDATE kb_pending SET status='learned', ai_suggest=? WHERE id=?", [answer.strip(), row["id"]])
                logger.info(f"Auto-learned: {row['question']}")
        except Exception as e:
            logger.warning(f"Auto-learn failed for #{row['id']}: {e}")


def _guess_keywords(question: str) -> list:
    import re
    tokens = re.split(r"[?？，。,\.\s!！]+", question)
    tokens = [t.strip() for t in tokens if len(t.strip()) >= 2]
    return tokens[:5] if tokens else ["一般"]
