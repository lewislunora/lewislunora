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

# 對外：必須明確 opt-in 才回覆，避免被任意拉群後洗版
EXTERNAL_CHAT_IDS = _ids("TELEGRAM_EXTERNAL_CHAT_IDS", "")

ALL_COMMANDS = frozenset({
    "start", "help",
    "靈感", "idea",
    "自動化", "auto",
    "部署", "deploy",
    "狀態", "status",
})

PUBLIC_COMMANDS = frozenset({"start", "help", "靈感", "idea"})
INTERNAL_ONLY_COMMANDS = frozenset({"自動化", "auto", "部署", "deploy", "狀態", "status"})

GROUP_TYPES = frozenset({"group", "supergroup", "channel"})


def is_internal(chat_id) -> bool:
    return str(chat_id) in INTERNAL_CHAT_IDS


def is_linked_channel(chat_id) -> bool:
    return str(chat_id) in LINKED_CHANNEL_IDS


def is_external(chat_id) -> bool:
    return not is_internal(chat_id) and not is_linked_channel(chat_id)


def is_allowed(chat_id, chat_type: str = "private") -> bool:
    """是否可以回覆此 chat。

    私聊保留原本的知識庫客服行為（任何人皆可問）；
    群組/頻道則必須是內部或明確 opt-in 的對外群組。
    """
    if chat_type not in GROUP_TYPES:
        return True
    s = str(chat_id)
    return is_internal(s) or is_linked_channel(s) or s in EXTERNAL_CHAT_IDS


def allowed_commands(chat_id):
    """依身份回傳可用的指令集合。"""
    return ALL_COMMANDS if (is_internal(chat_id) or is_linked_channel(chat_id)) else PUBLIC_COMMANDS


def command_internal_only(cmd: str) -> bool:
    return (cmd or "").lower() in INTERNAL_ONLY_COMMANDS


def requires_mention(chat_id, chat_type: str) -> bool:
    """對外群組必須 @bot 才回覆；對內群組與私聊不用。"""
    if chat_type not in GROUP_TYPES:
        return False
    return is_external(chat_id)


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
    if requires_mention(chat_id, chat_type) and not _mentioned(text, chat_type):
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
