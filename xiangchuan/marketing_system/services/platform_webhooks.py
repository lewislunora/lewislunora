"""Receive platform webhooks (Facebook / Instagram / Threads / X) in real time.

These endpoints let the platform call back into this server whenever a
customer comments or DMs the business. Each platform's official developer
approval is still required before production delivery, but the server-side
handling (verify + receive + store + notify) is fully implemented here.

Verification tokens / secrets come from env vars:
    FB_WEBHOOK_VERIFY_TOKEN   token configured in Meta App Dashboard
    TWITTER_API_SECRET        X consumer secret (for CRC challenge)
"""
import os
import json
import hmac
import base64
import hashlib
import logging

logger = logging.getLogger(__name__)

META_VERIFY_TOKEN = os.getenv("FB_WEBHOOK_VERIFY_TOKEN", "")


def verify_meta(params: dict, verify_token: str = ""):
    """Handle Meta webhook verification handshake.

    Meta sends GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
    Returns the challenge string when the token matches, else None.
    """
    verify_token = verify_token or os.getenv("FB_WEBHOOK_VERIFY_TOKEN", "")
    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token and token == verify_token and challenge:
        return challenge
    return None


def verify_x(params: dict, secret: str = ""):
    """Handle X Account Activity API CRC challenge.

    X sends GET /webhook?crc_token=... expecting a signed challenge:
    {"response_token": "sha256=<base64 hmac>"}
    """
    crc = params.get("crc_token", "")
    if not crc:
        return None
    secret = secret or os.getenv("TWITTER_API_SECRET", "")
    digest = hmac.new(secret.encode("utf-8"), crc.encode("utf-8"),
                      digestmod=hashlib.sha256).digest()
    return {"response_token": f"sha256={base64.b64encode(digest).decode('utf-8')}"}


def _store_incoming(platform: str, external_id: str, sender: str, text: str, raw: dict):
    from ..database import execute
    try:
        execute(
            "INSERT OR IGNORE INTO incoming_messages (platform, external_id, sender, text, raw) VALUES (?, ?, ?, ?, ?)",
            [
                platform,
                (external_id or sender)[:200],
                (sender or "")[:200],
                (text or "")[:2000],
                json.dumps(raw, ensure_ascii=False, default=str)[:5000],
            ],
        )
    except Exception as e:
        logger.error(f"incoming_messages insert failed: {e}")

    from .notification_service import notify_owner
    try:
        notify_owner("incoming", {
            "platform": platform,
            "sender": sender,
            "content": (text or "")[:300],
        })
    except Exception as e:
        logger.error(f"incoming notify failed: {e}")


def process_meta_payload(payload: dict, platform: str) -> int:
    """Parse a Meta Graph API webhook payload into incoming messages.

    Handles Messenger / Instagram DM messaging events (entry[].messaging)
    and page / IG / Threads change events (entry[].changes[]).
    Returns the number of new messages stored.
    """
    count = 0
    for entry in payload.get("entry", []):
        for m in entry.get("messaging", []):
            msg = m.get("message", {})
            text = msg.get("text", "") or ""
            if not text:
                postback = m.get("postback", {})
                if postback.get("payload"):
                    text = f"[postback] {postback['payload']}"
            if not text:
                continue
            sender = m.get("sender", {}).get("id", "") or ""
            external_id = msg.get("mid", "") or f"{sender}-{m.get('timestamp', '')}"
            _store_incoming(platform, external_id, sender, text, m)
            count += 1

        for ch in entry.get("changes", []):
            val = ch.get("value", {}) or {}
            frm = val.get("from", {}) or {}
            text = val.get("message", "") or val.get("text", "") or ""
            if not text:
                continue
            sender = frm.get("name", "") or frm.get("username", "") or frm.get("id", "") or ""
            external_id = (val.get("id", "") or val.get("comment_id", "") or
                           f"change-{val.get('created_time', ch.get('time', ''))}")
            _store_incoming(platform, external_id, sender, text, val)
            count += 1
    return count


def process_x_payload(payload: dict, platform: str = "x") -> int:
    """Parse an X Account Activity API payload into incoming messages.

    Handles direct_message_events and tweet_create_events.
    Returns the number of new messages stored.
    """
    count = 0
    for ev in payload.get("direct_message_events", []):
        if ev.get("type") != "message_create":
            continue
        mc = ev.get("message_create", {})
        text = (mc.get("message_data", {}) or {}).get("text", "") or ""
        if not text:
            continue
        sender = (mc.get("sender_id", "") or "")[:200]
        external_id = (ev.get("id", "") or f"dm-{sender}")
        _store_incoming(platform, external_id, sender, text, ev)
        count += 1

    for tweet in payload.get("tweet_create_events", []):
        text = tweet.get("text", "") or ""
        user = tweet.get("user", {}) or {}
        screen = user.get("screen_name", "") or ""
        name = user.get("name", "") or screen
        if not text:
            continue
        sender = (name or screen or str(user.get("id", "")))[:200]
        external_id = (tweet.get("id_str", "") or f"tweet-{sender}")
        _store_incoming(platform, external_id, sender, text, tweet)
        count += 1
    return count


def list_incoming(limit: int = 50, platform: str = ""):
    from ..database import fetch
    if platform:
        rows = fetch(
            "SELECT * FROM incoming_messages WHERE platform=? ORDER BY id DESC LIMIT ?",
            [platform, limit],
        )
    else:
        rows = fetch(
            "SELECT * FROM incoming_messages ORDER BY id DESC LIMIT ?",
            [limit],
        )
    return rows


def status() -> dict:
    return {
        "meta_verify_token_set": bool(META_VERIFY_TOKEN),
        "x_crc_secret_set": bool(os.getenv("TWITTER_API_SECRET", "")),
        "endpoints": [
            "/api/webhooks/facebook",
            "/api/webhooks/instagram",
            "/api/webhooks/threads",
            "/api/webhooks/x",
        ],
    }
