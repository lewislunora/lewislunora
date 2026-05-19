import sqlite3
import json
from datetime import datetime
from pathlib import Path
from .config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
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

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
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
    conn.close()


def execute(sql, params=None):
    conn = get_conn()
    cur = conn.execute(sql, params or [])
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def fetch(sql, params=None):
    conn = get_conn()
    rows = conn.execute(sql, params or []).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_one(sql, params=None):
    rows = fetch(sql, params)
    return rows[0] if rows else None
