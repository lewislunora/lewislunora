"""
OpenClaw Telegram Bot Agent - AI assistant for 翔川 Neo｜曜科技
Provides inspiration, deployment, and system management via Telegram.
"""
import os
import time
import logging
import threading
from datetime import datetime

import requests

from ..ai.generator import AIContentGenerator
from ..config import TELEGRAM_BOT_TOKEN, GROQ_API_KEY
from . import telegram_policy as policy

logger = logging.getLogger(__name__)

BOT_TOKEN = TELEGRAM_BOT_TOKEN
ALLOWED_CHAT_IDS = sorted(
    policy.INTERNAL_CHAT_IDS
    | policy.LINKED_CHANNEL_IDS
    | {os.getenv("TELEGRAM_NOTIFY_CHAT_ID", "626453598")}
    | {c.strip() for c in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if c.strip()}
)
DEPLOY_HOOK_URL = os.getenv("RENDER_DEPLOY_HOOK", "")

ai_gen = AIContentGenerator()

COMMANDS = {
    "start": "🚀 啟動 OpenClaw AI 助手",
    "靈感": "💡 產生內容靈感（可接主題，例如 /靈感 AI 行銷）",
    "idea": "💡 Generate content ideas (English)",
    "自動化": "⚙️ 觸發 AI 自動化內容生成",
    "部署": "🚀 觸發部署（網站更新）",
    "deploy": "🚀 Trigger deployment",
    "狀態": "📊 查看系統狀態",
    "status": "📊 Check system status",
    "幫助": "📋 顯示所有指令",
    "help": "📋 Show all commands",
}


def _send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


def _is_authorized(chat_id):
    return str(chat_id) in ALLOWED_CHAT_IDS


def _cmd_start():
    return (
        "🤖 *OpenClaw AI 助手已啟動！*\n\n"
        "我是你的 AI 個人助理，可以幫你：\n"
        "💡 產生內容靈感\n"
        "🚀 觸發網站部署\n"
        "📊 查看系統狀態\n\n"
        "輸入 /help 查看所有指令。"
    )


def _cmd_idea(topic=""):
    if not ai_gen.is_available():
        return "⚠️ AI 功能未啟用（需要設定 GROQ_API_KEY）"

    prompt = topic.strip() or "請給我一個創意的社群媒體內容點子"
    result = ai_gen.generate(
        "",
        {
            "prompt": (
                "你是一個行銷創意總監。根據主題「" + prompt + "」"
                "產生 3 個吸引人的內容點子，"
                "每個點子包含標題、文案方向、適合平台。用繁體中文回答。"
            )
        },
    )
    return f"💡 *內容靈感*\n主題：{prompt}\n\n{result}"


def _cmd_deploy():
    if DEPLOY_HOOK_URL:
        try:
            resp = requests.post(DEPLOY_HOOK_URL, timeout=30)
            if resp.ok:
                return (
                    "🚀 *部署已觸發！*\n"
                    "網站正在更新中，約 1-2 分鐘完成。\n\n"
                    "📌 GitHub Pages: https://lewislunora.github.io/lewislunora/\n"
                    "📌 Render: https://lewislunora.onrender.com/"
                )
            else:
                return f"⚠️ 部署觸發失敗：HTTP {resp.status_code}"
        except Exception as e:
            return f"⚠️ 部署請求錯誤：{e}"
    return (
        "🚀 *部署方式*\n\n"
        "目前支援的部署方式：\n"
        "1️⃣ GitHub Push → GitHub Pages 自動更新\n"
        "2️⃣ Render 自動偵測 GitHub 變更\n\n"
        "💡 設定 `RENDER_DEPLOY_HOOK` 環境變數即可透過此指令觸發部署。"
    )


def _cmd_auto(args=""):
    if not ai_gen.is_available():
        return "⚠️ AI 功能未啟用（需要設定 GROQ_API_KEY）"

    topic = args.strip() or "請給我一個創意的社群媒體內容點子"
    result = ai_gen.generate(
        "",
        {
            "prompt": (
                "你是 AI 自動化作業台。根據主題「" + topic + "」"
                "產生 1 個可執行的自動化內容任務（標題、文案方向、適合平台）。"
                "用繁體中文回答。"
            )
        },
    )
    return f"⚙️ *AI 自動化*\n任務主題：{topic}\n\n{result}"


def _cmd_status():
    ai_ok = ai_gen.is_available()
    groq_set = bool(GROQ_API_KEY)
    deploy_set = bool(DEPLOY_HOOK_URL)

    return (
        "📊 *系統狀態*\n\n"
        f"🤖 AI 引擎：{'✅ 正常' if ai_ok else '❌ 未啟用'}\n"
        f"🔑 Groq API：{'✅ 已設定' if groq_set else '❌ 未設定'}\n"
        f"🚀 部署鉤子：{'✅ 已設定' if deploy_set else '⚠️ 未設定'}\n"
        "⏰ 當前時間：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


def _cmd_help(chat_id=None):
    lines = ["📋 *OpenClaw 指令列表*\n"]
    allowed = policy.allowed_commands(chat_id) if chat_id is not None else policy.ALL_COMMANDS
    for cmd, desc in COMMANDS.items():
        if cmd.lower() in allowed:
            lines.append(f"/{cmd} — {desc}")
    if chat_id is not None and policy.is_external(chat_id):
        lines.append("\n🔒 自動化 / 部署 / 狀態僅供對內群組使用。")
    return "\n".join(lines)


def _handle_command(chat_id, cmd, args=""):
    if cmd in ("start",):
        return _cmd_start()
    elif cmd in ("靈感", "idea"):
        return _cmd_idea(args)
    elif cmd in ("自動化", "auto"):
        return _cmd_auto(args)
    elif cmd in ("部署", "deploy"):
        return _cmd_deploy()
    elif cmd in ("狀態", "status"):
        return _cmd_status()
    elif cmd in ("幫助", "help"):
        return _cmd_help(chat_id)
    return f"❌ 未知指令：`/{cmd}`\n請輸入 /help 查看可用指令"


def _process_update(update):
    message = update.get("message")
    if not message:
        return

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    # 對外群組未 @bot 或未 opt-in → 靜默忽略，不回「未授權」洗版
    if not policy.should_respond(message):
        return

    clean = policy.clean_text(text, chat.get("type", "private"))
    if clean.startswith("/"):
        parts = clean[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        if policy.command_internal_only(cmd) and not policy.is_internal(chat_id):
            response = "🔒 此指令僅供對內群組使用。"
        else:
            response = _handle_command(chat_id, cmd, args)
    else:
        response = _handle_command(chat_id, "靈感", clean)
    _send_message(chat_id, response)


def run_poller():
    if not BOT_TOKEN:
        logger.warning("OpenClaw agent: TELEGRAM_BOT_TOKEN not set, skipping")
        return

    offset = 0
    logger.info("OpenClaw agent started, polling Telegram...")

    while True:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                json={"offset": offset, "timeout": 30},
                timeout=35,
            )
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        _process_update(update)
                    except Exception as e:
                        logger.error(f"OpenClaw agent handler error: {e}")
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            logger.error(f"OpenClaw agent poll error: {e}")
            time.sleep(5)


def start_agent():
    thread = threading.Thread(target=run_poller, daemon=True)
    thread.start()
    return thread
