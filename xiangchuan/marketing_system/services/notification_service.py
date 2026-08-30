import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_NOTIFY_CHAT_ID = os.getenv("TELEGRAM_NOTIFY_CHAT_ID", "626453598")
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")

MAX_ATTEMPTS = int(os.getenv("NOTIFY_MAX_ATTEMPTS", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("NOTIFY_RETRY_BACKOFF", "2"))


def _get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _send_with_retry(fn, label: str, attempts: int = MAX_ATTEMPTS, backoff: float = RETRY_BACKOFF_SECONDS,
                     is_success=lambda r: bool(r)):
    """Call fn() until is_success(result), with exponential backoff between tries."""
    last = None
    for i in range(attempts):
        try:
            result = fn()
            if is_success(result):
                return result
            last = result
        except Exception as e:
            last = None
            logger.error(f"{label} error on attempt {i + 1}: {e}")
        if i < attempts - 1:
            time.sleep(backoff * (2 ** i))
    return last


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


def _send_email(subject: str, text: str):
    try:
        from ..services.email_service import send_generic_email
        result = send_generic_email(subject, text)
        return result
    except Exception as e:
        logger.error(f"Email notify error: {e}")
        return {"status": "error", "error": str(e)}


def notify_owner(event_type: str, data: dict, url: str = ""):
    """Fan out an event notification to all configured channels.
    event_type: contact / comment / thread / reply / reaction
    Returns a dict of per-channel results for testing/diagnostics.
    """
    lines = [_build_message(event_type, data)]
    if url:
        lines.append(f"🔗 連結：{url}")
    text = "\n".join(lines)

    results = {
        "telegram": bool(_send_with_retry(
            lambda: _send_telegram(text), "Telegram notification")),
        "line": bool(_send_with_retry(
            lambda: _send_line_notify(text), "LINE Notify notification")),
        "email": _send_with_retry(
            lambda: _send_email(_subject_for(event_type), text), "Email notification",
            is_success=lambda r: isinstance(r, dict) and r.get("status") == "sent"),
    }
    return results


def _subject_for(event_type: str) -> str:
    return {
        "contact": "🔔 新預約諮詢 - 翔川 Neo",
        "comment": "💬 新留言 - 翔川 Neo",
        "thread": "📌 新發案/貼文 - 翔川 Neo",
        "reply": "↩️ 新回覆 - 翔川 Neo",
        "reaction": "👍 新反應 - 翔川 Neo",
        "incoming": "📥 社群進站訊息 - 翔川 Neo",
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

    if event_type == "incoming":
        return (
            "📥 社群進站訊息\n"
            f"平台：{data.get('platform', '')}\n"
            f"發送者：{data.get('sender', '') or '匿名'}\n"
            f"內容：{(data.get('content') or '')[:500]}"
        )

    return str(data)


def send_telegram_notification(data: dict):
    """Backward-compatible: used by legacy contact flow."""
    return _send_telegram(_build_message("contact", data))
