import os
import json
import hashlib
import hmac
import secrets
import threading
import time
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

from ..database import init_db, execute, fetch, fetch_one
from student_platform.database import StudentDatabase
from student_platform.routes import router as student_router
from ..scheduler import ContentScheduler
from ..ai.generator import AIContentGenerator
from ..platforms.telegram_connector import TelegramConnector
from ..platforms.line_connector import LineConnector
from ..platforms.facebook_connector import FacebookConnector
from ..platforms.twitter_connector import TwitterConnector
from ..platforms.instagram_connector import InstagramConnector
from ..platforms.browser_automation import ThreadsConnector, DcardConnector, XiaohongshuConnector
from ..config import (
    PLATFORMS, DATA_DIR, DOCS_DIR,
    TELEGRAM_BOT_TOKEN, LINE_NOTIFY_TOKEN,
    LINE_CHANNEL_ACCESS_TOKEN, FACEBOOK_PAGE_TOKEN, INSTAGRAM_ACCESS_TOKEN,
)
from ..services.email_service import send_contact_email, is_configured as smtp_configured
from ..services.notification_service import notify_owner, send_telegram_notification
from ..services import platform_webhooks
from ..services.social_auth import (
    is_configured, configured_providers, authorize_url, exchange_and_profile,
    verify_telegram, encode_next, decode_next, PROVIDER_LABELS, TELEGRAM_BOT_USERNAME,
)
from ..services.openclaw_agent import _handle_command as openclaw_handle, _is_authorized as openclaw_authorized
from ..services.knowledge_base import get_kb_reply, save_unanswered, get_pending, auto_learn
from ..services.analytics import track_async, summary as analytics_summary

app = FastAPI(
    title="翔川 Neo｜曜科技 行銷自動化系統",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lewislunora.github.io",
        "https://lewislunora.onrender.com",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(student_router)

scheduler = ContentScheduler()
ai_generator = AIContentGenerator()

connectors = {}


def get_connectors(account_id=None):
    if account_id:
        acct = fetch_one("SELECT * FROM accounts WHERE id=?", [account_id])
        if not acct:
            raise HTTPException(404, "Account not found")
        creds = json.loads(acct["credentials"])
        return _build_connector(acct["platform"], creds)
    return connectors


def _build_connector(platform, creds):
    mapping = {
        "telegram": TelegramConnector,
        "line": LineConnector,
        "facebook": FacebookConnector,
        "twitter": TwitterConnector,
        "instagram": InstagramConnector,
        "threads": ThreadsConnector,
        "dcard": DcardConnector,
        "xiaohongshu": XiaohongshuConnector,
    }
    cls = mapping.get(platform)
    if not cls:
        raise HTTPException(400, f"Unsupported platform: {platform}")
    return cls(creds)


def _sync_scheduler_connectors():
    """從環境變數與資料庫帳號建立 connectors，註冊進 scheduler。

    讓排程發佈（scheduler._publish）能真正送到各平台：
    1. 環境變數提供預設（Telegram / Facebook / LINE）
    2. 資料庫 accounts 表中 enabled=1 的帳號覆蓋
    """
    built = {}
    if TELEGRAM_BOT_TOKEN:
        built.setdefault("telegram", TelegramConnector({
            "bot_token": TELEGRAM_BOT_TOKEN,
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        }))
    if FACEBOOK_PAGE_TOKEN:
        built.setdefault("facebook", FacebookConnector({"page_token": FACEBOOK_PAGE_TOKEN}))
    if LINE_CHANNEL_ACCESS_TOKEN:
        built.setdefault("line", LineConnector({"access_token": LINE_CHANNEL_ACCESS_TOKEN}))
    if INSTAGRAM_ACCESS_TOKEN:
        built.setdefault("instagram", InstagramConnector({"access_token": INSTAGRAM_ACCESS_TOKEN}))

    try:
        rows = fetch("SELECT * FROM accounts WHERE enabled=1")
        for acct in rows:
            try:
                creds = json.loads(acct["credentials"] or "{}")
                if not isinstance(creds, dict) or not any(str(v).strip() for v in creds.values()):
                    continue
                built[acct["platform"]] = _build_connector(acct["platform"], creds)
            except Exception as e:
                logger.error(f"Connector build failed ({acct['platform']}): {e}")
    except Exception as e:
        logger.error(f"Sync connectors (accounts) failed: {e}")

    scheduler.connectors = built
    connectors.clear()
    connectors.update(built)
    logger.info(f"Connectors synced: {sorted(built)}")
    return built


class ContentCreate(BaseModel):
    title: str
    body: str
    platforms: list
    scheduled_at: Optional[str] = None
    language: str = "zh-TW"
    category: str = ""
    media_urls: list = []


class ScheduleCreate(BaseModel):
    content_id: int
    platforms: list
    scheduled_at: str


class KBEntryCreate(BaseModel):
    keywords: list[str]
    answer: str
    language: str = "zh-TW"


class AIGenerateRequest(BaseModel):
    template: str = "社群貼文"
    variables: dict = {}


class AccountCreate(BaseModel):
    platform: str
    label: str = ""
    credentials: dict = {}


@app.on_event("startup")
def startup():
    init_db()
    StudentDatabase.init_db()
    _sync_scheduler_connectors()
    scheduler.start()
    try:
        import requests as http
        base = os.getenv("RENDER_EXTERNAL_URL", f"https://lewislunora.onrender.com")
        webhook_url = f"{base}/api/telegram/webhook"
        http.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}", timeout=10)
    except Exception:
        pass


@app.on_event("shutdown")
def shutdown():
    scheduler.stop()


@app.get("/api/status")
def status():
    from ..services.email_service import channel_summary
    return {
        "ai_available": ai_generator.is_available(),
        "smtp_configured": smtp_configured(),
        "email_channel": channel_summary(),
        "telegram_bot_token_set": bool(TELEGRAM_BOT_TOKEN),
        "line_notify_configured": bool(LINE_NOTIFY_TOKEN),
        "platform_webhooks": platform_webhooks.status(),
        "database_type": "sqlite",
        "scheduler": scheduler.get_status_summary(),
        "platforms": {k: (k in scheduler.connectors) for k in PLATFORMS},
    }


@app.get("/api/notify/test")
def notify_test():
    """Synchronously test all notification channels and report results."""
    from ..services import notification_service
    from ..services.email_service import channel_summary
    results = {
        "telegram": notification_service._send_telegram(
            "✅ [測試] 翔川 Neo 即時通知測試 — Telegram 管道正常"
        ),
        "line": notification_service._send_line_notify(
            "✅ [測試] 翔川 Neo 即時通知測試 — LINE 管道正常"
        ),
        "email": notification_service._send_email(
            "✅ [測試] 翔川 Neo 即時通知",
            "這是翔川 Neo 即時通知系統的測試信件。收到代表 Email 管道正常。"
        ),
    }
    return {
        "results": results,
        "email_channel": channel_summary(),
        "line_notify_configured": bool(LINE_NOTIFY_TOKEN),
        "smtp_configured": smtp_configured(),
    }


@app.get("/api/openclaw")
def openclaw_info():
    import requests as http
    info = {"bot_username": "ailunora_bot", "bot_link": "https://t.me/ailunora_bot"}
    try:
        r = http.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=5)
        if r.ok:
            d = r.json()
            if d.get("ok") and d.get("result", {}).get("username"):
                info["bot_username"] = d["result"]["username"]
                info["bot_link"] = f"https://t.me/{d['result']['username']}"
    except Exception:
        pass
    return {"status": "ok", "data": info}


@app.post("/api/analytics/track")
async def analytics_track(request: Request):
    body = await request.json()
    page = body.get("page", "/")
    ref = body.get("ref", "")
    ua = request.headers.get("user-agent", "")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "") or ""
    ip = ip.split(",")[0].strip()
    track_async(page, ref, ua, ip)
    return {"ok": True}


@app.get("/api/analytics/summary")
def analytics_summary_endpoint(since: int = 24):
    return analytics_summary(since_hours=since)


def _notify_contact(data: dict):
    try:
        notify_owner("contact", data, url="https://lewislunora.onrender.com/")
    except Exception as e:
        logger.error(f"Contact notification failed: {e}")

    # LINE Messaging API direct push
    try:
        line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        line_chat_id = os.getenv("LINE_CHAT_ID", "")
        if line_token and line_chat_id:
            msg = "🔔 新預約諮詢\n"
            for k, v in [("姓名", "姓名"), ("聯絡方式", "聯絡方式"),
                         ("公司", "公司"), ("行業別", "行業別"),
                         ("需求", "需求"), ("備註", "備註")]:
                val = data.get(k, "").strip()
                if val:
                    msg += f"・{v}：{val}\n"
            import requests as _r
            _r.post(
                "https://api.line.me/v2/bot/message/push",
                headers={"Authorization": f"Bearer {line_token}"},
                json={"to": line_chat_id, "messages": [{"type": "text", "text": msg}]},
                timeout=10,
            )
    except Exception as e:
        logger.error(f"LINE push failed: {e}")

@app.post("/api/contact")
async def contact_form(request: Request):
    data = await request.json()
    required = ["姓名", "聯絡方式"]
    for field in required:
        if not data.get(field, "").strip():
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": f"缺少必填欄位：{field}"},
            )
    cid = execute(
        "INSERT INTO contacts (name, company, contact, email, industry, message) VALUES (?, ?, ?, ?, ?, ?)",
        [
            data.get("姓名", ""),
            data.get("公司", ""),
            data.get("聯絡方式", ""),
            data.get("Email", ""),
            data.get("行業別", ""),
            data.get("備註", ""),
        ],
    )
    threading.Thread(target=_notify_contact, args=[data], daemon=True).start()
    return {"status": "ok", "id": cid}


@app.get("/api/contacts")
def list_contacts(page: int = 1, per_page: int = 50):
    offset = (page - 1) * per_page
    items = fetch(
        "SELECT * FROM contacts ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [per_page, offset],
    )
    total = fetch("SELECT COUNT(*) as c FROM contacts")[0]["c"]
    return {"items": items, "total": total, "page": page}


@app.post("/api/content")
def create_content(data: ContentCreate):
    cid = execute(
        "INSERT INTO contents (title, body, platforms, scheduled_at, status, language, category, media_urls) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [data.title, data.body, json.dumps(data.platforms), data.scheduled_at or datetime.now().strftime("%Y-%m-%d %H:%M"), "scheduled" if data.scheduled_at else "draft", data.language, data.category, json.dumps(data.media_urls)]
    )
    if data.scheduled_at and data.platforms:
        scheduler.schedule_content(cid, data.platforms, data.scheduled_at)
    return {"id": cid, "status": "created"}


@app.get("/api/content")
def list_contents(status: str = None, page: int = 1, per_page: int = 20):
    where = ""
    params = []
    if status:
        where = "WHERE status=?"
        params.append(status)
    offset = (page - 1) * per_page
    items = fetch(f"SELECT * FROM contents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [per_page, offset])
    total = fetch(f"SELECT COUNT(*) as c FROM contents {where}", params)[0]["c"]
    return {"items": items, "total": total, "page": page}


@app.get("/api/content/{content_id}")
def get_content(content_id: int):
    item = fetch_one("SELECT * FROM contents WHERE id=?", [content_id])
    if not item:
        raise HTTPException(404, "Content not found")
    item["schedules"] = fetch("SELECT * FROM schedules WHERE content_id=?", [content_id])
    return item


@app.delete("/api/content/{content_id}")
def delete_content(content_id: int):
    execute("DELETE FROM schedules WHERE content_id=?", [content_id])
    execute("DELETE FROM analytics WHERE content_id=?", [content_id])
    execute("DELETE FROM contents WHERE id=?", [content_id])
    return {"status": "deleted"}


@app.post("/api/content/{content_id}/publish")
def publish_now(content_id: int):
    item = fetch_one("SELECT * FROM contents WHERE id=?", [content_id])
    if not item:
        raise HTTPException(404, "Content not found")
    platforms = json.loads(item["platforms"])
    results = {}
    for platform in platforms:
        connector = _build_connector(platform, {})
        try:
            result = connector.post(item["body"], media_urls=json.loads(item.get("media_urls", "[]")))
            results[platform] = result
            execute("INSERT INTO schedules (content_id, platform, scheduled_at, status) VALUES (?, ?, datetime('now'), 'done')", [content_id, platform])
        except Exception as e:
            results[platform] = {"error": str(e)}
            execute("INSERT INTO schedules (content_id, platform, scheduled_at, status, error) VALUES (?, ?, datetime('now'), 'failed', ?)", [content_id, platform, str(e)])
    execute("UPDATE contents SET status='published', published_at=datetime('now') WHERE id=?", [content_id])
    return {"results": results}


@app.post("/api/content/ai-generate")
def ai_generate(data: AIGenerateRequest):
    if not ai_generator.is_available():
        return {"text": "⚠️ Groq API 未設定，請設定 GROQ_API_KEY 環境變數。", "fallback": True}
    result = ai_generator.generate(data.template, data.variables)
    return {"text": result}


@app.post("/api/accounts")
def create_account(data: AccountCreate):
    cid = execute(
        "INSERT INTO accounts (platform, label, credentials) VALUES (?, ?, ?)",
        [data.platform, data.label, json.dumps(data.credentials)]
    )
    _sync_scheduler_connectors()
    return {"id": cid, "status": "created"}


@app.get("/api/accounts")
def list_accounts():
    rows = fetch("SELECT * FROM accounts ORDER BY created_at DESC")
    for row in rows:
        row["credentials"] = "***"
    return {"items": rows}


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    execute("DELETE FROM accounts WHERE id=?", [account_id])
    _sync_scheduler_connectors()
    return {"status": "deleted"}


@app.post("/api/accounts/{account_id}/verify")
def verify_account(account_id: int):
    connector = get_connectors(account_id)
    ok = connector.verify()
    return {"verified": ok}


@app.get("/api/schedules")
def list_schedules(status: str = None, page: int = 1, per_page: int = 50):
    where = ""
    params = []
    if status:
        where = "WHERE s.status=?"
        params.append(status)
    offset = (page - 1) * per_page
    items = fetch(
        f"SELECT s.*, c.title, c.body FROM schedules s JOIN contents c ON s.content_id = c.id {where} ORDER BY s.scheduled_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    )
    total = fetch(f"SELECT COUNT(*) as c FROM schedules s {where}", params)[0]["c"]
    return {"items": items, "total": total, "page": page}


@app.get("/api/analytics")
def get_analytics(days: int = 7):
    items = fetch(
        "SELECT platform, COUNT(*) as posts, SUM(views) as total_views, SUM(likes) as total_likes FROM analytics WHERE recorded_at >= datetime('now', ?) GROUP BY platform",
        [f"-{days} days"]
    )
    return {"items": items}


@app.get("/api/kb")
def list_kb(language: str = None):
    if language:
        items = fetch("SELECT * FROM kb_entries WHERE language=? ORDER BY id", [language])
    else:
        items = fetch("SELECT * FROM kb_entries ORDER BY language, id")
    for i in items:
        i["keywords"] = json.loads(i["keywords"])
    return {"items": items}


@app.post("/api/kb")
def create_kb(data: KBEntryCreate):
    cid = execute(
        "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
        [json.dumps(data.keywords, ensure_ascii=False), data.answer, data.language],
    )
    return {"id": cid, "status": "created"}


@app.put("/api/kb/{kid}")
def update_kb(kid: int, data: KBEntryCreate):
    execute(
        "UPDATE kb_entries SET keywords=?, answer=?, language=?, updated_at=datetime('now') WHERE id=?",
        [json.dumps(data.keywords, ensure_ascii=False), data.answer, data.language, kid],
    )
    return {"status": "updated"}


@app.delete("/api/kb/{kid}")
def delete_kb(kid: int):
    execute("DELETE FROM kb_entries WHERE id=?", [kid])
    return {"status": "deleted"}


@app.get("/api/kb/pending")
def list_pending(page: int = 1):
    return get_pending(page)


@app.post("/api/kb/pending/auto-learn")
def trigger_auto_learn():
    from ..services.knowledge_base import auto_learn
    auto_learn()
    return {"status": "ok"}


@app.post("/api/kb/pending/{pid}/suggest")
def suggest_pending(pid: int):
    row = fetch_one("SELECT * FROM kb_pending WHERE id=?", [pid])
    if not row:
        raise HTTPException(404, "Not found")
    from ..ai.generator import AIContentGenerator
    gen = AIContentGenerator()
    suggest = ""
    if gen.is_available():
        try:
            resp = gen.generate("custom", {"prompt": f"根據以下問題，用{row['language']}產生一個簡短回答（50字內）：{row['question']}"})
            if resp and not resp.startswith("❌"):
                suggest = resp
        except Exception:
            pass
    return {"question": row["question"], "language": row["language"], "ai_suggest": suggest}


@app.post("/api/kb/query")
async def kb_query(request: Request):
    body = await request.json()
    text = body.get("text", "")
    if not text:
        raise HTTPException(400, "Missing text")
    from ..services.knowledge_base import get_kb_reply
    reply = get_kb_reply(text)
    return {"reply": reply}


@app.post("/api/kb/pending/{pid}/reject")
def reject_pending(pid: int):
    execute("UPDATE kb_pending SET status='rejected' WHERE id=?", [pid])
    return {"status": "rejected"}


@app.post("/api/telegram/broadcast")
def telegram_broadcast(text: str = None):
    if not text:
        raise HTTPException(400, "Missing text")
    groups = fetch("SELECT * FROM accounts WHERE platform='telegram_chat'")
    token = TELEGRAM_BOT_TOKEN
    results = []
    for g in groups:
        try:
            creds = json.loads(g["credentials"])
            cid = creds.get("chat_id")
            if cid:
                import requests as req
                r = req.post(f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
                results.append({"chat": g["label"], "ok": r.json().get("ok", False)})
        except Exception as e:
            results.append({"chat": g["label"], "error": str(e)})
    return {"broadcast": results, "total": len(results)}


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    body = await request.json()
    msg = body.get("message") or body.get("channel_post") or {}
    chat = msg.get("chat", {})
    cid = chat.get("id")
    text = (msg.get("text") or "").strip()
    chat_type = chat.get("type", "private")

    if not cid or not text:
        return {"ok": True}

    is_bot_command = text.startswith("/")
    is_group = chat_type in ("group", "supergroup", "channel")
    bot_username = "ailunora_bot"

    mentioned = bot_username in text.lower() if is_group else True

    if is_group:
        execute(
            "INSERT OR IGNORE INTO accounts (platform, label, credentials) VALUES (?, ?, ?)",
            ["telegram_chat", chat.get("title", str(cid)), json.dumps({"chat_id": cid, "type": chat_type})],
        )

    if is_bot_command:
        cmd_parts = text[1:].split(maxsplit=1)
        cmd = cmd_parts[0].lower()
        cmd_args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        if cmd in ("start", "help"):
            reply = (
                "🤖 歡迎使用 @ailunora_bot！\n\n"
                "你可以問我：\n"
                "• 方案與價格\n"
                "• 功能介紹\n"
                "• 平台支援\n"
                "• 如何開始\n"
                "• 其他行銷相關問題\n\n"
                "💡 *OpenClaw 指令*\n"
                "• /靈感 [主題] — 產生內容靈感\n"
                "• /部署 — 觸發網站部署\n"
                "• /狀態 — 查看系統狀態\n\n"
                "或在群組中 @ailunora_bot 你的問題"
            )
        elif cmd in ("靈感", "idea", "部署", "deploy", "狀態", "status"):
            if openclaw_authorized(cid):
                reply = openclaw_handle(cid, cmd, cmd_args)
            else:
                reply = "⛔ 未授權的使用者。"
        else:
            return {"ok": True}
    elif not mentioned:
        return {"ok": True}
    else:
        clean = text.replace(f"@{bot_username}", "").strip() if is_group else text
        reply = get_kb_reply(clean)
        if not reply:
            save_unanswered(clean, "zh-TW")
            reply = (
                "🤖 抱歉，這個問題我還不太會回答，已記錄給管理員學習。\n\n"
                "你可以問我：\n"
                "• 方案與價格\n"
                "• 功能介紹\n"
                "• 平台支援\n"
                "• 如何開始\n"
                "• 其他行銷相關問題"
            )

    msg_id = msg.get("message_id")

    token = TELEGRAM_BOT_TOKEN
    try:
        import requests as req
        payload = {"chat_id": cid, "text": reply, "parse_mode": "HTML"}
        if msg_id:
            payload["reply_to_message_id"] = msg_id
        req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
        )
    except Exception:
        pass

    return {"ok": True}


# ── Platform webhooks (FB / IG / Threads / X 即時接收) ────────────────
def _webhook_platform(request):
    path = request.url.path
    for p in ("facebook", "instagram", "threads", "x"):
        if f"/{p}" in path:
            return p
    return "facebook"


@app.api_route("/api/webhooks/facebook", methods=["GET", "POST"])
@app.api_route("/api/webhooks/instagram", methods=["GET", "POST"])
@app.api_route("/api/webhooks/threads", methods=["GET", "POST"])
@app.api_route("/api/webhooks/x", methods=["GET", "POST"])
async def platform_webhook_endpoint(request: Request):
    platform = _webhook_platform(request)

    if request.method == "GET":
        if platform == "x":
            resp = platform_webhooks.verify_x(dict(request.query_params))
            if resp:
                return JSONResponse(resp)
            return JSONResponse({"status": "error", "message": "Invalid CRC token"}, status_code=403)
        challenge = platform_webhooks.verify_meta(dict(request.query_params))
        if challenge:
            return Response(content=challenge, media_type="text/plain")
        return JSONResponse({"status": "error", "message": "Invalid verify token"}, status_code=403)

    try:
        body = await request.json()
    except Exception:
        body = {}
    if platform == "x":
        count = platform_webhooks.process_x_payload(body)
    else:
        count = platform_webhooks.process_meta_payload(body, platform)
    return {"status": "ok", "received": count}


@app.get("/api/incoming-messages")
def incoming_messages(limit: int = 50, platform: str = ""):
    return {"items": platform_webhooks.list_incoming(limit, platform)}


@app.get("/api/backup")
def backup_database():
    tables = ["contents", "schedules", "analytics", "contacts", "accounts", "ai_templates"]
    data = {}
    for t in tables:
        try:
            data[t] = fetch(f"SELECT * FROM {t}")
        except Exception:
            data[t] = []
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = DATA_DIR / f"backup_{now}.json"
    backup_path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    return {"status": "ok", "file": backup_path.name, "tables": {t: len(data[t]) for t in tables}}


@app.get("/api/config")
def client_config():
    return {
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
    }


@app.get("/api/templates")
def list_templates():
    return {"items": fetch("SELECT * FROM ai_templates")}


class AuthRegister(BaseModel):
    email: str
    password: str


class AuthLogin(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
def auth_register(body: AuthRegister):
    email = body.email.strip().lower()
    existing = fetch_one("SELECT id FROM users WHERE email=? OR username=?", (email, email))
    if existing:
        raise HTTPException(400, "此 Email 已經註冊過")
    salt = secrets.token_hex(8)
    pw_hash = hashlib.sha256((body.password + salt).encode()).hexdigest()
    token = secrets.token_hex(24)
    execute("INSERT INTO users (username, email, password_hash, salt, token) VALUES (?,?,?,?,?)",
            (email, email, pw_hash, salt, token))
    return {"token": token, "email": email, "name": email.split("@")[0]}


@app.post("/api/auth/login")
def auth_login(body: AuthLogin):
    email = body.email.strip().lower()
    row = fetch_one("SELECT id,password_hash,salt,token FROM users WHERE email=? OR username=?", (email, email))
    if not row:
        raise HTTPException(401, "Email 或密碼錯誤")
    pw_hash = hashlib.sha256((body.password + row["salt"]).encode()).hexdigest()
    if pw_hash != row["password_hash"]:
        raise HTTPException(401, "Email 或密碼錯誤")
    token = row["token"] or secrets.token_hex(24)
    if not row["token"]:
        execute("UPDATE users SET token=? WHERE id=?", (token, row["id"]))
    return {"token": token, "email": email, "name": email.split("@")[0]}


@app.get("/api/auth/me")
def auth_me(request: Request, token: str = ""):
    u = _current_user(request, token)
    if not u:
        raise HTTPException(401, "未登入")
    return _user_dict(u)


@app.get("/api/auth/providers")
def auth_providers(request: Request):
    base = str(request.base_url).rstrip("/")
    providers = []
    for p in configured_providers():
        item = {"id": p, "name": PROVIDER_LABELS[p], "authorize_url": f"{base}/api/auth/oauth/{p}/authorize"}
        if p == "telegram":
            item["authorize_url"] = f"{base}/api/auth/telegram/start"
        providers.append(item)
    return {"providers": providers, "email_password": True}


def _login_or_register(provider, profile):
    """依 provider profile 找尋或建立使用者，回傳 {token, user}。"""
    row = fetch_one("SELECT user_id FROM social_identities WHERE provider=? AND provider_id=?",
                    (provider, profile["provider_id"]))
    user = None
    if row:
        user = fetch_one("SELECT id, token FROM users WHERE id=? AND is_active=1", (row["user_id"],))
    if not user and profile.get("email"):
        user = fetch_one("SELECT id, token FROM users WHERE email=? AND is_active=1", (profile["email"],))
    if not user:
        base = (profile.get("name") or (profile.get("email") or "").split("@")[0] or f"{provider}_user")[:24]
        username = base
        suffix = 1
        while fetch_one("SELECT id FROM users WHERE username=?", (username,)):
            username = f"{base}_{suffix}"
            suffix += 1
        user_id = execute(
            "INSERT INTO users (username, email, password_hash, salt, token, name, avatar) VALUES (?,?,?,?,?,?,?)",
            (username, profile.get("email", ""), "", "", secrets.token_hex(24),
             profile.get("name", ""), profile.get("avatar", "")))
        user = fetch_one("SELECT id, token FROM users WHERE id=?", (user_id,))
    else:
        if user and user["token"] is None or not user["token"]:
            token = secrets.token_hex(24)
            execute("UPDATE users SET token=? WHERE id=?", (token, user["id"]))
            user["token"] = token
        if profile.get("avatar"):
            execute("UPDATE users SET avatar=? WHERE id=? AND avatar=''", (profile["avatar"], user["id"]))
        if profile.get("name"):
            execute("UPDATE users SET name=? WHERE id=? AND name=''", (profile["name"], user["id"]))
    if not row:
        execute("INSERT OR IGNORE INTO social_identities (user_id, provider, provider_id) VALUES (?,?,?)",
                (user["id"], provider, profile["provider_id"]))
    return user


def _safe_next(next_path: str, request: Request) -> str:
    """允許站內路徑或本站 / GH Pages 完整網址，避免開放轉址。"""
    if not next_path or next_path.startswith("//"):
        return ""
    if next_path.startswith("/"):
        return next_path
    base = str(request.base_url).rstrip("/")
    allowed = [u for u in ("https://lewislunora.github.io", base) if u]
    return next_path if any(next_path.startswith(u) for u in allowed) else ""


def _set_token_cookie(resp, token, request, max_age=86400 * 90):
    secure = str(request.base_url).startswith("https://")
    resp.set_cookie("token", token, httponly=True,
                    samesite="none" if secure else "lax",
                    secure=secure, max_age=max_age, path="/")
    return resp


@app.get("/api/auth/oauth/{provider}/authorize")
def oauth_authorize(provider: str, request: Request, next: str = ""):
    if provider not in ("google", "facebook", "instagram", "line") or not is_configured(provider):
        raise HTTPException(404, "此登入方式尚未設定")
    url, state = authorize_url(provider, _safe_next(next, request))
    resp = RedirectResponse(url)
    resp.set_cookie("oauth_state", state["state"], httponly=True, samesite="lax", max_age=600, path="/")
    resp.set_cookie("oauth_next", encode_next(state["next"]), httponly=True, samesite="lax", max_age=600, path="/")
    return resp


@app.get("/api/auth/oauth/{provider}/callback")
def oauth_callback(provider: str, request: Request, code: str = "", state: str = "", error: str = ""):
    if provider not in ("google", "facebook", "instagram", "line"):
        raise HTTPException(404, "此登入方式尚未設定")
    saved_state = request.cookies.get("oauth_state", "")
    next_path = _safe_next(decode_next(request.cookies.get("oauth_next", "")), request)
    if error or not code or not saved_state or not hmac.compare_digest(saved_state, state):
        raise HTTPException(400, "登入失敗或授權逾時，請重試")
    try:
        profile = exchange_and_profile(provider, code)
    except Exception as e:
        raise HTTPException(502, f"取得帳號資料失敗: {e}")
    user = _login_or_register(provider, profile)
    target = f"{next_path}{'&' if '?' in next_path else '?'}ok=1" if next_path else "/login.html?ok=1"
    resp = RedirectResponse(target)
    resp.delete_cookie("oauth_state", path="/")
    resp.delete_cookie("oauth_next", path="/")
    _set_token_cookie(resp, user["token"], request)
    return resp


@app.get("/api/auth/telegram/start")
def telegram_start(request: Request, next: str = ""):
    if not is_configured("telegram"):
        raise HTTPException(404, "Telegram 登入尚未設定")
    widget = f"""
<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram 登入</title>
<style>
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:24px;
background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h2{{font-weight:600;margin:0}}
p{{color:#94a3b8;margin:0;font-size:14px}}
#tg-widget{{display:flex;justify-content:center}}
a{{color:#38bdf8;font-size:13px}}
</style></head><body>
<h2>使用 Telegram 登入</h2>
<p>點下方按鈕，在 Telegram 中授權後自動登入</p>
<div id="tg-widget"></div>
<a href="/login.html">← 返回登入頁</a>
<script src="https://telegram.org/js/telegram-widget.js?22"></script>
<script>
new TelegramLoginWidget({{"data-telegram-login":"{TELEGRAM_BOT_USERNAME}",
"data-auth-url":"/api/auth/telegram/callback","data-size":"large","data-request-access":"write"}});
</script>
</body></html>"""
    resp = HTMLResponse(widget)
    safe_next = _safe_next(next, request)
    if safe_next:
        resp.set_cookie("oauth_next", encode_next(safe_next), httponly=True, samesite="lax", max_age=600, path="/")
    return resp


@app.post("/api/auth/telegram/callback")
async def telegram_callback(request: Request):
    if not is_configured("telegram"):
        raise HTTPException(404, "Telegram 登入尚未設定")
    form = await request.form()
    try:
        profile = verify_telegram(dict(form))
    except ValueError as e:
        raise HTTPException(400, str(e))
    user = _login_or_register("telegram", profile)
    next_path = _safe_next(decode_next(request.cookies.get("oauth_next", "")), request)
    resp = RedirectResponse(next_path or "/login.html?ok=1")
    _set_token_cookie(resp, user["token"], request)
    resp.delete_cookie("oauth_next", path="/")
    return resp


@app.get("/api/auth/set-cookie")
def auth_set_cookie(request: Request, token: str = "", next: str = ""):
    if not token or not fetch_one("SELECT id FROM users WHERE token=?", (token,)):
        raise HTTPException(401, "Token 無效")
    resp = RedirectResponse(_safe_next(next, request) or "/login.html?ok=1")
    _set_token_cookie(resp, token, request)
    return resp


@app.get("/api/auth/logout")
def auth_logout(request: Request, next: str = ""):
    secure = str(request.base_url).startswith("https://")
    resp = RedirectResponse(_safe_next(next, request) or "/login.html")
    resp.delete_cookie("token", path="/",
                       samesite="none" if secure else "lax", secure=secure)
    return resp


@app.get("/dashboard")
async def dashboard():
    html_path = DATA_DIR.parent / "frontend" / "dashboard.html"
    html = html_path.read_text(encoding="utf-8")
    guard = '<script src="/auth-guard.js"></script>'
    wcss = '<link rel="stylesheet" href="/widget.css">'
    wjs = '<script src="/widget.js"></script>'
    if guard not in html:
        html = html.replace("<head>", "<head>\n" + guard + "\n" + wcss + "\n" + wjs)
    return HTMLResponse(html)



@app.get("/")
async def root():
    landing = DOCS_DIR / "index.html"
    if landing.exists():
        return HTMLResponse(landing.read_text(encoding="utf-8"))
    return {"name": "翔川 Neo｜曜科技 行銷自動化系統", "version": "1.0"}


async def _serve_sub(path: str):
    fp = DOCS_DIR / path / "index.html"
    if fp.exists():
        return HTMLResponse(fp.read_text(encoding="utf-8"))
    raise HTTPException(404, "Not found")


@app.get("/99u")
@app.get("/99u/")
async def serve_99u(): return await _serve_sub("99u")


@app.get("/ai-brand")
@app.get("/ai-brand/")
async def serve_ai_brand(): return await _serve_sub("ai-brand")


@app.get("/guides")
@app.get("/guides/")
async def serve_guides(): return await _serve_sub("guides")


@app.get("/solopreneur")
@app.get("/solopreneur/")
async def serve_solopreneur(): return await _serve_sub("solopreneur")


@app.get("/games")
@app.get("/games/")
async def serve_games(): return await _serve_sub("games")


@app.get("/admin/analytics")
@app.get("/admin/analytics/")
async def serve_admin_analytics():
    fp = DOCS_DIR / "admin" / "analytics.html"
    if fp.exists():
        return HTMLResponse(fp.read_text(encoding="utf-8"))
    raise HTTPException(404, "Not found")


@app.get("/student")
@app.get("/student/")
async def serve_student():
    from fastapi.responses import FileResponse
    path = DOCS_DIR / "student" / "index.html"
    if path.exists():
        return FileResponse(str(path))
    return HTMLResponse("<h1>學生平台</h1><p>敬請期待</p>")

def _make_student_route(page):
    @app.get(f"/student/{page}")
    @app.get(f"/student/{page}/")
    async def _handler():
        from fastapi.responses import FileResponse
        p = DOCS_DIR / "student" / f"{page}.html"
        if p.exists():
            return FileResponse(str(p))
        return HTMLResponse("<h1>頁面不存在</h1>")
    _handler.__name__ = f"serve_student_{page}"
    return _handler

for _sp in ["dashboard", "tasks", "rewards", "history", "profile", "admin"]:
    _make_student_route(_sp)


class GameQuestion(BaseModel):
    topic: str
    question: str


@app.post("/api/game/questions")
async def game_20questions(body: GameQuestion):
    from ..ai.generator import AIContentGenerator
    gen = AIContentGenerator()
    if not gen.is_available():
        return JSONResponse({"answer": "不確定", "hint_level": 0, "fallback": True})
    prompt = (
        f"你正在玩 20 問遊戲。你心裡想的是「{body.topic}」。\n"
        f"玩家問：{body.question}\n\n"
        f"請用「是」「否」「不確定」其中一個詞回答。\n"
        f"如果問題與「{body.topic}」直接相關，回答「是」或「否」。\n"
        f"如果問題模糊或無法確定，回答「不確定」。\n"
        f"只回答一個詞，不要加任何解釋。"
    )
    try:
        resp = gen.generate("custom", {"prompt": prompt})
        answer = resp.strip() if resp else "不確定"
        if answer not in ("是", "否"):
            answer = "不確定"
        return JSONResponse({"answer": answer, "hint_level": 0})
    except Exception:
        return JSONResponse({"answer": "不確定", "hint_level": 0})


class CommentCreate(BaseModel):
    page_path: str
    author_name: str = "匿名"
    content: str
    parent_id: Optional[int] = None


class ReactionToggle(BaseModel):
    page_path: str
    emoji: str


class FeedPostCreate(BaseModel):
    content: str
    post_type: str = "tip"
    author: str = "翔川 Neo"


class ThreadCreate(BaseModel):
    title: str
    content: str
    author_name: str = "匿名"
    is_anonymous: bool = True


class ThreadReplyCreate(BaseModel):
    content: str
    author_name: str = "匿名"
    is_anonymous: bool = True


class ChatOpen(BaseModel):
    user_id: int


class MessageSend(BaseModel):
    conversation_id: Optional[int] = None
    to_user_id: Optional[int] = None
    body: str


class FollowToggle(BaseModel):
    user_id: int


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None


class FeedCommentCreate(BaseModel):
    content: str


@app.post("/api/comments")
def create_comment(data: CommentCreate):
    cid = execute(
        "INSERT INTO comments (page_path, author_name, content, parent_id) VALUES (?, ?, ?, ?)",
        [data.page_path, data.author_name.strip() or "匿名", data.content, data.parent_id],
    )
    row = fetch_one("SELECT * FROM comments WHERE id=?", [cid])
    try:
        notify_owner("comment", {
            "author_name": data.author_name.strip() or "匿名",
            "content": data.content,
            "page_path": data.page_path,
        }, url=f"https://lewislunora.onrender.com{data.page_path}")
    except Exception:
        pass
    return {"status": "ok", "comment": row}


@app.get("/api/comments")
def list_comments(path: str = ""):
    if not path:
        return {"items": []}
    rows = fetch(
        "SELECT * FROM comments WHERE page_path=? ORDER BY created_at ASC",
        [path],
    )
    tree = {}
    top = []
    for r in rows:
        r["replies"] = []
        tree[r["id"]] = r
    for r in rows:
        if r["parent_id"] and r["parent_id"] in tree:
            tree[r["parent_id"]]["replies"].append(r)
        else:
            top.append(r)
    return {"items": top}


@app.delete("/api/comments/{comment_id}")
def delete_comment(comment_id: int):
    execute("DELETE FROM comments WHERE id=?", [comment_id])
    return {"status": "deleted"}


@app.post("/api/reactions/toggle")
def toggle_reaction(data: ReactionToggle):
    existing = fetch_one(
        "SELECT id FROM reactions WHERE page_path=? AND emoji=?",
        [data.page_path, data.emoji],
    )
    if existing:
        execute("DELETE FROM reactions WHERE id=?", [existing["id"]])
        return {"status": "removed"}
    execute(
        "INSERT INTO reactions (page_path, emoji) VALUES (?, ?)",
        [data.page_path, data.emoji],
    )
    return {"status": "added"}


@app.get("/api/reactions")
def get_reactions(path: str = ""):
    if not path:
        return {"items": []}
    rows = fetch(
        "SELECT emoji, COUNT(*) as count FROM reactions WHERE page_path=? GROUP BY emoji ORDER BY count DESC",
        [path],
    )
    return {"items": rows}


@app.post("/api/community/threads")
def create_thread(data: ThreadCreate):
    tid = execute(
        "INSERT INTO community_threads (title, content, author_name, is_anonymous) VALUES (?, ?, ?, ?)",
        [data.title, data.content, data.author_name.strip() or "匿名", int(data.is_anonymous)],
    )
    row = fetch_one("SELECT * FROM community_threads WHERE id=?", [tid])
    try:
        notify_owner("thread", {
            "title": data.title,
            "content": data.content,
            "author_name": data.author_name.strip() or "匿名",
        }, url=f"https://lewislunora.onrender.com/community/?thread={tid}")
    except Exception:
        pass
    return {"status": "ok", "thread": row}


@app.get("/api/community/threads")
def list_threads(sort: str = "latest", page: int = 1, per_page: int = 20):
    offset = (page - 1) * per_page
    order = "created_at DESC"
    if sort == "hot":
        order = "(view_count + reply_count * 2) DESC, created_at DESC"
    items = fetch(
        f"SELECT * FROM community_threads ORDER BY {order} LIMIT ? OFFSET ?",
        [per_page, offset],
    )
    total = fetch("SELECT COUNT(*) as c FROM community_threads")[0]["c"]
    return {"items": items, "total": total, "page": page}


@app.get("/api/community/threads/{thread_id}")
def get_thread(thread_id: int):
    thread = fetch_one("SELECT * FROM community_threads WHERE id=?", [thread_id])
    if not thread:
        raise HTTPException(404, "Thread not found")
    execute("UPDATE community_threads SET view_count = view_count + 1 WHERE id=?", [thread_id])
    thread["view_count"] += 1
    replies = fetch(
        "SELECT * FROM community_replies WHERE thread_id=? ORDER BY created_at ASC",
        [thread_id],
    )
    thread["replies"] = replies
    return thread


@app.post("/api/community/threads/{thread_id}/reply")
def reply_to_thread(thread_id: int, data: ThreadReplyCreate):
    thread = fetch_one("SELECT id FROM community_threads WHERE id=?", [thread_id])
    if not thread:
        raise HTTPException(404, "Thread not found")
    rid = execute(
        "INSERT INTO community_replies (thread_id, content, author_name, is_anonymous) VALUES (?, ?, ?, ?)",
        [thread_id, data.content, data.author_name.strip() or "匿名", int(data.is_anonymous)],
    )
    execute("UPDATE community_threads SET reply_count = reply_count + 1 WHERE id=?", [thread_id])
    try:
        notify_owner("reply", {
            "content": data.content,
            "author_name": data.author_name.strip() or "匿名",
        }, url=f"https://lewislunora.onrender.com/community/?thread={thread_id}")
    except Exception:
        pass
    return {"status": "ok", "id": rid}


@app.post("/api/community/threads/{thread_id}/upvote")
def upvote_thread(thread_id: int):
    thread = fetch_one("SELECT id FROM community_threads WHERE id=?", [thread_id])
    if not thread:
        raise HTTPException(404, "Thread not found")
    execute("UPDATE community_threads SET view_count = view_count + 1 WHERE id=?", [thread_id])
    return {"status": "ok"}


def _current_user(request: Request, token: str = ""):
    """從 cookie 或 query token 取得目前登入使用者。未登入回傳 None。"""
    if not token:
        token = request.cookies.get("token", "")
    if not token:
        return None
    return fetch_one("SELECT id, username, email, name, avatar, bio FROM users WHERE token=? AND is_active=1", (token,))


def _user_dict(u):
    if not u:
        return None
    email_prefix = u["email"].split("@")[0] if u["email"] else ""
    name = u["name"] or email_prefix or u["username"] or "使用者"
    return {"id": u["id"], "name": name,
            "username": u["username"], "email": u["email"] or "", "avatar": u["avatar"] or "", "bio": u["bio"] or ""}


def _require_user(request: Request):
    u = _current_user(request)
    if not u:
        raise HTTPException(401, "請先登入")
    return u


def _get_or_create_conversation(me_id, other_id):
    row = fetch_one(
        "SELECT id FROM conversations WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)",
        (me_id, other_id, other_id, me_id),
    )
    if row:
        return row["id"]
    return execute("INSERT INTO conversations (user_a, user_b) VALUES (?, ?)",
                   (min(me_id, other_id), max(me_id, other_id)))


# ---------- 私訊聊天 ----------
@app.get("/api/chat/conversations")
def chat_conversations(request: Request):
    me = _require_user(request)
    rows = fetch(
        "SELECT c.id, c.last_message_at, "
        "u.id AS other_id, COALESCE(NULLIF(u.name,''), u.username) AS other_name, u.username AS other_username, u.avatar AS other_avatar, "
        "(SELECT m.body FROM messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_body, "
        "(SELECT m.created_at FROM messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_at, "
        "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id AND m.sender_id<>? AND m.read_at IS NULL) AS unread "
        "FROM conversations c JOIN users u ON u.id = CASE WHEN c.user_a=? THEN c.user_b ELSE c.user_a END "
        "WHERE c.user_a=? OR c.user_b=? ORDER BY c.last_message_at DESC",
        (me["id"], me["id"], me["id"], me["id"]),
    )
    return {"items": rows}


@app.get("/api/chat/conversations/{cid}/messages")
def chat_messages(cid: int, request: Request, before_id: int = 0, limit: int = 50):
    me = _require_user(request)
    conv = fetch_one("SELECT * FROM conversations WHERE id=?", (cid,))
    if not conv or (conv["user_a"] != me["id"] and conv["user_b"] != me["id"]):
        raise HTTPException(404, "對話不存在")
    if before_id:
        rows = fetch(
            "SELECT m.*, COALESCE(NULLIF(u.name,''), u.username) AS sender_name, u.avatar AS sender_avatar FROM messages m "
            "JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? AND m.id<? "
            "ORDER BY m.id DESC LIMIT ?",
            (cid, before_id, limit),
        )
        rows.reverse()
    else:
        rows = fetch(
            "SELECT m.*, COALESCE(NULLIF(u.name,''), u.username) AS sender_name, u.avatar AS sender_avatar FROM messages m "
            "JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? "
            "ORDER BY m.id DESC LIMIT ?",
            (cid, limit),
        )
        rows.reverse()
    execute("UPDATE messages SET read_at=datetime('now') WHERE conversation_id=? AND sender_id<>? AND read_at IS NULL",
            (cid, me["id"]))
    return {"items": rows}


@app.post("/api/chat/send")
def chat_send(data: MessageSend, request: Request):
    me = _require_user(request)
    if not data.body.strip():
        raise HTTPException(400, "訊息不能為空")
    body = data.body.strip()[:2000]
    if data.conversation_id:
        conv = fetch_one("SELECT * FROM conversations WHERE id=?", (data.conversation_id,))
        if not conv or (conv["user_a"] != me["id"] and conv["user_b"] != me["id"]):
            raise HTTPException(404, "對話不存在")
        cid = conv["id"]
    else:
        if not data.to_user_id:
            raise HTTPException(400, "缺少接收者")
        if data.to_user_id == me["id"]:
            raise HTTPException(400, "不能傳訊息給自己")
        other = fetch_one("SELECT id FROM users WHERE id=? AND is_active=1", (data.to_user_id,))
        if not other:
            raise HTTPException(404, "使用者不存在")
        cid = _get_or_create_conversation(me["id"], data.to_user_id)
    mid = execute(
        "INSERT INTO messages (conversation_id, sender_id, body) VALUES (?, ?, ?)",
        (cid, me["id"], body),
    )
    execute("UPDATE conversations SET last_message_at=datetime('now') WHERE id=?", (cid,))
    row = fetch_one(
        "SELECT m.*, u.name AS sender_name, u.avatar AS sender_avatar FROM messages m "
        "JOIN users u ON u.id=m.sender_id WHERE m.id=?", (mid,))
    return {"status": "ok", "message": row}


@app.post("/api/chat/open")
def chat_open(data: ChatOpen, request: Request):
    me = _require_user(request)
    if data.user_id == me["id"]:
        raise HTTPException(400, "不能與自己對話")
    other = fetch_one("SELECT id FROM users WHERE id=? AND is_active=1", (data.user_id,))
    if not other:
        raise HTTPException(404, "使用者不存在")
    cid = _get_or_create_conversation(me["id"], data.user_id)
    return {"conversation_id": cid}


@app.get("/api/chat/unread")
def chat_unread(request: Request):
    me = _current_user(request)
    if not me:
        return {"unread": 0}
    row = fetch_one(
        "SELECT COUNT(*) AS c FROM messages m JOIN conversations c ON c.id=m.conversation_id "
        "WHERE (c.user_a=? OR c.user_b=?) AND m.sender_id<>? AND m.read_at IS NULL",
        (me["id"], me["id"], me["id"]),
    )
    return {"unread": row["c"] if row else 0}


@app.post("/api/chat/suggest")
def chat_suggest(data: MessageSend, request: Request):
    me = _require_user(request)
    context = ""
    if data.conversation_id:
        conv = fetch_one("SELECT * FROM conversations WHERE id=?", (data.conversation_id,))
        if conv and (conv["user_a"] == me["id"] or conv["user_b"] == me["id"]):
            last = fetch(
                "SELECT m.body, u.name AS n FROM messages m JOIN users u ON u.id=m.sender_id "
                "WHERE m.conversation_id=? ORDER BY m.id DESC LIMIT 5", (data.conversation_id,))
            context = " | ".join(f"{r['n']}: {r['body'][:120]}" for r in reversed(last))
    if not ai_generator.is_available():
        return {"suggestion": "", "fallback": True}
    prompt = ("你是親切友善的交友聊天助手。根據以下對話脈絡，幫我寫一句自然的回覆建議（繁體中文，20-60 字，口語、真誠、不要罐頭話）：\n\n"
              f"對話：{context}\n\n回覆建議：")
    try:
        suggestion = ai_generator.generate("custom", {"prompt": prompt}).strip()
        return {"suggestion": suggestion, "fallback": False}
    except Exception:
        return {"suggestion": "", "fallback": True}


# ---------- 交友 / 追蹤 ----------
@app.get("/api/users")
def list_users(request: Request, q: str = "", page: int = 1, per_page: int = 30):
    me = _current_user(request)
    cond = "is_active=1"
    params = []
    if me:
        cond += " AND id<>?"
        params.append(me["id"])
    if q:
        cond += " AND (name LIKE ? OR username LIKE ? OR email LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    offset = (page - 1) * per_page
    rows = fetch(f"SELECT id, username, email, name, avatar, bio FROM users WHERE {cond} ORDER BY id DESC LIMIT ? OFFSET ?",
                 params + [per_page, offset])
    items = []
    for r in rows:
        item = _user_dict(r)
        if me:
            item["is_following"] = bool(fetch_one("SELECT id FROM follows WHERE follower_id=? AND following_id=?",
                                                  (me["id"], r["id"])))
        else:
            item["is_following"] = False
        items.append(item)
    total = fetch(f"SELECT COUNT(*) AS c FROM users WHERE {cond}", params)[0]["c"]
    return {"items": items, "total": total, "page": page}


@app.get("/api/users/{uid}")
def get_user_profile(uid: int, request: Request):
    me = _current_user(request)
    row = fetch_one("SELECT id, username, email, name, avatar, bio FROM users WHERE id=? AND is_active=1", (uid,))
    if not row:
        raise HTTPException(404, "使用者不存在")
    profile = _user_dict(row)
    profile["followers"] = fetch_one("SELECT COUNT(*) AS c FROM follows WHERE following_id=?", (uid,))["c"]
    profile["following"] = fetch_one("SELECT COUNT(*) AS c FROM follows WHERE follower_id=?", (uid,))["c"]
    profile["post_count"] = fetch_one("SELECT COUNT(*) AS c FROM feed_posts WHERE user_id=?", (uid,))["c"]
    profile["is_following"] = bool(me and fetch_one(
        "SELECT id FROM follows WHERE follower_id=? AND following_id=?", (me["id"], uid)))
    profile["is_me"] = bool(me and me["id"] == uid)
    return profile


@app.post("/api/users/{uid}/follow")
def follow_user(uid: int, request: Request):
    me = _require_user(request)
    if uid == me["id"]:
        raise HTTPException(400, "不能追蹤自己")
    other = fetch_one("SELECT id FROM users WHERE id=? AND is_active=1", (uid,))
    if not other:
        raise HTTPException(404, "使用者不存在")
    execute("INSERT OR IGNORE INTO follows (follower_id, following_id) VALUES (?, ?)", (me["id"], uid))
    return {"status": "following"}


@app.delete("/api/users/{uid}/follow")
def unfollow_user(uid: int, request: Request):
    me = _require_user(request)
    execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (me["id"], uid))
    return {"status": "unfollowed"}


@app.get("/api/me/following")
def my_following(request: Request):
    me = _require_user(request)
    rows = fetch(
        "SELECT u.id, u.name, u.username, u.avatar FROM follows f JOIN users u ON u.id=f.following_id "
        "WHERE f.follower_id=? ORDER BY f.created_at DESC", (me["id"],))
    return {"items": rows}


@app.put("/api/me/profile")
def update_my_profile(data: ProfileUpdate, request: Request):
    me = _require_user(request)
    name = (data.name or "").strip()[:40]
    bio = (data.bio or "").strip()[:200]
    if name:
        execute("UPDATE users SET name=?, bio=? WHERE id=?", (name, bio, me["id"]))
    else:
        execute("UPDATE users SET bio=? WHERE id=?", (bio, me["id"]))
    return {"status": "ok"}


# ---------- 動態牆 (Threads 風) ----------
def _feed_item(p, me):
    author_id = p["user_id"]
    author = None
    if author_id:
        u = fetch_one("SELECT id, name, username, email, avatar, bio FROM users WHERE id=?", (author_id,))
        if u:
            author = _user_dict(u)
    if not author:
        author = {"id": None, "name": p["author"], "username": "", "avatar": "", "bio": ""}
    likes = fetch("SELECT COUNT(*) AS c FROM reactions WHERE page_path=? AND emoji='❤'",
                  (f"feed:{p['id']}",))
    like_count = likes[0]["c"] if likes else 0
    liked = bool(me and fetch_one(
        "SELECT id FROM reactions WHERE page_path=? AND emoji='❤' AND user_id=?", (f"feed:{p['id']}", me["id"])))
    comment_count = fetch_one("SELECT COUNT(*) AS c FROM comments WHERE page_path=?", (f"feed:{p['id']}",))["c"]
    return {
        "id": p["id"], "content": p["content"], "post_type": p["post_type"],
        "author": author, "created_at": p["created_at"],
        "like_count": like_count, "liked": liked, "comment_count": comment_count,
    }


@app.post("/api/feed")
def create_feed_post(data: FeedPostCreate, request: Request):
    me = _current_user(request)
    if not data.content.strip():
        raise HTTPException(400, "內容不能為空")
    content = data.content.strip()[:2000]
    user_id = me["id"] if me else None
    author = (me["name"] or me["username"] or data.author) if me else data.author
    pid = execute(
        "INSERT INTO feed_posts (user_id, content, post_type, author) VALUES (?, ?, ?, ?)",
        [user_id, content, data.post_type, author],
    )
    row = fetch_one("SELECT * FROM feed_posts WHERE id=?", (pid,))
    return {"status": "ok", "post": _feed_item(row, me)}


@app.get("/api/feed")
def list_feed_posts(request: Request, page: int = 1, per_page: int = 20):
    me = _current_user(request)
    offset = (page - 1) * per_page
    rows = fetch("SELECT * FROM feed_posts ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", [per_page, offset])
    total = fetch("SELECT COUNT(*) AS c FROM feed_posts")[0]["c"]
    return {"items": [_feed_item(p, me) for p in rows], "total": total, "page": page}


@app.post("/api/feed/{pid}/like")
def toggle_feed_like(pid: int, request: Request):
    me = _require_user(request)
    post = fetch_one("SELECT id FROM feed_posts WHERE id=?", (pid,))
    if not post:
        raise HTTPException(404, "貼文不存在")
    path = f"feed:{pid}"
    existing = fetch_one("SELECT id FROM reactions WHERE page_path=? AND emoji='❤' AND user_id=?", (path, me["id"]))
    if existing:
        execute("DELETE FROM reactions WHERE id=?", (existing["id"],))
        return {"status": "removed", "liked": False}
    execute("INSERT INTO reactions (page_path, emoji, user_id) VALUES (?, '❤', ?)", (path, me["id"]))
    return {"status": "added", "liked": True}


@app.post("/api/feed/{pid}/comment")
def comment_feed_post(pid: int, data: FeedCommentCreate, request: Request):
    me = _require_user(request)
    post = fetch_one("SELECT id FROM feed_posts WHERE id=?", (pid,))
    if not post:
        raise HTTPException(404, "貼文不存在")
    content = (data.content or "").strip()[:500]
    if not content:
        raise HTTPException(400, "留言不能為空")
    cid = execute(
        "INSERT INTO comments (page_path, author_name, content, user_id) VALUES (?, ?, ?, ?)",
        (f"feed:{pid}", me["name"] or me["username"] or "匿名", content, me["id"]),
    )
    return {"status": "ok", "comment_id": cid}


@app.get("/api/feed/{pid}/comments")
def feed_comments(pid: int, request: Request):
    rows = fetch(
        "SELECT c.*, u.avatar AS user_avatar FROM comments c "
        "LEFT JOIN users u ON u.id=c.user_id WHERE c.page_path=? ORDER BY c.id ASC",
        (f"feed:{pid}",),
    )
    return {"items": rows}


@app.post("/api/ai/summarize")
async def ai_summarize(request: Request):
    body = await request.json()
    text = body.get("text", "")
    lang = body.get("language", "zh-TW")
    if not text.strip():
        return {"summary": "", "fallback": True}
    if not ai_generator.is_available():
        lang_label = {"zh-TW": "繁體中文", "zh-CN": "簡體中文", "en": "英文"}.get(lang, lang)
        return {"summary": f"（AI 摘要功能需要設定 GROQ_API_KEY）", "fallback": True}
    prompt = f"請用{lang}用 3 句話簡短總結以下內容：\n\n{text[:3000]}"
    try:
        summary = ai_generator.generate("custom", {"prompt": prompt})
        return {"summary": summary.strip(), "fallback": False}
    except Exception as e:
        return {"summary": "", "fallback": True, "error": str(e)}


@app.post("/api/ai/recommend")
async def ai_recommend(request: Request):
    body = await request.json()
    path = body.get("path", "")
    lang = body.get("language", "zh-TW")
    if not path:
        return {"items": []}
    exclude = [path]
    rows = fetch(
        "SELECT page_path, COUNT(*) as score FROM article_views WHERE page_path != ? GROUP BY page_path ORDER BY score DESC LIMIT 5",
        [path],
    )
    items = []
    for r in rows:
        items.append({"path": r["page_path"], "reason": f"其他讀者也閱覽了此內容"})
    return {"items": items}


@app.post("/api/analytics/article-view")
async def track_article_view(request: Request):
    body = await request.json()
    path = body.get("path", "/")
    execute("INSERT INTO article_views (page_path) VALUES (?)", [path])
    return {"ok": True}


# ── AI Code Review ──────────────────────────────────────────────────────
class AIReviewRequest(BaseModel):
    diff: str
    description: str = ""
    project: str = ""
    mr_iid: str = ""
    language: str = ""

@app.post("/api/ai-review")
async def ai_code_review(req: AIReviewRequest):
    from ..config import GROQ_API_KEY, GROQ_MODEL
    if not GROQ_API_KEY:
        return {"review": "⚠️ AI Code Review 未啟用（需要設定 GROQ_API_KEY）", "fallback": True}
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""你是一個專業的 Senior Code Reviewer。請針對以下 Merge Request 進行程式碼審查。

MR 描述：
{req.description or "(無描述)"}

Diff 變更：
{req.diff[:8000]}

請輸出以下結構（繁體中文）：

## 🔍 審查結果

### ✅ 優點
- （列出 1-2 個優點）

### ⚠️ 需要改善
- （列出問題，含檔案與行號）
- 每個問題附上風險等級：🟢 建議 / 🟡 注意 / 🔴 嚴重

### 💡 建議改善範例
- （如果發現問題，給出 diff 格式的建議寫法）

### 📊 總結
- 總變更檔案數、建議數量、主要風險領域

如果沒有重大問題，回覆「✅ 程式碼品質良好，無重大問題。」"""

        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.3,
        )
        review = resp.choices[0].message.content or "（AI 無法生成審查）"
        return {"review": review, "fallback": False}

    except Exception as e:
        return {"review": f"⚠️ AI Review 錯誤：{str(e)}", "fallback": True}


# ── Auto Promote ────────────────────────────────────────────────────────
PROMO_TOPICS = [
    "一人公司的 AI 自動化——每天省 4 小時的 3 個系統",
    "Code Review 太慢？用 AI 把 30 分鐘變成 10 分鐘",
    "為什麼你的 AI 客服沒有效？90% 的人少了這一步",
    "一人公司不需要工程團隊——你只需要這套 AI 系統",
    "工程師如何用 Threads 接到第一個付費客戶？",
    "AI 自動化導入失敗的 3 個常見原因",
    "從接案到 SaaS：一人工程師的獲利路徑",
    "資料庫報表整理太花時間？把這個交給 AI",
    "一人公司最該外包的不是會計，是客服",
    "寫了 10 年 Code，我學到最重要的事：別自己扛全部",
]

@app.get("/api/auto-promote")
def auto_promote():
    from ..config import GROQ_API_KEY, GROQ_MODEL
    import random
    topic = random.choice(PROMO_TOPICS)
    if not GROQ_API_KEY:
        return {"ok": False, "error": "GROQ_API_KEY not set", "body": "", "topic": topic}

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"""你是一個擅長在 Threads 上推廣 AI 自動化服務的文案高手。
請根據主題寫一篇 Threads 貼文（繁體中文，200 字內）。

主題：{topic}

風格：專業但有溫度，像在分享經驗，而不是廣告。
結構：開頭一句話抓住注意 → 2-3 句說明痛點或方法 → 結尾引導到免費諮詢。
不用 hashtag，不要 emoji 過多。
結尾固定加這行：
「👇 預約免費 30 分鐘 AI 盤點 👉 lewislunora.onrender.com/」"""

        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        body = resp.choices[0].message.content or ""

        execute(
            "INSERT INTO promo_queue (platform, body, status) VALUES ('threads', ?, 'pending')",
            [body]
        )
        return {"ok": True, "body": body, "topic": topic}

    except Exception as e:
        return {"ok": False, "error": str(e), "body": "", "topic": topic}


@app.get("/api/auto-promote/queue")
def promo_queue(page: int = 1, per_page: int = 20):
    rows = fetch(
        "SELECT * FROM promo_queue ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [per_page, (page - 1) * per_page]
    )
    total = fetch("SELECT COUNT(*) as c FROM promo_queue")[0]["c"]
    return {"items": rows, "total": total, "page": page}


@app.post("/api/auto-promote/post/{promo_id}")
def post_promo(promo_id: int):
    """Post a generated promo to Threads (if credentials configured)."""
    from ..config import GROQ_API_KEY
    row = fetch_one("SELECT * FROM promo_queue WHERE id=?", [promo_id])
    if not row:
        raise HTTPException(404, "Promo not found")
    if row["status"] == "done":
        return {"ok": False, "error": "Already posted"}

    from ..platforms.browser_automation import ThreadsConnector
    from ..config import DATA_DIR
    config_path = DATA_DIR / "threads_config.json"
    if not config_path.exists():
        return {"ok": False, "error": "Threads credentials not configured. Set up at /admin/promo"}

    config = json.loads(config_path.read_text())
    connector = ThreadsConnector(config)
    try:
        result = connector.post(row["body"])
        execute(
            "UPDATE promo_queue SET status='done', posted_at=datetime('now') WHERE id=?",
            [promo_id]
        )
        return {"ok": True, "result": result}
    except Exception as e:
        execute(
            "UPDATE promo_queue SET status='failed', error=? WHERE id=?",
            [str(e), promo_id]
        )
        return {"ok": False, "error": str(e)}


# ── Scheduler auto-promote task ─────────────────────────────────────────
def _register_promo_task():
    if not scheduler:
        return
    import random
    minute = random.randint(0, 59)

    def daily_promo():
        from ..config import GROQ_API_KEY
        if not GROQ_API_KEY:
            return
        try:
            today = fetch(
                "SELECT COUNT(*) as c FROM promo_queue WHERE date(created_at) = date('now')"
            )[0]["c"]
            if today > 0:
                return
            resp = auto_promote()
            from ..config import DATA_DIR
            config_path = DATA_DIR / "threads_config.json"
            if config_path.exists():
                row = fetch_one("SELECT id FROM promo_queue ORDER BY id DESC LIMIT 1")
                if row:
                    post_promo(row["id"])
        except Exception:
            pass

    original_loop = scheduler._loop

    def patched_loop():
        while scheduler.running:
            try:
                scheduler._process_pending()
                scheduler._ping_count += 1
                if scheduler._ping_count % 1440 == 0:
                    scheduler._daily_backup()
                if scheduler._ping_count % 60 == 0:
                    scheduler._auto_learn_kb()
                if scheduler._ping_count % 1440 == minute:
                    daily_promo()
            except Exception:
                pass
            time.sleep(60)

    scheduler._loop = patched_loop


# ── Web Roamer ──────────────────────────────────────────────────────────
@app.get("/api/roam/search")
def roam_search(query: str = ""):
    from ..services.web_roamer import WebRoamer
    roamer = WebRoamer(data_dir=DATA_DIR)
    results = roamer.search(query or None, max_results=10)
    return {"query": query, "results": results, "count": len(results)}


@app.post("/api/roam/visit")
async def roam_visit(request: Request):
    body = await request.json()
    url = body.get("url", "")
    if not url:
        raise HTTPException(400, "url required")
    from ..services.web_roamer import WebRoamer
    roamer = WebRoamer(data_dir=DATA_DIR)
    info = roamer.visit(url)
    return info


@app.post("/api/roam/generate")
async def roam_generate(request: Request):
    body = await request.json()
    from ..services.web_roamer import WebRoamer
    roamer = WebRoamer(data_dir=DATA_DIR)
    from ..config import GROQ_API_KEY, GROQ_MODEL
    reply = roamer.generate_reply(
        body.get("title", ""),
        body.get("content", ""),
        body.get("url", ""),
        groq_client=GROQ_API_KEY,
        groq_model=GROQ_MODEL,
    )
    return {"reply": reply or "（無法生成）"}


@app.post("/api/roam/post")
async def roam_post(request: Request):
    body = await request.json()
    url = body.get("url", "")
    reply = body.get("reply", "")
    from ..services.web_roamer import WebRoamer
    roamer = WebRoamer(data_dir=DATA_DIR)
    result = await roamer.post_reply_playwright(url, reply)
    return result


@app.post("/api/roam/run")
def roam_run():
    """Full roam cycle: search → visit → generate → post."""
    from ..services.web_roamer import WebRoamer
    from ..config import GROQ_API_KEY, GROQ_MODEL
    roamer = WebRoamer(data_dir=DATA_DIR)
    result = roamer.roam(
        max_sites=5,
        groq_client=GROQ_API_KEY,
        groq_model=GROQ_MODEL,
    )
    posted = sum(1 for r in result["results"] if r.get("post_result", {}).get("ok"))
    result["posted_count"] = posted
    return result


# ==============================
# AI 理想型配對 API
# ==============================

class BaziRequest(BaseModel):
    birth_datetime: str  # ISO format: "1990-05-15T14:30:00"
    gender: str  # "male" or "female"
    birthplace: Optional[str] = None


class MatchingRequest(BaseModel):
    birth_datetime: str
    gender: str
    birthplace: Optional[str] = None
    preferences: list[str] = []  # 擇偶條件
    personality: list[str] = []  # 性格特質


@app.post("/api/bazi")
def api_bazi(req: BaziRequest):
    """八字排盤 API"""
    from ..services.bazi_engine import calculate_bazi
    try:
        result = calculate_bazi(
            birth_datetime=req.birth_datetime,
            gender=req.gender,
            birthplace=req.birthplace,
        )
        return result.to_dict()
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/matching")
async def api_matching(req: MatchingRequest):
    """AI 理想型配對分析"""
    from ..services.bazi_engine import calculate_bazi
    from ..config import GROQ_API_KEY, GROQ_MODEL
    import groq

    # 1. 計算八字
    try:
        bazi = calculate_bazi(
            birth_datetime=req.birth_datetime,
            gender=req.gender,
            birthplace=req.birthplace,
        )
    except Exception as e:
        raise HTTPException(400, f"八字計算錯誤: {str(e)}")

    bazi_dict = bazi.to_dict()

    # 2. 用 AI 分析
    if not GROQ_API_KEY:
        raise HTTPException(500, "GROQ_API_KEY 未設定")

    preferences_text = "、".join(req.preferences) if req.preferences else "未指定"
    personality_text = "、".join(req.personality) if req.personality else "未指定"

    prompt = f"""你是專業的命理分析師與情感顧問。根據以下八字資料，進行深度分析。

## 八字資料
- 四柱：{bazi_dict['pillars']['year']} {bazi_dict['pillars']['month']} {bazi_dict['pillars']['day']} {bazi_dict['pillars']['hour']}
- 日主：{bazi_dict['day_master']['name']}（{bazi_dict['day_master']['element']}，{bazi_dict['day_master']['polarity']}）
- 五行分數：{json.dumps(bazi_dict['five_elements']['scores'], ensure_ascii=False)}
- 十神：{json.dumps([g['ten_god'] for g in bazi_dict['ten_gods']], ensure_ascii=False)}
- 日主強弱：{'偏強' if bazi_dict['strength_analysis']['is_strong'] else '偏弱'}
- 地支關係：{json.dumps([r['description'] for r in bazi_dict['relationships']], ensure_ascii=False)}

## 用戶擇偶條件
{preferences_text}

## 用戶性格特質
{personality_text}

## 請分析以下內容（使用 JSON 格式回傳）：

{{
  "personality_analysis": "根據八字分析這個人的性格特質（5-8 點，每點一句話，用換行分隔，不要用 JSON 陣列）",
  "ideal_partner": "根據八字分析的理想型畫像（具體描述外表氣質、性格、價值觀、生活方式，用換行分隔段落）",
  "matching_dimensions": {{
    "values": {{ "score": 0-100, "analysis": "價值觀契合度分析" }},
    "lifestyle": {{ "score": 0-100, "analysis": "生活風格匹配分析" }},
    "communication": {{ "score": 0-100, "analysis": "溝通方式相容分析" }},
    "emotion": {{ "score": 0-100, "analysis": "情感需求互補分析" }}
  }},
  "conflicts": ["潛在衝突點1", "潛在衝突點2"],
  "meeting_suggestion": "建議的認識管道與方式（用換行分隔段落）",
  "overall_score": 0-100,
  "overall_summary": "整體分析總結（2-3 句話）"
}}

注意：
1. 分析要具體，不要空泛
2. 結合八字五行與十神的特性
3. 如果用戶有提供擇偶條件和性格特質，要融入分析中
4. 保持專業但溫暖的語氣
5. 只回傳 JSON，不要有其他文字"""

    try:
        client = groq.Client(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7,
        )
        ai_text = response.choices[0].message.content.strip()

        # 嘗試解析 JSON
        # 有時 AI 會在 JSON 前後加文字，嘗試提取
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_text:
            ai_text = ai_text.split("```")[1].split("```")[0].strip()

        ai_result = json.loads(ai_text)

        # 修正：AI 有時會把完整 JSON 當字串放在某個欄位裡
        # 嘗試找到包含完整結構的欄位並展開
        for key in list(ai_result.keys()):
            val = ai_result[key]
            if isinstance(val, str) and val.strip().startswith("{"):
                try:
                    nested = json.loads(val)
                    if isinstance(nested, dict) and len(nested) > 2:
                        ai_result = nested
                        break
                except (json.JSONDecodeError, ValueError):
                    pass
    except json.JSONDecodeError as e:
        # 如果 JSON 解析失敗，回傳原始文字
        ai_result = {
            "personality_analysis": ai_text,
            "ideal_partner": "",
            "matching_dimensions": {},
            "conflicts": [],
            "meeting_suggestion": "",
            "overall_score": 0,
            "overall_summary": f"AI 分析完成，但格式解析失敗。原始回應：{ai_text[:500]}",
        }
    except Exception as e:
        raise HTTPException(500, f"AI 分析錯誤: {str(e)}")

    # 3. 儲存用戶資料
    try:
        execute(
            "INSERT INTO matching_records (birth_datetime, gender, bazi_data, ai_result, preferences, personality) VALUES (?, ?, ?, ?, ?, ?)",
            [
                req.birth_datetime,
                req.gender,
                json.dumps(bazi_dict, ensure_ascii=False),
                json.dumps(ai_result, ensure_ascii=False),
                json.dumps(req.preferences, ensure_ascii=False),
                json.dumps(req.personality, ensure_ascii=False),
            ],
        )
    except Exception:
        pass  # 儲存失敗不影響回應

    # 4. 回傳結果
    return {
        "bazi": bazi_dict,
        "analysis": ai_result,
    }


_register_promo_task()


@app.middleware("http")
async def security_and_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path

    # Cache control
    if path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    else:
        response.headers.setdefault("Cache-Control", "no-cache, max-age=0")

    # Security headers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

    # CSP — allow only own domain + inline styles/scripts (existing site uses them)
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://accounts.google.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://lewislunora.onrender.com https://accounts.google.com; "
        "frame-ancestors 'none'"
    )
    response.headers["Content-Security-Policy"] = csp

    # Remove server info
    if "server" in response.headers:
        del response.headers["server"]

    return response


app.mount("/", StaticFiles(directory=str(DOCS_DIR), html=True), name="site")