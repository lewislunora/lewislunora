"""Telegram 機器人互動政策：對內群組 / 連動頻道 / 對外社群。

此模組只做身份判定與訊息路由判斷，不碰 DB 或 HTTP，方便單獨測試。
polling（openclaw_agent）與 webhook（api/server.py）共用同一套規則。
"""
import os


def _ids(env_name: str, default: str = "") -> set:
    return {c.strip() for c in os.getenv(env_name, default).split(",") if c.strip()}


BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "ailunora_bot")

# 對內：群組 + 連動頻道 + 站長私人 chat
INTERNAL_CHAT_IDS = _ids(
    "TELEGRAM_INTERNAL_CHAT_IDS", "-1003739611959,626453598"
)
LINKED_CHANNEL_IDS = _ids("TELEGRAM_LINKED_CHANNEL_IDS", "-1003937328575")

# 對外：預設所有 Group/Channel 都能互動（需 @bot）；
# 若設定此白名單，則只回覆名單內的對外 chat。
EXTERNAL_CHAT_IDS = _ids("TELEGRAM_EXTERNAL_CHAT_IDS", "")

ALL_COMMANDS = frozenset({
    "start", "help", "ai",
    "靈感", "idea",
    "翻譯", "translate",
    "搜尋", "search",
    "生圖", "image",
    "計算", "calc",
    "筆記", "note",
    "提醒", "remind",
    "語音", "voice",
    "自動化", "auto",
    "部署", "deploy",
    "狀態", "status",
})

# 翻譯/搜尋/計算成本低可對外開放；生圖、語音會花 API 費用，個人資料僅對內。
PUBLIC_COMMANDS = frozenset({
    "start", "help", "ai", "靈感", "idea", "翻譯", "translate",
    "搜尋", "search", "計算", "calc",
})
INTERNAL_ONLY_COMMANDS = frozenset({
    "自動化", "auto", "部署", "deploy", "狀態", "status", "生圖", "image",
    "筆記", "note", "提醒", "remind", "語音", "voice",
})

GROUP_TYPES = frozenset({"group", "supergroup", "channel"})


def is_internal(chat_id) -> bool:
    return str(chat_id) in INTERNAL_CHAT_IDS


def is_linked_channel(chat_id) -> bool:
    return str(chat_id) in LINKED_CHANNEL_IDS


def is_external(chat_id) -> bool:
    return not is_internal(chat_id) and not is_linked_channel(chat_id)


def is_allowed(chat_id, chat_type: str = "private") -> bool:
    """是否可以回覆此 chat。

    - 私聊：保留知識庫客服，任何人皆可問
    - 私人工作群：永遠允許
    - 網站進來的 Group/Channel：預設可互動（需 @bot）；
      若設了 TELEGRAM_EXTERNAL_CHAT_IDS 則只回覆名單內的 chat
    """
    if chat_type not in GROUP_TYPES:
        return True
    if is_internal(chat_id):
        return True
    if EXTERNAL_CHAT_IDS:
        return str(chat_id) in EXTERNAL_CHAT_IDS
    return True


def allowed_commands(chat_id):
    """只有私人工作群／站長私聊能用控制指令；連動頻道也算對外。"""
    return ALL_COMMANDS if is_internal(chat_id) else PUBLIC_COMMANDS


def command_internal_only(cmd: str) -> bool:
    return (cmd or "").lower() in INTERNAL_ONLY_COMMANDS


def requires_mention(chat_id, chat_type: str) -> bool:
    """私人工作群必須 @bot 才處理（避免誤吃聊天）；對外群組/頻道不用。"""
    if chat_type not in GROUP_TYPES:
        return False
    return is_internal(chat_id)


_QUESTION_MARKS = ("?", "？")
_QUESTION_WORDS = (
    "嗎", "呢", "什麼", "怎麼", "如何", "為什麼", "哪裡", "哪位", "誰",
    "是否", "能不能", "可不可以", "有沒有", "多少", "幾點", "請問",
    "help", "how", "what", "why", "where", "when", "which", "can you",
)


def looks_like_question(text: str) -> bool:
    """對外群組用輕量規則判斷是否為提問，避免每句話都回。"""
    lower = (text or "").strip().lower()
    if not lower:
        return False
    if lower.endswith(_QUESTION_MARKS) or any(m in lower for m in _QUESTION_MARKS):
        return True
    return any(w in lower for w in _QUESTION_WORDS)


def _mentioned(text: str, chat_type: str) -> bool:
    if chat_type not in GROUP_TYPES:
        return True
    lower = text.lower()
    return f"@{BOT_USERNAME.lower()}" in lower


def should_respond(message: dict) -> bool:
    """判斷一則 Telegram message 是否應該觸發 bot 回覆。"""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type", "private")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return False
    if not is_allowed(chat_id, chat_type):
        return False

    if requires_mention(chat_id, chat_type):
        # 私人工作群：一定要 @bot
        if not _mentioned(text, chat_type):
            return False
    elif chat_type in GROUP_TYPES:
        # 對外群組/頻道：不用 @，但只在提問、明確指令或 @ 時回覆
        if not text.startswith("/") and not _mentioned(text, chat_type) and not looks_like_question(text):
            return False
    return True


def clean_text(text: str, chat_type: str) -> str:
    """移除 @bot 標記及指令後綴（/cmd@bot）。"""
    result = (text or "").strip()
    if chat_type in GROUP_TYPES:
        result = result.replace(f"@{BOT_USERNAME}", "").strip()
    if result.startswith("/"):
        cmd, _, args = result[1:].partition(" ")
        cmd = cmd.split("@", 1)[0]
        result = "/" + cmd + ((" " + args) if args else "")
    return result
