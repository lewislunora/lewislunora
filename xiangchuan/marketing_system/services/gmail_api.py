"""Send email via Gmail REST API over HTTPS.

Render free tier blocks outbound SMTP (port 587), so plain SMTP fails with
"[Errno 101] Network is unreachable". Gmail API uses HTTPS (443) which is
allowed, so this is the recommended email channel.

Requires a Google Cloud OAuth2 desktop client plus an offline refresh token.
Env vars:
    GMAIL_CLIENT_ID       Google OAuth2 client id
    GMAIL_CLIENT_SECRET   Google OAuth2 client secret
    GMAIL_REFRESH_TOKEN   Offline refresh token (scope: https://mail.google.com/)
    GMAIL_USER            Sender / fallback recipient address
"""
import os
import base64
import logging
import requests
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
DEFAULT_TO = "lewislunora@gmail.com"


def get_config():
    return {
        "client_id": os.getenv("GMAIL_CLIENT_ID", ""),
        "client_secret": os.getenv("GMAIL_CLIENT_SECRET", ""),
        "refresh_token": os.getenv("GMAIL_REFRESH_TOKEN", ""),
        "user": os.getenv("GMAIL_USER", ""),
    }


def is_configured():
    cfg = get_config()
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["refresh_token"])


def _get_access_token():
    cfg = get_config()
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "refresh_token": cfg["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if r.status_code != 200:
        logger.error(f"Gmail OAuth token error: {r.status_code} {r.text[:300]}")
        raise RuntimeError(f"Gmail OAuth token error: {r.status_code}")
    return r.json()["access_token"]


def _build_raw_message(subject: str, to: str, body: str) -> str:
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


def send_email(subject: str, body: str, to: str = "") -> dict:
    cfg = get_config()
    to = (to or cfg["user"] or DEFAULT_TO).strip()
    if not is_configured():
        return {"status": "skipped", "reason": "Gmail API not configured (missing GMAIL_CLIENT_ID/GMAIL_REFRESH_TOKEN)"}
    try:
        token = _get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"raw": _build_raw_message(subject, to, body)}
        r = requests.post(SEND_URL, json=payload, headers=headers, timeout=20)
        if r.status_code in (200, 201):
            logger.info(f"Gmail API email sent to {to}: {subject}")
            return {"status": "sent"}
        logger.error(f"Gmail API send error: {r.status_code} {r.text[:300]}")
        return {"status": "error", "error": f"Gmail API error {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        logger.error(f"Gmail API send exception: {e}")
        return {"status": "error", "error": str(e)}
