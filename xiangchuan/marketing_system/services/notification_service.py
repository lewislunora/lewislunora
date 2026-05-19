import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_NOTIFY_CHAT_ID = os.getenv("TELEGRAM_NOTIFY_CHAT_ID", "626453598")
HARDCODED_BOT_TOKEN = "8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8"


def _get_bot_token():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    return token or HARDCODED_BOT_TOKEN


def send_telegram_notification(data: dict):
    chat_id = TELEGRAM_NOTIFY_CHAT_ID
    bot_token = _get_bot_token()
    if not chat_id or not bot_token:
        logger.warning("Telegram notify: missing chat_id or bot_token")
        return False

    lines = [
        "🔔 新預約諮詢",
        f"姓名：{data.get('姓名', '')}",
    ]
    if data.get("公司"):
        lines.append(f"公司：{data['公司']}")
    if data.get("行業別"):
        lines.append(f"行業別：{data['行業別']}")
    if data.get("備註"):
        lines.append(f"備註：{data['備註']}")

    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=15)
        ok = r.json().get("ok", False)
        if ok:
            logger.info(f"Telegram notification sent to {chat_id}")
        else:
            logger.warning(f"Telegram send failed: {r.text}")
        return ok
    except Exception as e:
        logger.error(f"Telegram notification error: {e}")
        return False
