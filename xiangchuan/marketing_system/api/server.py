import os
import json
import hashlib
import secrets
import threading
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from ..database import init_db, execute, fetch, fetch_one
from student_platform.database import StudentDatabase
from student_platform.routes import router as student_router
from ..scheduler import ContentScheduler
from ..ai.generator import AIContentGenerator
from ..platforms.telegram_connector import TelegramConnector
from ..platforms.line_connector import LineConnector
from ..platforms.facebook_connector import FacebookConnector
from ..platforms.twitter_connector import TwitterConnector
from ..platforms.browser_automation import ThreadsConnector, DcardConnector, XiaohongshuConnector
from ..config import PLATFORMS, DATA_DIR, DOCS_DIR, TELEGRAM_BOT_TOKEN, LINE_NOTIFY_TOKEN
from ..services.email_service import send_contact_email, is_configured as smtp_configured
from ..services.notification_service import notify_owner, send_telegram_notification
from ..services.openclaw_agent import _handle_command as openclaw_handle, _is_authorized as openclaw_authorized
from ..services.knowledge_base import get_kb_reply, save_unanswered, get_pending, auto_learn
from ..services.analytics import track_async, summary as analytics_summary

app = FastAPI(title="翔川 Neo｜曜科技 行銷自動化系統")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    StudentDatabase.init_db()
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
    return {
        "ai_available": ai_generator.is_available(),
        "smtp_configured": smtp_configured(),
        "telegram_bot_token_set": bool(TELEGRAM_BOT_TOKEN),
        "line_notify_configured": bool(LINE_NOTIFY_TOKEN),
        "database_type": "sqlite",
        "scheduler": scheduler.get_status_summary(),
        "platforms": {k: v["enabled"] for k, v in PLATFORMS.items()},
    }


@app.get("/api/notify/test")
def notify_test():
    """Synchronously test all notification channels and report results."""
    from ..services import notification_service
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
    return {"results": results, "line_notify_configured": bool(LINE_NOTIFY_TOKEN), "smtp_configured": smtp_configured()}


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
        import logging
        logging.getLogger(__name__).error(f"Contact notification failed: {e}")

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


@app.get("/api/debug")
async def debug_info():
    import os
    return {
        "cwd": os.getcwd(),
        "docs_dir": str(DOCS_DIR),
        "docs_exists": DOCS_DIR.exists(),
        "99u_exists": (DOCS_DIR / "99u" / "index.html").exists(),
        "ai_brand_exists": (DOCS_DIR / "ai-brand" / "index.html").exists(),
        "files": sorted([str(f) for f in DOCS_DIR.rglob("*.html")])[-20:] if DOCS_DIR.exists() else [],
    }


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


@app.post("/api/feed")
def create_feed_post(data: FeedPostCreate):
    pid = execute(
        "INSERT INTO feed_posts (content, post_type, author) VALUES (?, ?, ?)",
        [data.content, data.post_type, data.author],
    )
    return {"status": "ok", "id": pid}


@app.get("/api/feed")
def list_feed_posts(page: int = 1, per_page: int = 10):
    offset = (page - 1) * per_page
    items = fetch(
        "SELECT * FROM feed_posts ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [per_page, offset],
    )
    total = fetch("SELECT COUNT(*) as c FROM feed_posts")[0]["c"]
    return {"items": items, "total": total, "page": page}


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


_register_promo_task()


@app.middleware("http")
async def cache_control_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.endswith(".html") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    else:
        response.headers.setdefault("Cache-Control", "no-cache, max-age=0")
    return response


app.mount("/", StaticFiles(directory=str(DOCS_DIR), html=True), name="site")