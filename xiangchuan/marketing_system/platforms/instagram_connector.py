import logging
from .base import PlatformConnector
from ..config import INSTAGRAM_ACCESS_TOKEN

logger = logging.getLogger(__name__)


class InstagramConnector(PlatformConnector):
    """Post to an Instagram business account via Meta Graph API.

    Requires an Instagram Business / Creator account linked to a Facebook
    Page. Credentials come from env vars or account config:
        access_token  IG long-lived user token (or page token)
        ig_user_id    Instagram business account id
    """
    GRAPH_URL = "https://graph.facebook.com/v21.0"

    def __init__(self, config=None):
        super().__init__(config)
        self.name = "instagram"
        self.access_token = config.get("access_token") or INSTAGRAM_ACCESS_TOKEN
        self.ig_user_id = config.get("ig_user_id", "")

    def verify(self):
        if not self.access_token:
            return False
        import requests
        try:
            url = f"{self.GRAPH_URL}/{self.ig_user_id}" if self.ig_user_id else f"{self.GRAPH_URL}/me"
            r = requests.get(url, params={"access_token": self.access_token}, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Instagram verify failed: {e}")
            return False

    def _media_publish(self, media_id):
        import requests
        r = requests.post(
            f"{self.GRAPH_URL}/{self.ig_user_id}/media_publish",
            params={"creation_id": media_id, "access_token": self.access_token},
            timeout=30,
        )
        if r.status_code in (200, 201):
            return r.json().get("id", "")
        raise Exception(f"Instagram media_publish error: {r.status_code} {r.text}")

    def post(self, text, media_urls=None):
        import requests
        if not self.ig_user_id:
            raise Exception("Instagram: ig_user_id not configured")
        media_urls = media_urls or []
        if not media_urls:
            raise Exception("Instagram 貼文需要至少一張圖片")
        text = self.truncate(text, 2200)

        container_ids = []
        for url in media_urls[:10]:
            payload = {
                "image_url": url,
                "caption": text if not container_ids else "",
                "access_token": self.access_token,
            }
            r = requests.post(
                f"{self.GRAPH_URL}/{self.ig_user_id}/media",
                params=payload, timeout=30,
            )
            if r.status_code not in (200, 201):
                raise Exception(f"Instagram media container error: {r.status_code} {r.text}")
            container_ids.append(r.json()["id"])

        post_id = self._media_publish(container_ids[0])
        return {"success": True, "post_url": f"https://instagram.com/p/{post_id}"}
