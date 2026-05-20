import json
import logging
from ..database import fetch

logger = logging.getLogger(__name__)


def get_kb_reply(text: str, lang: str = "zh-TW") -> str | None:
    rows = fetch("SELECT keywords, answer FROM kb_entries WHERE language=?", [lang])
    if not rows:
        rows = fetch("SELECT keywords, answer FROM kb_entries WHERE language='zh-TW'")
    lower = text.lower()
    for row in rows:
        try:
            keywords = json.loads(row["keywords"])
        except Exception:
            continue
        for kw in keywords:
            if kw.lower() in lower:
                return row["answer"]
    if lang == "en" and any(w in lower for w in ["how", "what", "can you"]):
        rows = fetch("SELECT keywords, answer FROM kb_entries WHERE language='en' AND keywords LIKE '%how%'")
        return rows[0]["answer"] if rows else None
    return None
