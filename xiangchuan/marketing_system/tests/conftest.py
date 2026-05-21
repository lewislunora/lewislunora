import os
import sys
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Set test env vars BEFORE any app imports
os.environ["GROQ_API_KEY"] = ""
os.environ["SMTP_USER"] = "test@example.com"
os.environ["SMTP_PASS"] = "test_pass"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = ""
os.environ["FACEBOOK_PAGE_TOKEN"] = ""

# Override DATABASE_PATH before importing app modules
import marketing_system.config as cfg
cfg.DATABASE_PATH = cfg.DATA_DIR / "test_marketing.db"
cfg.DATABASE_BACKUP_PATH = cfg.DATA_DIR / "test_backup.json"

# Clean up any previous test DB + backup
for p in [cfg.DATABASE_PATH, cfg.DATABASE_BACKUP_PATH]:
    if p.exists():
        p.unlink()

from marketing_system.database import init_db, execute, fetch, fetch_one
from marketing_system.api.server import app


@pytest.fixture(autouse=True)
def setup_db():
    """Re-initialize DB before each test"""
    for p in [cfg.DATABASE_PATH, cfg.DATABASE_BACKUP_PATH]:
        if p.exists():
            p.unlink()
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_content():
    return {
        "title": "Test Post",
        "body": "This is a test content body with sufficient length for testing.",
        "platforms": ["telegram", "line"],
        "language": "zh-TW",
        "category": "social",
    }


@pytest.fixture
def sample_contact():
    return {
        "姓名": "Test User",
        "公司": "Test Corp",
        "聯絡方式": "test@example.com",
        "Email": "test@example.com",
        "行業別": "tech",
        "備註": "I want to know more about the professional plan.",
    }


@pytest.fixture
def sample_kb_entry():
    return {
        "keywords": ["方案", "價格", "費用"],
        "answer": "我們提供三種方案：入門版免費，專業版NT$890/月，企業版NT$5,990/月",
        "language": "zh-TW",
    }


@pytest.fixture
def sample_account():
    return {
        "platform": "telegram",
        "label": "Test Channel",
        "credentials": {"bot_token": "test:token", "chat_id": "-100123456"},
    }
