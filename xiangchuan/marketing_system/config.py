import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR.parent.parent / "docs"
BACKUP_DIR = BASE_DIR.parent.parent / "docs" / "data"
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "marketing.db"
DATABASE_BACKUP_PATH = BACKUP_DIR / "db_backup.json"

SCHEDULER_CHECK_INTERVAL = 60
PORT = int(os.environ.get("PORT", "8742"))

PLATFORMS = {
    "telegram": {"enabled": True, "name": "Telegram", "icon": "✈️"},
    "line": {"enabled": True, "name": "Line", "icon": "💬"},
    "facebook": {"enabled": True, "name": "Facebook", "icon": "📘"},
    "instagram": {"enabled": True, "name": "Instagram", "icon": "📸"},
    "twitter": {"enabled": False, "name": "X/Twitter", "icon": "🐦"},
    "threads": {"enabled": False, "name": "Threads", "icon": "🧵"},
    "dcard": {"enabled": False, "name": "Dcard", "icon": "🦴"},
    "xiaohongshu": {"enabled": False, "name": "小紅書", "icon": "📕"},
}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_MAX_TOKENS = 2048

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "")
FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

FB_WEBHOOK_VERIFY_TOKEN = os.environ.get("FB_WEBHOOK_VERIFY_TOKEN", "")

GMAIL_CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8742").rstrip("/")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
FACEBOOK_APP_ID = os.environ.get("FACEBOOK_APP_ID", "")
FACEBOOK_APP_SECRET = os.environ.get("FACEBOOK_APP_SECRET", "")
INSTAGRAM_APP_ID = os.environ.get("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET", "")
LINE_LOGIN_CHANNEL_ID = os.environ.get("LINE_LOGIN_CHANNEL_ID", "")
LINE_LOGIN_CHANNEL_SECRET = os.environ.get("LINE_LOGIN_CHANNEL_SECRET", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")

BROWSER_HEADLESS = True
BROWSER_TIMEOUT = 30000

DEFAULT_SCHEDULE_TIME = "09:00"
MAX_CONTENT_LENGTH = 2000
LANGUAGES = ["zh-TW", "zh-CN", "en"]
