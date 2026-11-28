"""自然但不囉嗦的回覆引擎：網站 AI 精靈與 Telegram bot 共用。

目標：像人聊天——先回答、必要時再問一句；不條列、不標題、不長篇。
能力範圍寫死在 prompt，AI 不能自行承諾沒實作的功能。
"""
import logging
import re

from ..ai.generator import AIContentGenerator
from . import bot_learning

logger = logging.getLogger(__name__)

CAPABILITIES = (
    "即時計算、個人筆記、個人提醒、翻譯、整合搜尋、內容靈感、"
    "AI 生圖、語音轉文字、系統狀態、知識庫問答"
)
_DEFAULT_GEN = AIContentGenerator()
# 能力問題一律用固定白名單回答，不讓模型條列成一長串
_CAPABILITY_RE = re.compile(
    r"能做什麼|有哪些功能|功能有哪些|你會什麼|列出功能|有什麼功能|"
    r"what can you do|all commands", re.I,
)


def reply_budget(text: str, chat_id=None) -> tuple:
    """依對方訊息長度與群組習慣決定 (句數, 字數)，30–60 字、最多 3 句。"""
    lines, chars = bot_learning.reply_budget(chat_id)
    user_len = len((text or "").strip())
    # 對方寫得短也至少留 30 字，才不會把人話截成半句；上限 60 字。
    mirrored = max(30, min(60, round(user_len * 1.2) + 10))
    return lines, max(30, min(60, min(chars, mirrored)))


def _clip(part: str, room: int) -> str:
    """超長時在完整子句收尾，不留下「、，」這種斷頭結尾。"""
    if len(part) <= room:
        return part
    cut = part[:room]
    for sep in "。！？!?":
        idx = cut.rfind(sep)
        if idx >= max(8, room // 2):
            return cut[:idx + 1]
    for sep in "，,、；;：:":
        idx = cut.rfind(sep)
        if idx >= max(10, int(room * 0.6)):
            return cut[:idx].rstrip() + "…"
    return cut.rstrip("，,、；;：: —-") + "…"


def polish(text: str, max_lines: int = 2, max_chars: int = 45) -> str:
    """把模型輸出修成口語短回覆，去掉制式感。"""
    # 模型偶爾回傳字面 "\n"，先還原成換行再壓成空白，條列才會被清掉
    s = str(text or "").replace("\\n", "\n")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("**", "").replace("__", "").strip()
    s = re.sub(r"^(?:作為|身為)\s*AI[，,、]?\s*", "", s)
    s = re.sub(r"^(?:以下是|回覆：|答案：|好的[，,]\s*)+", "", s)
    s = re.sub(r"(?:^|\s)[•\-]\s*", "", s)
    s = re.sub(r"(?<!\d)\d+\.\s*", "", s)
    s = s.strip()
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?])\s*|\n+", s) if p.strip()]
    if not parts:
        return ""
    out = []
    total = 0
    for part in parts[:max_lines]:
        room = max_chars - total
        if room <= 0:
            break
        if len(part) > room:
            part = _clip(part, room)
        out.append(part)
        total += len(part)
        if total >= max_chars:
            break
    return "".join(out)[:max_chars]


def reply(text: str, *, chat_id=None, history=None, kb_answer: str = "",
          generator=None, persona: str = "") -> str:
    """自然回覆：KB 命中就直接回，其餘交給模型但限字數與能力範圍。"""
    max_lines, max_chars = reply_budget(text, chat_id)
    if kb_answer:
        return polish(kb_answer, max_lines, max_chars)
    if _CAPABILITY_RE.search(text or ""):
        return "計算、翻譯、搜尋這些我都會，想先試哪個？"
    gen = generator or _DEFAULT_GEN
    if not gen.is_available():
        return "我現在有點卡住，稍後再問我一次好嗎？"

    context = ""
    if history:
        recent = ["{}：{}".format(
            "我" if h.get("role") == "ai" else "對方", str(h.get("text", ""))[:80]
        ) for h in list(history)[-6:]]
        context = "近期對話：" + " | ".join(recent) + "\n" if recent else ""

    prompt = (
        (persona or "你是翔川 Neo 的助理，用繁體中文像朋友一樣自然聊天。") + "\n"
        + context
        + "對方說：" + (text or "") + "\n\n"
        + "請直接回覆：先回答，必要時最多再問一句。"
        + f"最多 {max_lines} 句、全段 {max_chars} 字以內，口語自然，"
        + "不要條列、不要一口氣列舉功能、不要標題、不要 emoji 轟炸、不要說「身為 AI」。\n"
        + "被問身份就簡單說自己是誰，再反問對方需要什麼。\n"
        + "被問「能做什麼」時用一句話帶過、反問想試哪個，不要條列或列舉超過三項。\n"
        + f"只能提到已實作的功能：{CAPABILITIES}。不會的就直說不會，不要編造。\n"
        + "需要登入的功能請提醒對方先登入，不要說已經幫他做好了。\n"
        + "只輸出回覆內容。"
    )
    try:
        result = gen.generate("", {"prompt": prompt})
    except Exception as e:
        logger.warning("natural reply failed: %s", e)
        return "我剛剛沒聽清楚，再說一次好嗎？"
    if not result or result.startswith(("❌", "⚠️")):
        return "我剛剛沒聽清楚，再說一次好嗎？"
    return polish(result, max_lines, max_chars)
