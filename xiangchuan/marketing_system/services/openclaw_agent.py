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
from . import bot_learning as learning
from . import natural_reply
from .knowledge_base import get_kb_reply, save_unanswered

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
    "ai": "🤖 自然語言提問（AI 自動判讀意圖）",
    "靈感": "💡 產生內容靈感（可接主題，例如 /靈感 AI 行銷）",
    "idea": "💡 Generate content ideas (English)",
    "翻譯": "🌐 翻譯（/翻譯 文字 或 /翻譯 en: 文字）",
    "translate": "🌐 Translate (/translate text or /translate zh-TW: text)",
    "搜尋": "🔍 整合搜尋（政府資料＋知識庫＋網路）",
    "search": "🔍 Search (gov data, knowledge base, web)",
    "生圖": "🎨 AI 生圖（僅對內，需 OPENAI_API_KEY）",
    "image": "🎨 Generate image (internal only)",
    "計算": r"🧮 安全計算（/計算 (1+2)\*3、sqrt(16)）",
    "calc": r"🧮 Calculator (/calc (1+2)\*3)",
    "筆記": "📝 個人筆記（/筆記 內容、/筆記 列表、/筆記 刪除 3；僅對內）",
    "note": "📝 Personal notes (internal only)",
    "提醒": "⏰ 個人提醒（/提醒 30分鐘後 喝水；僅對內）",
    "remind": "⏰ Reminders (internal only)",
    "語音": "🎤 直接傳語音訊息即轉文字（僅對內）",
    "voice": "🎤 Send a voice message to transcribe (internal only)",
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


def _cmd_start(chat_id=None):
    if chat_id is not None and not policy.is_internal(chat_id):
        return (
            "🤖 *OpenClaw AI 助手已啟動！*\n\n"
            "公開功能：\n"
            "💡 內容靈感／🌐 翻譯／🔍 整合搜尋\n"
            "🧮 計算\n\n"
            "輸入 /help 查看公開指令。"
        )
    return (
        "🤖 *OpenClaw AI 助手已啟動！*\n\n"
        "我是你的 AI 個人助理，可以幫你：\n"
        "💡 產生內容靈感／🌐 翻譯／🔍 整合搜尋\n"
        "🧮 計算／📝 筆記／⏰ 提醒／🎤 語音轉文字\n"
        "🎨 AI 生圖／🚀 觸發網站部署\n"
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


# ── 個人工具：計算 / 筆記 / 提醒 / 語音 ──────────────────────────────
def _cmd_calc(args=""):
    expr = (args or "").strip()
    if not expr:
        return "🧮 用法：/計算 (1+2)*3、sqrt(16)、pi*2\n可用 + - * / % ^ ** 與 sqrt/log/sin/cos 等函數"
    try:
        from .personal_tools import calculate
        return f"🧮 {_md_safe(expr)} = *{calculate(expr)}*"
    except ValueError as e:
        return f"⚠️ {e}"


def _cmd_notes(args="", chat_id=None):
    from .personal_tools import add_note, delete_note, list_notes, owner_for_chat
    owner = owner_for_chat(chat_id)
    raw = (args or "").strip()
    if not raw or raw.lower() in ("列表", "list", "列出"):
        rows = list_notes(owner, limit=10)
        if not rows:
            return "📝 還沒有筆記。用 /筆記 想記的事 新增。"
        lines = ["📝 *我的筆記*"]
        for row in rows:
            lines.append(f"#{row['id']} {_md_safe(row['content'][:200])}")
        return "\n".join(lines)
    m = re.match(r"^(刪除|delete|del)\s+(\d+)$", raw, re.I)
    if m:
        ok = delete_note(owner, int(m.group(2)))
        return f"📝 已刪除 #{m.group(2)}" if ok else "⚠️ 找不到該筆記（或已被刪除）。"
    item = add_note(owner, raw)
    return f"📝 已記錄（#{item['id']}）：{_md_safe(item['content'][:200])}"


def _cmd_remind(args="", chat_id=None):
    from .personal_tools import add_reminder, cancel_reminder, list_reminders, owner_for_chat
    owner = owner_for_chat(chat_id)
    raw = (args or "").strip()
    if not raw or raw.lower() in ("列表", "list", "列出"):
        rows = list_reminders(owner, limit=10)
        if not rows:
            return "⏰ 還沒有提醒。用 /提醒 30分鐘後 喝水 新增。"
        lines = ["⏰ *我的提醒*"]
        for row in rows:
            lines.append(f"#{row['id']} [{row['status']}] {row['due_at']} {_md_safe(row['text'][:100])}")
        return "\n".join(lines)
    m = re.match(r"^(取消|cancel)\s+(\d+)$", raw, re.I)
    if m:
        ok = cancel_reminder(owner, int(m.group(2)))
        return f"⏰ 已取消 #{m.group(2)}" if ok else "⚠️ 找不到待觸發的提醒。"
    # 先認絕對時間（含空白），再認「30分鐘後」等相對時間
    m = re.match(r"^(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?)\s+(.+)$", raw)
    if not m:
        m = re.match(r"^(\d+\s*(?:秒|分鐘|分|小時|時|天|日|週)\s*後?)\s+(.+)$", raw)
    if not m:
        return "⏰ 用法：/提醒 30分鐘後 喝水，或 /提醒 2026-11-28 10:00 開會"
    due_raw, text = m.group(1), m.group(2).strip()
    if not text:
        return "⚠️ 請輸入提醒內容。"
    try:
        item = add_reminder(owner, text, due_raw, chat_id=str(chat_id or ""))
    except ValueError as e:
        return f"⚠️ {e}"
    return f"⏰ 已設定（#{item['id']}）：{item['due_at']} — {_md_safe(text[:120])}"


def _download_telegram_file(file_id) -> bytes:
    info = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        json={"file_id": file_id}, timeout=20,
    ).json()
    path = (info.get("result") or {}).get("file_path", "")
    if not path:
        raise RuntimeError("取得語音檔失敗")
    resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/{path}", timeout=60)
    resp.raise_for_status()
    return resp.content


def process_voice(message):
    """語音訊息轉文字（僅對內，避免外部群組產生 OpenAI/Groq 費用）。"""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    voice = message.get("voice") or {}
    file_id = voice.get("file_id")
    if not chat_id or not file_id or not policy.is_internal(chat_id):
        return None
    if _throttled(chat_id, "voice", 10):
        return "⏳ 語音請 10 秒後再試。"
    try:
        from .ai_tools import transcribe
        text = transcribe(_download_telegram_file(file_id), voice.get("file_name") or "voice.ogg")
        return f"🎤 *語音轉文字*\n{_md_safe(text[:4000])}"
    except Exception as e:
        return f"⚠️ {e}"


def wants_capabilities(text: str) -> bool:
    """「列出功能」類問題直接回指令表，不讓 AI 自由編造能力。"""
    s = (text or "").strip().lower()
    return any(k in s for k in (
        "列出所有可執行功能", "列出功能", "有哪些功能", "有什麼功能",
        "能做什麼", "你會什麼", "有哪些指令", "all commands", "what can you do",
    ))


# ── 自然語言意圖判讀 ──────────────────────────────────────────────────
# AI 只能在這份代號表裡選，不能自由承諾功能（避免「情感分析」類幻覺）。
_INTENT_CODES = (
    "help", "stop", "calc", "translate", "search",
    "note", "remind", "image", "status", "deploy", "idea",
    "unsupported", "faq",
)
_INTERNAL_INTENTS = frozenset({"note", "remind", "image", "status", "deploy"})

_STOP_RE = re.compile(
    r"(關閉|關掉|停用|停止|安靜|不要回|disable|turn\s*off|stop).{0,24}"
    r"(openclaw|ai\s*助手|bot|機器人|助理|回覆|自動回)"
    r"|(openclaw|ai\s*助手|bot|機器人|助理|自動回覆).{0,24}"
    r"(關閉|關掉|停用|停止|安靜|不要回|disable|turn\s*off|stop)",
    re.I,
)
_UNSUPPORTED_RE = re.compile(
    r"情感分析|情緒分析|sentiment|個人日曆|日曆|語音撥打|撥打|打電話|"
    r"購物|下單|訂餐|外送|改程式|寫程式|修改程式|開關觸發邏輯",
    re.I,
)
_RULES = (
    ("calc", (r"計算|算一下|算算|加起來|乘以|除以|sqrt\s*\(|\bcalc\b|\d+\s*[+\-*/^%]\s*\d+",)),
    ("translate", (r"翻譯|翻成|譯成|英文怎麼說|中文怎麼說|\btranslate\b",)),
    ("search", (r"搜尋|查找|查一下|查資料|\bsearch\b|\bgoogle\b",)),
    ("remind", (r"提醒|通知我|幾分鐘後|小時後|\bremind\b",)),
    ("note", (r"筆記|記一下|記住|記錄一下|\bnote\b",)),
    ("image", (r"生圖|產生圖片|畫一張|畫個|\bimage\b|\bdraw\b",)),
    ("status", (r"系統狀態|\bstatus\b",)),
    ("deploy", (r"部署|上線|更新網站|\bdeploy\b",)),
    ("idea", (r"靈感|點子|構思|文案|內容點子|\bidea\b",)),
)
_INTENT_ARGS = {
    "calc": r"^(?:請|幫我)?(?:算一下|算算|計算|calc)\s*",
    "translate": r"^(?:請|幫我)?(?:翻譯成|翻譯|翻成|譯成|translate)\s*",
    "search": r"^(?:請|幫我)?(?:搜尋|查找|查一下|search)\s*",
    "note": r"^(?:請|幫我)?(?:筆記|記一下|記住|記錄一下|note)\s*",
    "remind": r"^(?:請|幫我)?(?:提醒我|提醒|通知我|remind)\s*",
    "image": r"^(?:請|幫我)?(?:生圖|產生圖片|畫一張|畫個|image|draw)\s*",
}
_INTENT_PROMPT = (
    "你是意圖分類器，不是問答機器人。只輸出一行代號："
    "help/stop/calc/translate/search/note/remind/image/status/deploy/idea/unsupported/faq。"
    "若代號是 faq，第二行才可直接給繁體中文自然回答（45 字內、像聊天、不要條列）。"
    "絕對不要輸出代號表以外的功能，也不要承諾未列出的能力。"
    "stop=使用者想關閉或停用助手；unsupported=要求未實作功能或改程式。\n"
    "訊息："
)


def _kb_answer(text):
    try:
        return get_kb_reply(text) or ""
    except Exception as e:
        logger.warning("KB lookup failed: %s", e)
        return ""


def _remember_unanswered(text):
    """重複出現的問題交由既有 auto_learn() 變成知識庫答案。"""
    if not (text or "").strip():
        return
    try:
        save_unanswered(text.strip(), "zh-TW")
    except Exception as e:
        logger.warning("save unanswered failed: %s", e)


def classify_intent(text, chat_id=None):
    """回 (intent, answer_hint)。先規則、後 KB、最後 AI 選代號。"""
    s = (text or "").strip()
    if not s:
        return "faq", ""
    if wants_capabilities(s):
        return "help", ""
    if _STOP_RE.search(s):
        return "stop", ""
    if _UNSUPPORTED_RE.search(s):
        return "unsupported", ""
    for code, patterns in _RULES:
        if any(re.search(p, s, re.I) for p in patterns):
            return code, s
    kb = _kb_answer(s)
    if kb:
        return "faq", kb
    if not ai_gen.is_available():
        return "faq", ""
    try:
        result = ai_gen.generate("", {"prompt": _INTENT_PROMPT + s})
    except Exception as e:
        logger.warning("intent classify failed: %s", e)
        return "faq", ""
    lines = [line.strip() for line in (result or "").splitlines() if line.strip()]
    code = re.sub(r"[^a-z_]+", "", lines[0].lower()) if lines else ""
    if code in _INTENT_CODES:
        return code, "\n".join(lines[1:])
    # AI 沒照格式輸出：把內容當成 faq 簡答，不再多打一次 API。
    return "faq", (result or "").strip()


def _cmd_stop():
    return "想讓我安靜啊？在群組別 @ 我就不會回；真的要停用，跟站長說一聲就好。"


def route_natural_language(text, chat_id=None):
    """自然語言統一入口：AI 判讀意圖後轉給既有指令，不新增假功能。"""
    intent, hint = classify_intent(text, chat_id)
    if intent == "help":
        return _cmd_help(chat_id)
    if intent == "stop":
        return _cmd_stop()
    if intent in _INTERNAL_INTENTS and not policy.is_internal(chat_id):
        return "🔒 此功能僅供對內群組使用。"
    if intent == "unsupported":
        _remember_unanswered(text)
        return "這我還不會耶～目前會的是計算、翻譯、搜尋這些，打 /help 我列給你。"
    if intent == "faq":
        _remember_unanswered(text)
        if hint:
            return _shorten(hint, chat_id=chat_id)
        return short_answer(text, chat_id)
    pattern = _INTENT_ARGS.get(intent)
    args = re.sub(pattern, "", (text or "").strip(), flags=re.I).strip() if pattern else (text or "").strip()
    return _handle_command(chat_id, intent, args)


def _shorten(text: str, limit: int = 60, chat_id=None) -> str:
    """依群組習慣壓短：最多 3 句 / 60 字（預設 2 句 / 45 字）。"""
    max_lines, max_chars = learning.reply_budget(chat_id)
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    parts = [p.strip() for p in re.split(r"[\n。！？!?]+", clean) if p.strip()]
    lines = []
    for part in parts[:max_lines]:
        if len(part) > max_chars:
            part = part[:max_chars].rstrip() + "…"
        lines.append(part)
        if sum(len(x) for x in lines) >= limit:
            break
    return "\n".join(lines)[:limit]


def short_answer(text: str, chat_id=None) -> str:
    """自然但不囉嗦的客服回覆（與網站共用同一套語氣與字數規則）。"""
    return natural_reply.reply(text, chat_id=chat_id, generator=ai_gen)


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
        lines.append("\n🔒 自動化 / 部署 / 狀態 / 生圖 / 筆記 / 提醒 / 語音僅供對內群組使用。")
    return "\n".join(lines)


def _handle_command(chat_id, cmd, args=""):
    if cmd in ("start",):
        return _cmd_start(chat_id)
    elif cmd in ("ai",):
        return route_natural_language(args, chat_id)
    elif cmd in ("靈感", "idea"):
        return _cmd_idea(args)
    elif cmd in ("翻譯", "translate"):
        return _cmd_translate(args, chat_id)
    elif cmd in ("搜尋", "search"):
        return _cmd_search(args)
    elif cmd in ("生圖", "image"):
        return _cmd_image(args, chat_id)
    elif cmd in ("計算", "calc"):
        return _cmd_calc(args)
    elif cmd in ("筆記", "note"):
        return _cmd_notes(args, chat_id)
    elif cmd in ("提醒", "remind"):
        return _cmd_remind(args, chat_id)
    elif cmd in ("語音", "voice"):
        return "🎤 直接在私聊或對內群組傳語音訊息，我就會回文字（10 秒冷卻）。"
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
    chat_type = chat.get("type", "private")

    # 只學統計、不存原文；在 should_respond 之前觀察，才能學到「沒被回覆」的聊天習慣。
    if chat_type in learning.GROUP_TYPES and text:
        learning.observe(
            chat_id, text,
            is_question=policy.looks_like_question(text),
            is_mention=f"@{policy.BOT_USERNAME.lower()}" in text.lower(),
        )

    # 語音訊息沒有 text，需先於 should_respond 處理（僅對內）。
    if message.get("voice"):
        reply = process_voice(message)
        if reply:
            _send_result(chat_id, reply, message.get("message_id"))
        return

    # 對外群組未 @bot 或未 opt-in → 靜默忽略，不回「未授權」洗版
    if not policy.should_respond(message):
        return

    clean = policy.clean_text(text, chat_type)
    if wants_capabilities(clean):
        _send_message(chat_id, _cmd_help(chat_id))
        return
    if clean.startswith("/"):
        parts = clean[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        if policy.command_internal_only(cmd) and not policy.is_internal(chat_id):
            response = "🔒 此指令僅供對內群組使用。"
        else:
            response = _handle_command(chat_id, cmd, args)
    else:
        # 自然語言交給同一套意圖引擎：計算／翻譯／筆記／提醒都免打斜線。
        response = route_natural_language(clean, chat_id)
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
