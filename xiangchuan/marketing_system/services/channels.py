"""免費社群管道自動發佈（Telegram + Bluesky）。

設計重點
- 只用免費方案：Telegram Bot API、Bluesky atproto 公開 API，都不需要審核。
- 沒憑證就跳過（skipped），不算失敗，避免排程被雜訊淹沒。
- 每筆內容對每個管道只推一次（channel_pushes 記錄去重），並限制每日上限防止洗版。

環境變數
- TELEGRAM_BOT_TOKEN: Telegram bot token（沿用既有設定）
- TELEGRAM_PUSH_CHAT_IDS: 要推的頻道/群組，逗號分隔。公開頻組用 @channelusername
- BLUESKY_HANDLE: 你的 handle，例如 lewislunora.bsky.social
- BLUESKY_APP_PASSWORD: atproto app password（Bluesky 設定 → 進階 → App password）
"""

import logging
import re
import threading
import uuid
from datetime import datetime, timedelta

import requests

from ..config import BLUESKY_APP_PASSWORD, BLUESKY_HANDLE, TELEGRAM_BOT_TOKEN
from ..database import execute, fetch, fetch_one

logger = logging.getLogger(__name__)

TELEGRAM_PUSH_CHAT_IDS = [
    c.strip() for c in __import__("os").environ.get("TELEGRAM_PUSH_CHAT_IDS", "").split(",")
    if c.strip()
]

BSKY_API = "https://bsky.social/xrpc"
BSKY_MAX_CHARS = 300
DAILY_CAP = {"telegram": 3, "bluesky": 3}

_lock = threading.Lock()
_session_cache = {"accessJwt": None, "did": None, "expires": None}


def channels_configured() -> dict:
    return {
        "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_PUSH_CHAT_IDS),
        "bluesky": bool(BLUESKY_HANDLE and BLUESKY_APP_PASSWORD),
    }


def today_count(channel: str) -> int:
    """今日推播次數。pushed_at 由 SQLite 以 UTC 寫入，故用台灣日界換算。"""
    return fetch_one(
        "SELECT COUNT(*) AS c FROM channel_pushes "
        "WHERE channel=? AND date(pushed_at,'+8 hours')=date('now','+8 hours')",
        [channel],
    )["c"]


def _already_pushed(item_key: str, channel: str) -> bool:
    return bool(fetch_one(
        "SELECT id FROM channel_pushes WHERE item_key=? AND channel=?", [item_key, channel]
    ))


def _record(item_key: str, channel: str, title: str, ok: bool, detail: str = "") -> None:
    execute(
        "INSERT INTO channel_pushes (item_key, channel, title, ok, detail, pushed_at) "
        "VALUES (?,?,?,?,?,datetime('now'))",
        [item_key, channel, title[:120], 1 if ok else 0, detail[:300]],
    )


# ---------------------------------------------------------------- Telegram
def push_telegram(text: str) -> dict:
    if not TELEGRAM_BOT_TOKEN:
        return {"ok": False, "skipped": True, "detail": "未設定 TELEGRAM_BOT_TOKEN"}
    if not TELEGRAM_PUSH_CHAT_IDS:
        return {"ok": False, "skipped": True, "detail": "未設定 TELEGRAM_PUSH_CHAT_IDS"}
    sent, errors = 0, []
    for chat_id in TELEGRAM_PUSH_CHAT_IDS:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
                timeout=20,
            )
            if r.json().get("ok"):
                sent += 1
            else:
                errors.append(f"{chat_id}: {r.text[:120]}")
        except Exception as e:
            errors.append(f"{chat_id}: {e}")
    if sent:
        return {"ok": True, "detail": f"已送 {sent} 個頻道" + (f"｜失敗 {errors[0]}" if errors else "")}
    return {"ok": False, "detail": "; ".join(errors)[:250] or "全部失敗"}


# ---------------------------------------------------------------- Bluesky
def _bsky_session() -> dict:
    if _session_cache["accessJwt"] and _session_cache["expires"] > datetime.now():
        return _session_cache
    r = requests.post(f"{BSKY_API}/com.atproto.server.createSession",
                      json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD},
                      timeout=20)
    r.raise_for_status()
    d = r.json()
    _session_cache.update({
        "accessJwt": d["accessJwt"],
        "did": d["did"],
        "expires": datetime.now() + timedelta(minutes=45),
    })
    return _session_cache


def push_bluesky(text: str) -> dict:
    if not (BLUESKY_HANDLE and BLUESKY_APP_PASSWORD):
        return {"ok": False, "skipped": True, "detail": "未設定 BLUESKY_HANDLE/BLUESKY_APP_PASSWORD"}
    text = text.strip()
    if len(text) > BSKY_MAX_CHARS:
        text = text[: BSKY_MAX_CHARS - 1].rstrip() + "…"
    url = re.search(r"https?://\S+", text)
    try:
        sess = _bsky_session()
        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now().astimezone().isoformat(),
        }
        if url:
            record["facets"] = [{
                "$type": "app.bsky.richtext.facet#link",
                "features": [{
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": url.group(0).rstrip("、。）)"),
                }],
                "index": {
                    "byteStart": url.start(),
                    "byteEnd": url.end() - len(url.group(0).rstrip("、。）)")),
                },
            }]
        r = requests.post(
            f"{BSKY_API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {sess['accessJwt']}"},
            json={"repo": sess["did"], "collection": "app.bsky.feed.post",
                  "rkey": uuid.uuid4().hex, "record": record},
            timeout=20,
        )
        if r.status_code >= 400:
            # session 過期時清快取重試一次
            _session_cache["accessJwt"] = None
            sess = _bsky_session()
            r = requests.post(
                f"{BSKY_API}/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {sess['accessJwt']}"},
                json={"repo": sess["did"], "collection": "app.bsky.feed.post",
                      "rkey": uuid.uuid4().hex, "record": record},
                timeout=20,
            )
        if r.status_code >= 400:
            return {"ok": False, "detail": r.text[:200]}
        uri = r.json().get("uri", "")
        cid = (r.json().get("cid") or "")[:12]
        return {"ok": True, "detail": f"已發佈 {uri.rsplit('/', 1)[-1]}" + (f" ({cid})" if cid else "")}
    except Exception as e:
        logger.warning("bluesky push failed: %s", e)
        return {"ok": False, "detail": str(e)[:200]}


PUSHERS = {"telegram": push_telegram, "bluesky": push_bluesky}


# ---------------------------------------------------------------- 排程入口
def _pending_item() -> dict:
    """取最新且尚未推過的內容。"""
    from .promo import latest_content
    configured = channels_configured()
    for it in latest_content(limit_each=4):
        key = f"{it['kind']}:{it['url_path']}:{it.get('created_at', '')}"
        for ch, ready in configured.items():
            if ready and not _already_pushed(key, ch):
                return {**it, "item_key": key}
    return {}


def _build_text(item: dict) -> str:
    from .promo import _clip, _utm
    body = _clip(item.get("summary") or item.get("title", ""), 150)
    link = _utm(item["url_path"], "auto_push")
    return f"{body}\n\n{link}"


def auto_push(force_key: str = "") -> dict:
    """推送到所有已設定的免費管道。每筆內容每管道只推一次。"""
    results = {}
    with _lock:
        configured = channels_configured()
        if not any(configured.values()):
            return {"ok": False, "detail": "尚未設定任何社群管道憑證", "channels": results}
        if force_key:
            from .promo import latest_content
            cands = [i for i in latest_content(limit_each=8)
                     if f"{i['kind']}:{i['url_path']}:{i.get('created_at', '')}" == force_key]
            item = {**cands[0], "item_key": force_key} if cands else {}
        else:
            item = _pending_item()
        if not item:
            return {"ok": True, "detail": "沒有待推的新內容", "channels": results}

        text = _build_text(item)
        for ch, pusher in PUSHERS.items():
            if not configured[ch]:
                results[ch] = {"ok": False, "skipped": True, "detail": "未設定"}
                continue
            if _already_pushed(item["item_key"], ch):
                results[ch] = {"ok": True, "skipped": True, "detail": "已推過"}
                continue
            if today_count(ch) >= DAILY_CAP[ch]:
                results[ch] = {"ok": True, "skipped": True,
                               "detail": f"今日已達上限 {DAILY_CAP[ch]}"}
                continue
            r = pusher(text)
            results[ch] = r
            _record(item["item_key"], ch, item.get("title", ""), r.get("ok", False),
                    r.get("detail", ""))
    ok_any = any(r.get("ok") for r in results.values())
    return {"ok": ok_any, "item": item.get("title", ""),
            "detail": f"已推：{item.get('title', '')[:40]}" if ok_any else "所有管道都未成功",
            "channels": results}


def status() -> dict:
    cfg = channels_configured()
    return {
        "configured": cfg,
        "today": {ch: today_count(ch) for ch in PUSHERS},
        "cap": DAILY_CAP,
        "recent": fetch(
            "SELECT item_key, channel, title, ok, detail, pushed_at FROM channel_pushes "
            "ORDER BY id DESC LIMIT 10"
        ),
        "pending_item": (_pending_item() or {}).get("title", ""),
    }