"""從群組／頻道的聊天習慣自我學習。

設計原則：
- 只存統計（平均字數、行數、提問率、關鍵詞次數），**不存訊息原文**。
- 回覆長度由該群習慣決定，但永遠不超過「3 行、每行 10 字」上限。
- 任何 DB 異常都不能讓 bot 崩潰，全部降級為預設值。
"""
import json
import logging
import re
import time

from ..database import execute, fetch_one

logger = logging.getLogger(__name__)

GROUP_TYPES = frozenset({"group", "supergroup", "channel"})
OBSERVE_INTERVAL = 20  # 同一 chat 20 秒內只更新一次，避免大量寫 DB
MIN_SAMPLES = 5        # 樣本太少時用預設值，不被單句帶偏

_STOPWORDS = frozenset({
    "please", "thanks", "help", "the", "and", "for", "with", "this", "that",
    "你好", "謝謝", "請問", "一下", "怎麼", "什麼", "可以", "現在", "我們",
})
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}|[\u4e00-\u9fff]{2,8}")
_last_observe = {}


def _keywords(text: str) -> list:
    """抽出少量主題詞，只用于統計，不保留原句。"""
    out = []
    for token in _WORD_RE.findall(text or ""):
        token = token.lower()
        if token in _STOPWORDS or token.isdigit():
            continue
        if re.search(r"[\u4e00-\u9fff]", token) and len(token) > 4:
            # 4 字滑窗（步長 2）：保留「方案價格」這類完整詞，而不是切成「案價格」
            out.extend(token[i:i + 4] for i in range(0, len(token) - 3, 2))
        else:
            out.append(token)
        if len(out) >= 8:
            break
    return out


def observe(chat_id, text: str, *, is_question: bool = False,
            is_mention: bool = False, force: bool = False):
    """增量更新該 chat 的聊天習慣統計。"""
    if not chat_id or not text:
        return None
    key = str(chat_id)
    now = time.time()
    if not force and now - _last_observe.get(key, 0) < OBSERVE_INTERVAL:
        return None
    _last_observe[key] = now
    try:
        row = fetch_one(
            "SELECT samples, avg_chars, avg_lines, questions, mentions, topics "
            "FROM bot_chat_habits WHERE chat_id=?", [key]
        )
        n = int(row["samples"] or 0) if row else 0
        avg_chars = float(row["avg_chars"] or 0) if row else 0.0
        avg_lines = float(row["avg_lines"] or 1) if row else 1.0
        questions = int(row["questions"] or 0) if row else 0
        mentions = int(row["mentions"] or 0) if row else 0
        topics = {}
        if row and row["topics"]:
            try:
                topics = json.loads(row["topics"])
            except (ValueError, TypeError):
                topics = {}

        n2 = n + 1
        avg_chars += (min(len(text), 500) - avg_chars) / n2
        avg_lines += (min(text.count("\n") + 1, 10) - avg_lines) / n2
        questions += bool(is_question)
        mentions += bool(is_mention)
        for word in _keywords(text):
            topics[word] = min(int(topics.get(word, 0)) + 1, 999)
        topics = dict(sorted(topics.items(), key=lambda kv: -kv[1])[:20])

        execute(
            "INSERT INTO bot_chat_habits "
            "(chat_id, samples, avg_chars, avg_lines, questions, mentions, topics, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(chat_id) DO UPDATE SET "
            "samples=excluded.samples, avg_chars=excluded.avg_chars, "
            "avg_lines=excluded.avg_lines, questions=excluded.questions, "
            "mentions=excluded.mentions, topics=excluded.topics, "
            "updated_at=datetime('now')",
            [key, n2, round(avg_chars, 2), round(avg_lines, 2),
             questions, mentions, json.dumps(topics, ensure_ascii=False)],
        )
        return True
    except Exception as e:
        logger.warning("bot habit observe failed: %s", e)
        return None


def profile(chat_id) -> dict:
    """回傳該 chat 的學習結果（只有統計，無原文）。"""
    if not chat_id:
        return {}
    try:
        row = fetch_one("SELECT * FROM bot_chat_habits WHERE chat_id=?", [str(chat_id)])
        if not row:
            return {}
        data = dict(row)
        try:
            data["topics"] = json.loads(data.get("topics") or "{}")
        except (ValueError, TypeError):
            data["topics"] = {}
        return data
    except Exception as e:
        logger.warning("bot habit profile failed: %s", e)
        return {}


def reply_budget(chat_id) -> tuple:
    """回 (最多幾行, 每行最多幾個字)。依群組習慣調整，上限 3 行 / 10 字。"""
    data = profile(chat_id)
    if not data or int(data.get("samples") or 0) < MIN_SAMPLES:
        return 1, 10
    avg_chars = float(data.get("avg_chars") or 0)
    avg_lines = float(data.get("avg_lines") or 1)
    max_chars = max(6, min(10, round(avg_chars / 2)))
    max_lines = max(1, min(3, round(avg_lines)))
    return max_lines, max_chars


def learned_topics(chat_id, limit: int = 5) -> list:
    """該群最常聊的主題，供 FAQ 優先比對。"""
    topics = profile(chat_id).get("topics") or {}
    return sorted(topics, key=lambda k: -topics[k])[:limit]
