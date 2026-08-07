import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_NOTIFY_CHAT_ID = os.getenv("TELEGRAM_NOTIFY_CHAT_ID", "626453598")
HARDCODED_BOT_TOKEN = "8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8"
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")


def _get_bot_token():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    return token or HARDCODED_BOT_TOKEN


def _send_telegram(text: str) -> bool:
    chat_id = TELEGRAM_NOTIFY_CHAT_ID
    bot_token = _get_bot_token()
    if not chat_id or not bot_token:
        logger.warning("Telegram notify: missing chat_id or bot_token")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=15)
        ok = r.json().get("ok", False)
        if ok:
            logger.info("Telegram notification sent")
        else:
            logger.warning(f"Telegram send failed: {r.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False


def _send_line_notify(text: str) -> bool:
    token = LINE_NOTIFY_TOKEN
    if not token:
        logger.info("LINE Notify not configured, skipping")
        return False
    try:
        r = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": text[:1000]},
            timeout=15,
        )
        ok = r.status_code == 200
        if ok:
            logger.info("LINE Notify sent")
        else:
            logger.warning(f"LINE Notify failed: {r.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"LINE Notify error: {e}")
        return False


def _send_email(subject: str, text: str) -> bool:
    try:
        from ..services.email_service import send_generic_email
        result = send_generic_email(subject, text)
        return result.get("status") == "sent"
    except Exception as e:
        logger.error(f"Email notify error: {e}")
        return False


def notify_owner(event_type: str, data: dict, url: str = ""):
    """Fan out an event notification to all configured channels.
    event_type: contact / comment / thread / reply / reaction
    """
    lines = [_build_message(event_type, data)]
    if url:
        lines.append(f"🔗 連結：{url}")
    text = "\n".join(lines)

    _send_telegram(text)
    _send_line_notify(text)
    _send_email(_subject_for(event_type), text)


def _subject_for(event_type: str) -> str:
    return {
        "contact": "🔔 新預約諮詢 - 翔川 Neo",
        "comment": "💬 新留言 - 翔川 Neo",
        "thread": "📌 新發案/貼文 - 翔川 Neo",
        "reply": "↩️ 新回覆 - 翔川 Neo",
        "reaction": "👍 新反應 - 翔川 Neo",
    }.get(event_type, "🔔 翔川 Neo 通知")


def _build_message(event_type: str, data: dict) -> str:
    if event_type == "contact":
        parts = ["🔔 新預約諮詢"]
        for key, label in [("姓名", "姓名"), ("公司", "公司"), ("聯絡方式", "聯絡方式"),
                           ("Email", "Email"), ("行業別", "行業別"), ("需求", "想了解的服務"),
                           ("備註", "備註")]:
            val = data.get(key, "").strip()
            if val:
                parts.append(f"{label}：{val}")
        return "\n".join(parts)

    if event_type == "comment":
        page = data.get("page_path", "/")
        return (
            "💬 新留言\n"
            f"留言者：{data.get('author_name', '匿名')}\n"
            f"頁面：{page}\n"
            f"內容：{(data.get('content') or '')[:500]}"
        )

    if event_type == "thread":
        return (
            "📌 新發案/貼文\n"
            f"作者：{data.get('author_name', '匿名')}\n"
            f"標題：{(data.get('title') or '')[:200]}\n"
            f"內容：{(data.get('content') or '')[:500]}"
        )

    if event_type == "reply":
        return (
            "↩️ 新回覆\n"
            f"回覆者：{data.get('author_name', '匿名')}\n"
            f"回覆：{(data.get('content') or '')[:500]}"
        )

    if event_type == "reaction":
        return (
            "👍 新反應\n"
            f"頁面：{data.get('page_path', '/')}\n"
            f"表情：{data.get('emoji', '')}"
        )

    return str(data)


def send_telegram_notification(data: dict):
    """Backward-compatible: used by legacy contact flow."""
    return _send_telegram(_build_message("contact", data))
