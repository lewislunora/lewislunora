"""AI 社交機器人：在發佈版自動發文、回覆，並在私訊中陪聊。

設計：
- 機器人是真正的 users 帳號（is_bot=1），所以既有的追蹤／私訊／聊天室全部可直接用。
- 所有動作寫入 ai_bot_actions，用來做頻率限制與去重。
- 沒有 GROQ_API_KEY 時完全安靜，不會產生任何假內容。
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta

from ..config import GROQ_API_KEY, GROQ_MODEL
from ..database import execute, fetch, fetch_one

logger = logging.getLogger(__name__)

BOTS = [
    {
        "username": "ai_xiaoxiang",
        "name": "小翔 AI",
        "avatar": "🤖",
        "bio": "站長分身｜自動化、DevOps、AI 工具實測",
        "persona": "auto",
        "style": "務實、工程師語氣、會給具體步驟，偶爾自嘲。擅長把複雜的自動化講成人話。",
    },
    {
        "username": "ai_lele",
        "name": "阿樂",
        "avatar": "🌱",
        "bio": "生活觀察｜下班後的閒聊與陪伴",
        "persona": "life",
        "style": "溫暖、口語、像朋友聊天，會主動問對方今天過得如何，不給說教式建議。",
    },
    {
        "username": "ai_nini",
        "name": "妮妮",
        "avatar": "✨",
        "bio": "內容靈感｜寫作、行銷、個人品牌",
        "persona": "idea",
        "style": "有創意、會丟具體點子，擅長把模糊的想法變成可以馬上做的下一步。",
    },
    {
        "username": "ai_kuge",
        "name": "酷哥",
        "avatar": "🛠️",
        "bio": "科技趨勢｜AI 工具、實測、踩坑心得",
        "persona": "tech",
        "style": "直接、懂技術、會比較工具優缺點，講話有梗但不浮誇。",
    },
]

PERSONA_LABELS = {"auto": "AI 自動化", "life": "生活", "idea": "靈感", "tech": "科技"}


# ────────────────────────── 基礎 ──────────────────────────

def is_configured() -> bool:
    return bool(GROQ_API_KEY)


def _bot_hash(username: str) -> str:
    # 機器人不接受密碼登入；用不可逆亂數佔位
    return hashlib.sha256(f"bot::{username}::{random.random()}".encode()).hexdigest()


def ensure_bots() -> list[dict]:
    """建立／更新機器人帳號，回傳機器人 user rows。"""
    rows = []
    for b in BOTS:
        row = fetch_one("SELECT * FROM users WHERE username=?", (b["username"],))
        if not row:
            execute(
                "INSERT INTO users (username, name, avatar, bio, password_hash, is_bot, persona) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (b["username"], b["name"], b["avatar"], b["bio"], _bot_hash(b["username"]), b["persona"]),
            )
            row = fetch_one("SELECT * FROM users WHERE username=?", (b["username"],))
        else:
            if (row["name"] != b["name"] or row["avatar"] != b["avatar"]
                    or row["bio"] != b["bio"] or row["persona"] != b["persona"]
                    or not row["is_bot"]):
                execute(
                    "UPDATE users SET name=?, avatar=?, bio=?, is_bot=1, persona=? WHERE id=?",
                    (b["name"], b["avatar"], b["bio"], b["persona"], row["id"]),
                )
                row = fetch_one("SELECT * FROM users WHERE username=?", (b["username"],))
        rows.append(row)
    return rows


def list_bots() -> list[dict]:
    ensure_bots()
    rows = fetch("SELECT id, username, name, avatar, bio, persona FROM users WHERE is_bot=1 ORDER BY id")
    return [dict(r) for r in rows]


def get_bot(username: str = "") -> dict | None:
    ensure_bots()
    if username:
        return fetch_one("SELECT * FROM users WHERE username=? AND is_bot=1", (username,))
    row = fetch_one("SELECT * FROM users WHERE is_bot=1 ORDER BY random() LIMIT 1")
    return row


# ────────────────────────── Groq ──────────────────────────

def _generate(prompt: str, system: str = "", max_tokens: int = 320) -> str:
    if not GROQ_API_KEY:
        return ""
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.95,
            max_tokens=max_tokens,
        )
        text = (resp.choices[0].message.content or "").strip()
        return _clean(text)
    except Exception as exc:  # noqa: BLE001 - 不讓 AI 失敗影響網站
        logger.warning(f"ai_social generate failed: {exc}")
        return ""


def _clean(text: str) -> str:
    text = text.strip().strip('"').strip("「」")
    for prefix in ("貼文：", "回覆：", "AI：", "小翔 AI：", "阿樂：", "妮妮：", "酷哥："):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = " ".join(lines)
    return text[:500]


# ────────────────────────── 動作紀錄／限流 ──────────────────────────

def _log_action(bot_id: int, action: str, ref: str = "") -> None:
    execute(
        "INSERT INTO ai_bot_actions (bot_user_id, action, ref) VALUES (?, ?, ?)",
        (bot_id, action, ref),
    )


def _count_actions(bot_id: int, action: str, minutes: int) -> int:
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    row = fetch_one(
        "SELECT COUNT(*) AS c FROM ai_bot_actions WHERE bot_user_id=? AND action=? AND created_at>=?",
        (bot_id, action, cutoff),
    )
    return row["c"] if row else 0


# ────────────────────────── 發文 ──────────────────────────

POST_PROMPT = (
    "你是「{name}」，{bio}。個性與語氣：{style}\n"
    "現在是 {now}。請寫一則要發在社群動態版上的繁體中文貼文：\n"
    "- 60~120 字，口語、像真人\n"
    "- 具體、有畫面，不要空泛雞湯\n"
    "- 結尾用一個自然的問句邀請互動\n"
    "- 最多 2 個 hashtag，不要條列，不要提到自己是 AI 或機器人\n"
    "只輸出貼文內容。"
)


def create_bot_post(bot: dict) -> int | None:
    if not is_configured():
        return None
    if _count_actions(bot["id"], "post", 360) >= 1:
        return None
    now = datetime.now().strftime("%m/%d %H:%M")
    text = _generate(
        POST_PROMPT.format(name=bot["name"], bio=bot["bio"], style=bot.get("persona_style", ""), now=now),
        max_tokens=260,
    )
    if not text:
        return None
    pid = execute(
        "INSERT INTO feed_posts (user_id, content, post_type, author) VALUES (?, ?, ?, ?)",
        (bot["id"], text, bot["persona"] or "life", bot["name"]),
    )
    _log_action(bot["id"], "post", str(pid))
    return pid


# ────────────────────────── 回覆動態 ──────────────────────────

REPLY_PROMPT = (
    "你是「{name}」，{bio}。個性與語氣：{style}\n"
    "有人在社群動態發了這則貼文：\n「{content}」\n"
    "請用繁體中文寫一則 30~70 字的回覆：真誠、具體、延伸對方的話題，"
    "最後用一個小問題讓對話繼續。不要說教，不要提到自己是 AI，只輸出回覆內容。"
)


def reply_to_post(post: dict, bot: dict) -> int | None:
    if not is_configured():
        return None
    if _count_actions(bot["id"], "reply", 60) >= 2:
        return None
    path = f"feed:{post['id']}"
    exists = fetch_one(
        "SELECT c.id FROM comments c JOIN users u ON u.id=c.user_id "
        "WHERE c.page_path=? AND u.is_bot=1 LIMIT 1",
        (path,),
    )
    if exists:
        return None
    text = _generate(
        REPLY_PROMPT.format(name=bot["name"], bio=bot["bio"],
                            style=bot.get("persona_style", ""), content=post["content"][:600]),
        max_tokens=220,
    )
    if not text:
        return None
    cid = execute(
        "INSERT INTO comments (page_path, author_name, content, user_id) VALUES (?, ?, ?, ?)",
        (path, bot["name"], text, bot["id"]),
    )
    _log_action(bot["id"], "reply", str(post["id"]))
    return cid


# ────────────────────────── 私訊陪聊 ──────────────────────────

DM_PROMPT = (
    "你是「{name}」，{bio}。個性與語氣：{style}\n"
    "以下是你和對方的私訊（由舊到新）：\n{history}\n\n"
    "請用繁體中文回覆最後一則訊息：20~60 字，像朋友聊天，"
    "可以回答、接話或問一個問題。不要條列、不要提到自己是 AI。只輸出回覆內容。"
)


def bot_reply_to_dm(bot: dict, conversation_id: int, history: list[dict]) -> int | None:
    if not is_configured() or not history:
        return None
    # 同一對話 4 秒內不重複回，避免前端輪詢造成連發
    recent = fetch_one(
        "SELECT id FROM ai_bot_actions WHERE bot_user_id=? AND action='dm' AND ref=? "
        "AND created_at >= datetime('now','-5 seconds')",
        (bot["id"], str(conversation_id)),
    )
    if recent:
        return None
    lines = []
    for m in history[-8:]:
        who = "你" if m.get("sender_id") == bot["id"] else "對方"
        lines.append(f"{who}：{m.get('body', '')[:300]}")
    text = _generate(
        DM_PROMPT.format(name=bot["name"], bio=bot["bio"],
                         style=bot.get("persona_style", ""), history="\n".join(lines)),
        max_tokens=200,
    )
    if not text:
        return None
    mid = execute(
        "INSERT INTO messages (conversation_id, sender_id, body) VALUES (?, ?, ?)",
        (conversation_id, bot["id"], text),
    )
    execute("UPDATE conversations SET last_message_at=datetime('now') WHERE id=?", (conversation_id,))
    _log_action(bot["id"], "dm", str(conversation_id))
    return mid


def greeting_for(bot: dict) -> str:
    text = _generate(
        f"你是「{bot['name']}」，{bot['bio']}。用繁體中文寫一句 20~40 字的開場白，"
        "主動打招呼並問對方今天想做什麼。只輸出這句話。",
        max_tokens=120,
    )
    return text or f"嗨，我是{bot['name']}。今天想聊什麼？工作、生活，還是隨便聊聊都可以。"


# ────────────────────────── 排程 ──────────────────────────

def _prune_actions(days: int = 7) -> None:
    """動作紀錄只用來限流與去重，保留 7 天即可，避免備份 JSON 無限長大。"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    execute("DELETE FROM ai_bot_actions WHERE created_at < ?", (cutoff,))

def _bot_posts_last_24h() -> int:
    cutoff = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    row = fetch_one(
        "SELECT COUNT(*) AS c FROM ai_bot_actions WHERE action='post' AND created_at>=?",
        (cutoff,),
    )
    return row["c"] if row else 0


def tick() -> dict:
    """每 20 分鐘跑一次：補發文 + 回覆真人貼文。"""
    _prune_actions()
    if not is_configured():
        return {"ok": True, "skipped": "no GROQ_API_KEY"}
    bots = [dict(r) for r in ensure_bots()]
    for b in bots:
        b["persona_style"] = next(
            (x["style"] for x in BOTS if x["username"] == b["username"]), ""
        )
    posted = replied = 0

    # 1) 發文：每個機器人 6 小時最多一篇，每次 tick 最多 2 篇
    #    另外全站每天最多 8 篇 AI 貼文，避免洗版蓋掉真人內容。
    can_post = _bot_posts_last_24h() < 8
    random.shuffle(bots)
    for b in bots:
        if posted >= 2 or not can_post:
            break
        if create_bot_post(b):
            posted += 1
            if _bot_posts_last_24h() >= 8:
                can_post = False

    # 2) 回覆：抓最近 48 小時、還沒有機器人回覆的真人貼文
    cutoff = (datetime.utcnow() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    posts = fetch(
        "SELECT p.* FROM feed_posts p WHERE p.created_at>=? AND p.user_id IS NOT NULL "
        "AND p.user_id NOT IN (SELECT id FROM users WHERE is_bot=1) "
        "AND NOT EXISTS (SELECT 1 FROM comments c JOIN users u ON u.id=c.user_id "
        "                WHERE c.page_path='feed:'||p.id AND u.is_bot=1) "
        "ORDER BY p.id DESC LIMIT 3",
        (cutoff,),
    )
    for p in posts:
        if replied >= 2:
            break
        b = random.choice(bots)
        if reply_to_post(dict(p), b):
            replied += 1

    return {"ok": True, "posted": posted, "replied": replied}
