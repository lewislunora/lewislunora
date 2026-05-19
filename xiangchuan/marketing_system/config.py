import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "marketing.db"

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
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_MAX_TOKENS = 2048

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

BROWSER_HEADLESS = True
BROWSER_TIMEOUT = 30000

DEFAULT_SCHEDULE_TIME = "09:00"
MAX_CONTENT_LENGTH = 2000
LANGUAGES = ["zh-TW", "zh-CN", "en"]
