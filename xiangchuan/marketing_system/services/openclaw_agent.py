"""
OpenClaw Telegram Bot Agent - AI assistant for 翔川 Neo｜曜科技
Provides inspiration, deployment, and system management via Telegram.
"""
import os
import re
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
    "翻譯": "🌐 翻譯（/翻譯 文字 或 /翻譯 en: 文字）",
    "translate": "🌐 Translate (/translate text or /translate zh-TW: text)",
    "搜尋": "🔍 整合搜尋（政府資料＋知識庫＋網路）",
    "search": "🔍 Search (gov data, knowledge base, web)",
    "生圖": "🎨 AI 生圖（僅對內，需 OPENAI_API_KEY）",
    "image": "🎨 Generate image (internal only)",
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
        "🌐 翻譯文字／🔍 整合搜尋／🎨 AI 生圖\n"
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


# ── 翻譯 / 搜尋 / 生圖（網站 API 與 bot 共用 ai_tools） ─────────────
_last_tool_call = {}
_LANG_ALIAS = {
    "zh-tw": "zh-TW", "zh-cn": "zh-CN", "zh": "zh-TW",
    "en": "en", "ja": "ja", "jp": "ja", "ko": "ko",
}


def _throttled(chat_id, cmd, seconds=5):
    """簡單的每 chat 冷卻，避免公開群組洗版或暴衝 API 額度。"""
    key = (str(chat_id), cmd)
    now = time.time()
    if now - _last_tool_call.get(key, 0) < seconds:
        return True
    _last_tool_call[key] = now
    return False


def _md_safe(text) -> str:
    """Telegram Markdown v1 會把這些符號當語法，先跳脫。"""
    return re.sub(r"([_*\[\]`])", r"\\\1", str(text or ""))


def _send_photo(chat_id, png_bytes, caption="", reply_to=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        payload = {"chat_id": chat_id, "caption": (caption or "")[:1000]}
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        requests.post(
            url,
            data=payload,
            files={"photo": ("ai-image.png", png_bytes, "image/png")},
            timeout=90,
        )
    except Exception as e:
        logger.error(f"Telegram sendPhoto failed: {e}")


def _send_result(chat_id, result, reply_to=None):
    """指令回傳可能是文字，也可能是要直接貼圖的 dict。"""
    if isinstance(result, dict) and result.get("photo"):
        _send_photo(chat_id, result["photo"], result.get("caption", ""), reply_to)
    else:
        _send_message(chat_id, result)


def _cmd_translate(args="", chat_id=None):
    if _throttled(chat_id or "bot", "translate"):
        return "⏳ 請 5 秒後再試。"
    raw = (args or "").strip()
    if not raw:
        return "🌐 用法：/翻譯 文字，或 /翻譯 en: 文字\n語言代碼：zh-TW / zh-CN / en / ja / ko"
    target = None
    text = raw
    m = re.match(r"^(zh-tw|zh-cn|zh|en|ja|jp|ko)\s*[:：]\s*(.+)$", raw, re.I | re.S)
    if m:
        target = _LANG_ALIAS.get(m.group(1).lower(), m.group(1))
        text = m.group(2).strip()
    else:
        # 有中文字 → 譯成英文；否則譯成繁中
        target = "en" if re.search(r"[\u4e00-\u9fff]", raw) else "zh-TW"
    if not text:
        return "⚠️ 請輸入要翻譯的內容。"
    try:
        from .ai_tools import translate
        result = translate(text, target)
    except Exception as e:
        return f"⚠️ {e}"
    return f"🌐 *翻譯（→{target}）*\n{_md_safe(result[:4000])}"


def _cmd_search(args=""):
    q = (args or "").strip()
    if not q:
        return "🔍 用法：/搜尋 關鍵字，或 /搜尋 web: 關鍵字\n範圍：all / gov / kb / web"
    scope = "all"
    m = re.match(r"^(all|gov|kb|web)\s*[:：]\s*(.+)$", q, re.I | re.S)
    if m:
        scope = m.group(1).lower()
        q = m.group(2).strip()
    if not q:
        return "⚠️ 請輸入搜尋關鍵字。"
    try:
        from .ai_tools import search
        items = search(q, scope, limit=5)
    except Exception as e:
        return f"⚠️ {e}"
    if not items:
        return f"🔍 「{_md_safe(q)}」沒有找到結果。"
    lines = [f"🔍 *搜尋結果：{_md_safe(q)}*"]
    for i, it in enumerate(items, 1):
        url = it.get("url") or ""
        lines.append(
            f"{i}. {_md_safe(it.get('title', ''))}\n"
            f"   {_md_safe(it.get('detail', ''))[:160]}"
            + (f"\n   {url}" if url else "")
        )
    return "\n".join(lines)


def _cmd_image(args="", chat_id=None):
    if _throttled(chat_id or "bot", "image", 10):
        return "⏳ 生圖請 10 秒後再試。"
    raw = (args or "").strip()
    if not raw:
        return "🎨 用法：/生圖 圖片描述（或 /生圖 1792x1024 描述）"
    size = "1024x1024"
    m = re.match(r"^(1024x1024|1792x1024|1024x1792)\s+(.+)$", raw, re.I | re.S)
    if m:
        size, raw = m.group(1).lower(), m.group(2).strip()
    try:
        from .ai_tools import generate_image
        png, revised = generate_image(raw, size)
    except Exception as e:
        return f"⚠️ {e}"
    return {"photo": png, "caption": f"🎨 {revised[:600]}"}


def _shorten(text: str, limit: int = 60) -> str:
    """把回覆壓成短句：目標約 15 字，最長 limit 字。"""
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    for sep in ("\n", "。", "！", "？", ". ", "! "):
        if sep in clean:
            clean = clean.split(sep, 1)[0].strip()
            break
    if len(clean) > limit:
        clean = clean[:limit].rstrip() + "…"
    return clean


def short_answer(text: str) -> str:
    """對外群組/頻道的簡短回覆（目標約 15 字）。"""
    if not ai_gen.is_available():
        return "⚠️ AI 未啟用"
    result = ai_gen.generate(
        "",
        {
            "prompt": (
                "你是翔川 Neo 的客服助理。請用繁體中文回答下面的問題，"
                "答案盡量 15 個字左右，直接給答案，不要條列、不要標題、不要多餘說明。\n"
                f"問題：{text}"
            )
        },
    )
    return _shorten(result)


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
        lines.append("\n🔒 自動化 / 部署 / 狀態 / 生圖僅供對內群組使用。")
    return "\n".join(lines)


def _handle_command(chat_id, cmd, args=""):
    if cmd in ("start",):
        return _cmd_start()
    elif cmd in ("靈感", "idea"):
        return _cmd_idea(args)
    elif cmd in ("翻譯", "translate"):
        return _cmd_translate(args, chat_id)
    elif cmd in ("搜尋", "search"):
        return _cmd_search(args)
    elif cmd in ("生圖", "image"):
        return _cmd_image(args, chat_id)
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
    elif policy.is_internal(chat_id):
        # 私人工作群：已 @bot，可給完整 AI 回覆（含控制指令能力）
        response = _handle_command(chat_id, "靈感", clean)
    else:
        # 對外群組/頻道：自動判斷提問，只回簡短訊息
        response = short_answer(clean)
    _send_result(chat_id, response)


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
