import logging
from .base import PlatformConnector
from ..config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


class TelegramConnector(PlatformConnector):
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "telegram"
        self.bot_token = config.get("bot_token") or TELEGRAM_BOT_TOKEN
        self.chat_id = config.get("chat_id", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def verify(self):
        if not self.bot_token:
            logger.error("Telegram: no bot token")
            return False
        import requests
        try:
            r = requests.get(f"{self.base_url}/getMe", timeout=10)
            return r.json().get("ok", False)
        except Exception as e:
            logger.error(f"Telegram verify failed: {e}")
            return False

    def post(self, text, media_urls=None):
        import requests
        text = self.truncate(text, 4000)
        media_urls = media_urls or []

        if media_urls:
            media = [{"type": "photo", "media": url} for url in media_urls[:10]]
            media[0]["caption"] = text
            payload = {"chat_id": self.chat_id, "media": media}
            r = requests.post(f"{self.base_url}/sendMediaGroup", json=payload, timeout=30)
        else:
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            r = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=30)

        result = r.json()
        if result.get("ok"):
            msg = result["result"]
            if isinstance(msg, list):
                msg = msg[0]
            return {"success": True, "post_url": f"https://t.me/c/{msg['chat']['id']}/{msg['message_id']}"}
        else:
            raise Exception(f"Telegram API error: {result}")

    def send_to_channel(self, channel_id, text, media_urls=None):
        self.chat_id = channel_id
        return self.post(text, media_urls)
