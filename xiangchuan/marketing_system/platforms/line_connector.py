import logging
from .base import PlatformConnector
from ..config import LINE_CHANNEL_ACCESS_TOKEN

logger = logging.getLogger(__name__)


class LineConnector(PlatformConnector):
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "line"
        self.access_token = config.get("access_token") or LINE_CHANNEL_ACCESS_TOKEN
        self.target = config.get("target", "")  # user_id or group_id

    def verify(self):
        if not self.access_token:
            return False
        import requests
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            r = requests.get("https://api.line.me/v2/bot/info", headers=headers, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Line verify failed: {e}")
            return False

    def post(self, text, media_urls=None):
        import requests
        text = self.truncate(text, 5000)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        messages = [{"type": "text", "text": text}]

        if media_urls:
            for url in media_urls[:5]:
                messages.append({"type": "image", "originalContentUrl": url, "previewImageUrl": url})

        payload = {"to": self.target, "messages": messages}
        r = requests.post("https://api.line.me/v2/bot/message/push", json=payload, headers=headers, timeout=30)

        if r.status_code == 200:
            return {"success": True, "post_url": ""}
        else:
            raise Exception(f"Line API error: {r.status_code} {r.text}")

    def broadcast(self, text, media_urls=None):
        import requests
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        messages = [{"type": "text", "text": self.truncate(text, 5000)}]
        r = requests.post("https://api.line.me/v2/bot/message/broadcast", json={"messages": messages}, headers=headers, timeout=30)
        if r.status_code == 200:
            return {"success": True}
        raise Exception(f"Line broadcast error: {r.status_code}")
