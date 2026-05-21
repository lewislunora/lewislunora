import os
import json
import hashlib
import secrets
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from ..database import init_db, execute, fetch, fetch_one
from ..scheduler import ContentScheduler
from ..ai.generator import AIContentGenerator
from ..platforms.telegram_connector import TelegramConnector
from ..platforms.line_connector import LineConnector
from ..platforms.facebook_connector import FacebookConnector
from ..platforms.twitter_connector import TwitterConnector
from ..platforms.browser_automation import ThreadsConnector, DcardConnector, XiaohongshuConnector
from ..config import PLATFORMS, DATA_DIR, DOCS_DIR, TELEGRAM_BOT_TOKEN
from ..services.email_service import send_contact_email, is_configured as smtp_configured
from ..services.notification_service import send_telegram_notification
from ..services.knowledge_base import get_kb_reply, save_unanswered, get_pending, auto_learn

app = FastAPI(title="翔川 Neo｜曜科技 行銷自動化系統")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "threads": ThreadsConnector,
        "dcard": DcardConnector,
        "xiaohongshu": XiaohongshuConnector,
    }
    cls = mapping.get(platform)
    if not cls:
        raise HTTPException(400, f"Unsupported platform: {platform}")
    return cls(creds)


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
    scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.stop()


@app.get("/api/status")
def status():
    return {
        "ai_available": ai_generator.is_available(),
        "smtp_configured": smtp_configured(),
        "telegram_bot_token_set": bool(TELEGRAM_BOT_TOKEN),
        "database_type": "sqlite",
        "scheduler": scheduler.get_status_summary(),
        "platforms": {k: v["enabled"] for k, v in PLATFORMS.items()},
    }


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
    if smtp_configured():
        send_contact_email(data)
    else:
        send_telegram_notification(data)
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
    return {"id": cid, "status": "created"}


@app.get("/api/accounts")
def list_accounts():
    return {"items": fetch("SELECT * FROM accounts ORDER BY created_at DESC")}


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    execute("DELETE FROM accounts WHERE id=?", [account_id])
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
        if text in ("/start", "/help"):
            reply = (
                "🤖 歡迎使用 @ailunora_bot！\n\n"
                "你可以問我：\n"
                "• 方案與價格\n"
                "• 功能介紹\n"
                "• 平台支援\n"
                "• 如何開始\n"
                "• 其他行銷相關問題\n\n"
                "或在群組中 @ailunora_bot 你的問題"
            )
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
def auth_me(token: str = ""):
    if not token:
        raise HTTPException(401, "未登入")
    row = fetch_one("SELECT email FROM users WHERE token=?", (token,))
    if not row:
        raise HTTPException(401, "Token 無效")
    return {"email": row["email"], "name": row["email"].split("@")[0] if row["email"] else ""}


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


app.mount("/", StaticFiles(directory=str(DOCS_DIR), html=True), name="site")
