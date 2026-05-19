import logging
from .base import PlatformConnector
from ..config import TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_BEARER_TOKEN

logger = logging.getLogger(__name__)


class TwitterConnector(PlatformConnector):
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "twitter"
        self.api_key = config.get("api_key") or TWITTER_API_KEY
        self.api_secret = config.get("api_secret") or TWITTER_API_SECRET
        self.bearer_token = config.get("bearer_token") or TWITTER_BEARER_TOKEN

    def verify(self):
        if not self.bearer_token:
            return False
        import requests
        try:
            r = requests.get(
                "https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {self.bearer_token}"},
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Twitter verify failed: {e}")
            return False

    def post(self, text, media_urls=None):
        import requests
        text = self.truncate(text, 280)
        headers = {"Authorization": f"Bearer {self.bearer_token}", "Content-Type": "application/json"}

        user_resp = requests.get("https://api.twitter.com/2/users/me", headers=headers, timeout=10)
        if user_resp.status_code != 200:
            raise Exception(f"Twitter auth failed: {user_resp.text}")
        user_id = user_resp.json()["data"]["id"]

        media_ids = []
        if media_urls:
            for url in media_urls[:4]:
                fr = requests.get(url, timeout=30)
                upload = requests.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    headers={"Authorization": f"Bearer {self.bearer_token}"},
                    files={"media": fr.content},
                    timeout=60
                )
                if upload.status_code == 200:
                    media_ids.append(upload.json()["media_id_string"])

        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        r = requests.post(
            f"https://api.twitter.com/2/tweets",
            headers=headers, json=payload, timeout=30
        )

        if r.status_code in (200, 201):
            data = r.json()
            tweet_id = data["data"]["id"]
            return {"success": True, "post_url": f"https://twitter.com/i/web/status/{tweet_id}"}
        else:
            raise Exception(f"Twitter API error: {r.status_code} {r.text}")
