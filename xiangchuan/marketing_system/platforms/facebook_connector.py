import logging
from .base import PlatformConnector
from ..config import FACEBOOK_PAGE_TOKEN

logger = logging.getLogger(__name__)


class FacebookConnector(PlatformConnector):
    GRAPH_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, config=None):
        super().__init__(config)
        self.name = "facebook"
        self.page_token = config.get("page_token") or FACEBOOK_PAGE_TOKEN
        self.page_id = config.get("page_id", "me")

    def verify(self):
        if not self.page_token:
            return False
        import requests
        try:
            r = requests.get(
                f"{self.GRAPH_URL}/{self.page_id}",
                params={"access_token": self.page_token},
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Facebook verify failed: {e}")
            return False

    def post(self, text, media_urls=None):
        import requests
        text = self.truncate(text, 5000)
        media_urls = media_urls or []

        if media_urls:
            first_url = media_urls[0]
            ext = first_url.rsplit(".", 1)[-1].lower()
            if ext in ("jpg", "jpeg", "png", "gif", "webp"):
                params = {"url": first_url, "caption": text, "access_token": self.page_token, "published": "true"}
                if len(media_urls) > 1:
                    params["caption"] = ""
                    for i, url in enumerate(media_urls):
                        params[f"attached_media[{i}]"] = f'{{"media_fbid":"{url}"}}'
                r = requests.post(
                    f"{self.GRAPH_URL}/{self.page_id}/photos",
                    params=params if "attached_media" not in params else {k: v for k, v in params.items() if not k.startswith("url")},
                    data=params if "attached_media" in params else {},
                    timeout=30
                )
            else:
                params = {"access_token": self.page_token}
                files = {}
                for i, url in enumerate(media_urls):
                    fr = requests.get(url, timeout=30)
                    files[f"source_{i}"] = (f"media_{i}.mp4", fr.content)
                r = requests.post(
                    f"{self.GRAPH_URL}/{self.page_id}/videos",
                    params=params, files=files, timeout=60
                )
        else:
            params = {"message": text, "access_token": self.page_token}
            r = requests.post(
                f"{self.GRAPH_URL}/{self.page_id}/feed",
                data=params, timeout=30
            )

        if r.status_code in (200, 201):
            data = r.json()
            post_id = data.get("id", "")
            return {"success": True, "post_url": f"https://facebook.com/{post_id}"}
        else:
            raise Exception(f"Facebook API error: {r.status_code} {r.text}")
