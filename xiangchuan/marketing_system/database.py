import os
import json
import sqlite3
import logging
import threading
from datetime import datetime
from pathlib import Path
from .config import DATABASE_PATH, DATABASE_BACKUP_PATH, DATA_DIR

logger = logging.getLogger(__name__)

_commit_lock = threading.Lock()

DB_TABLES = [
    "accounts", "contents", "schedules", "analytics",
    "ai_templates", "kb_entries", "kb_pending", "contacts", "users",
]


def _conn():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _backup_exists():
    return DATABASE_BACKUP_PATH.exists() and DATABASE_BACKUP_PATH.stat().st_size > 10


def _restore_from_backup():
    logger.info("Restoring database from backup JSON...")
    data = json.loads(DATABASE_BACKUP_PATH.read_text("utf-8"))
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.execute("PRAGMA foreign_keys=OFF")
    for table in DB_TABLES:
        rows = data.get(table, [])
        if not rows:
            continue
        conn.execute(f"DELETE FROM {table}")
        if not rows:
            continue
        cols = list(rows[0].keys())
        placeholders = ",".join("?" for _ in cols)
        colnames = ",".join(f'"{c}"' for c in cols)
        for row in rows:
            conn.execute(
                f"INSERT INTO {table} ({colnames}) VALUES ({placeholders})",
                [row.get(c) for c in cols],
            )
    conn.commit()
    conn.close()
    logger.info(f"Restored {sum(len(v) for v in data.values())} rows from backup")


def _dump_to_json():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    data = {}
    for table in DB_TABLES:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]
        except Exception:
            data[table] = []
    conn.close()
    DATABASE_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_BACKUP_PATH.write_text(
        json.dumps(data, ensure_ascii=False, default=str, indent=2),
        encoding="utf-8",
    )
    _try_git_push()


def _try_git_push():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return
    try:
        import subprocess
        repo_dir = str(DATABASE_BACKUP_PATH.parent.parent)
        rel = os.path.relpath(str(DATABASE_BACKUP_PATH), repo_dir)
        subprocess.run(
            ["git", "-C", repo_dir, "config", "user.name", "AI Backup"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo_dir, "config", "user.email", "bot@example.com"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo_dir, "add", rel],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo_dir, "commit", "-m", f"auto-backup {datetime.now().isoformat()}"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", repo_dir, "push",
             f"https://x-access-token:{token}@github.com/lewislunora/lewislunora.git",
             "main"],
            capture_output=True, timeout=30,
        )
    except Exception as e:
        logger.warning(f"Git backup push failed: {e}")


def init_db():
    db_exists = DATABASE_PATH.exists() and DATABASE_PATH.stat().st_size > 100
    restore = not db_exists and _backup_exists()

    conn = _conn()

    if restore:
        conn.execute("PRAGMA foreign_keys=OFF")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            label TEXT DEFAULT '',
            credentials TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            platforms TEXT DEFAULT '[]',
            scheduled_at TEXT,
            status TEXT DEFAULT 'draft',
            language TEXT DEFAULT 'zh-TW',
            category TEXT DEFAULT '',
            media_urls TEXT DEFAULT '[]',
            ai_generated INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            published_at TEXT
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (content_id) REFERENCES contents(id)
        );

        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            recorded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (content_id) REFERENCES contents(id)
        );

        CREATE TABLE IF NOT EXISTS ai_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            prompt_template TEXT NOT NULL,
            platform TEXT DEFAULT '',
            category TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS kb_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keywords TEXT NOT NULL,
            answer TEXT NOT NULL,
            language TEXT DEFAULT 'zh-TW',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO kb_entries (id, keywords, answer, language) VALUES
        (1, '["方案","價格","費用","多少錢","pricing","plan","price","cost"]', '我們提供三種方案：\\n\\n① 入門版：免費，50次/天\\n② 專業版：NT$890/月，無限次數\\n③ 企業版：NT$5,990/月，無限次數+私有部署\\n\\n詳細比較請看 👉 https://lewislunora.onrender.com/product/#pricing', 'zh-TW'),
        (2, '["方案","價格","費用","多少錢","pricing","plan","price","cost"]', 'We offer 3 plans:\\n① Starter: Free, 50 chats/day\\n② Pro: $29/mo, unlimited\\n③ Enterprise: $199/mo, unlimited+private deployment\\n\\nSee details 👉 https://lewislunora.onrender.com/product/#pricing', 'en'),
        (3, '["功能","能做什麼","features","capabilities"]', '主要功能包括：\\n• AI 智能客服（24/7）\\n• 自動內容生成（文章+社群）\\n• 知識庫自增長\\n• 多平台分發\\n• 數據驅動優化\\n• AI 短劇創作', 'zh-TW'),
        (4, '["功能","能做什麼","features","capabilities"]', 'Key features:\\n• AI Customer Service (24/7)\\n• Auto Content Generation\\n• Self-Growing Knowledge Base\\n• Multi-Platform Distribution\\n• Data-Driven Optimization', 'en'),
        (5, '["平台","支援","platform","support","整合"]', '目前已支援：Telegram、Line、Facebook、Instagram。更多平台持續新增中。', 'zh-TW'),
        (6, '["平台","支援","platform","support","整合"]', 'Supported platforms: Telegram, Line, Facebook, Instagram. More coming soon.', 'en'),
        (7, '["開始","試用","註冊","start","trial","begin","signup"]', '開始很簡單：\\n1. 點擊「免費試用」按鈕\\n2. 加入我們的 Telegram 頻道\\n3. 設定你的知識庫\\n4. AI 立即上線\\n\\n立即開始 👉 https://lewislunora.onrender.com/product/', 'zh-TW'),
        (8, '["開始","試用","註冊","start","trial","begin","signup"]', 'Getting started:\\n1. Click "Free Trial"\\n2. Join our Telegram\\n3. Set up your knowledge base\\n4. AI goes live instantly', 'en'),
        (9, '["客服","customer service","support"]', 'AI 客服可以 24/7 自動回覆客戶問題。支援多語言、知識庫自增長、串接多平台。專業版每月只要 NT$890。企業版含私有部署。', 'zh-TW'),
        (10, '["客服","customer service","support"]', 'AI customer service works 24/7. Multi-language, self-growing KB, multi-platform. Pro $29/mo. Enterprise includes private deployment.', 'en'),
        (11, '["內容","content","文章","生成"]', '自動內容生成系統可以產出：品牌文章、社群貼文、行銷文案、電子報、短劇劇本。支援中英雙語。', 'zh-TW'),
        (12, '["內容","content","文章","生成"]', 'Auto content system generates: blog posts, social posts, marketing copy, newsletters, drama scripts. Chinese + English.', 'en'),
        (13, '["知識庫","knowledge base","kb"]', '知識庫是 AI 客服的核心。好的回答會自動保存，不好的會被淘汰。支援 👍/👎 回饋機制，越用越聰明。你現在就可以在 Dashboard 中編輯知識庫內容。', 'zh-TW'),
        (14, '["知識庫","knowledge base","kb"]', 'The knowledge base is the core. Good answers auto-save, bad ones get淘汰. 👍/👎 feedback system. You can edit KB entries in the Dashboard.', 'en'),
        (15, '["品牌","brand","app","應用"]', '品牌 App 使用 Flutter 開發，同時支援 iOS、Android 和 Web。內容從 JSON 讀取，無需後端即可更新。', 'zh-TW'),
        (16, '["品牌","brand","app","應用"]', 'Brand app built with Flutter. iOS + Android + Web. Content from JSON, no backend needed.', 'en'),
        (17, '["聯絡","contact","email","電話","line"]', '歡迎聯絡我們：\\n📧 lewislunora@gmail.com\\n✈️ Telegram 頻道：https://t.me/+QgAyWlVyIxFjNmRl\\n🤖 客服機器人：@ailunora_bot', 'zh-TW'),
        (18, '["聯絡","contact","email","電話","line"]', 'Contact us:\\n📧 lewislunora@gmail.com\\n✈️ Telegram: https://t.me/+QgAyWlVyIxFjNmRl\\n🤖 Bot: @ailunora_bot', 'en'),
        (19, '["展示","demo","演示"]', '觀看即時展示 👉 前往商品頁 https://lewislunora.onrender.com/product/ 直接體驗 AI 客服回覆。', 'zh-TW'),
        (20, '["展示","demo","演示"]', 'Live demo 👉 Visit https://lewislunora.onrender.com/product/ to try AI customer service.', 'en'),
        (21, '["ai","llm","groq","人工智慧"]', '系統使用 Groq Llama 3 LLM 驅動，支援智慧對話、內容生成、情感分析等功能。', 'zh-TW'),
        (22, '["ai","llm","groq","人工智慧"]', 'Powered by Groq Llama 3 LLM. Smart conversations, content generation, sentiment analysis.', 'en');

        CREATE TABLE IF NOT EXISTS kb_pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            language TEXT DEFAULT 'zh-TW',
            count INTEGER DEFAULT 1,
            ai_suggest TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT DEFAULT '',
            contact TEXT NOT NULL,
            email TEXT DEFAULT '',
            industry TEXT DEFAULT '',
            message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            salt TEXT DEFAULT '',
            token TEXT DEFAULT '',
            plan TEXT DEFAULT 'free',
            api_key TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO ai_templates (name, prompt_template, platform, category) VALUES
        ('社群貼文', '以{language}寫一篇關於{topic}的社群貼文，語氣{style}，長度約{length}字。加入3-5個相關hashtag。', 'facebook', 'social'),
        ('品牌文章', '以{language}寫一篇關於{topic}的品牌部落格文章，字數約{length}字，語氣{style}。包含引言、主體和結語。', 'blog', 'content'),
        ('產品文案', '以{language}寫一段關於{product}的產品推廣文案，字數約{length}字。強調{benefits}。', 'instagram', 'sales'),
        ('短劇劇本', '以{language}創作一個關於{topic}的短劇劇本，約{length}字。包含場景描述、對白和情感節奏。', 'drama', 'creative');
    """)
    conn.commit()

    if restore:
        conn.close()
        _restore_from_backup()
        return

    # Migration: add missing columns
    for col, col_def in [("email", "TEXT DEFAULT ''"), ("salt", "TEXT DEFAULT ''"), ("token", "TEXT DEFAULT ''")]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

    # After init, dump seed data as backup
    _dump_to_json()


def execute(sql, params=None):
    with _commit_lock:
        conn = _conn()
        cur = conn.execute(sql, params or [])
        conn.commit()
        last_id = cur.lastrowid
        conn.close()
        is_write = sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        if is_write:
            _dump_to_json()
        return last_id


def fetch(sql, params=None):
    conn = _conn()
    rows = conn.execute(sql, params or []).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_one(sql, params=None):
    rows = fetch(sql, params)
    return rows[0] if rows else None
