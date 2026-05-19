import os
import logging
import requests
from ..config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

TELEGRAM_NOTIFY_CHAT_ID = os.getenv("TELEGRAM_NOTIFY_CHAT_ID", "626453598")


def send_telegram_notification(data: dict):
    chat_id = TELEGRAM_NOTIFY_CHAT_ID
    if not chat_id or not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram notify: TELEGRAM_NOTIFY_CHAT_ID or TELEGRAM_BOT_TOKEN not set")
        return False

    lines = [
        "🔔 新預約諮詢",
        f"姓名：{data.get('姓名', '')}",
    ]
    if data.get("公司"):
        lines.append(f"公司：{data['公司']}")
    lines.append(f"聯絡方式：{data.get('聯絡方式', '')}")
    if data.get("Email"):
        lines.append(f"Email：{data['Email']}")
    if data.get("行業別"):
        lines.append(f"行業別：{data['行業別']}")
    if data.get("備註"):
        lines.append(f"備註：{data['備註']}")

    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
