"""共用 AI 工具：翻譯、生圖、資料搜尋。

網站 API 與 Telegram bot 都呼叫這裡，避免兩邊行為不一致。
翻譯用既有 Groq（文字模型）；生圖需另外設定 OPENAI_API_KEY。
"""
import base64
import json
import logging
import os

from ..ai.generator import ai_generator
from ..config import DATA_DIR
from ..database import fetch

logger = logging.getLogger(__name__)

LANG_NAMES = {
    "zh-TW": "繁體中文",
    "zh-CN": "簡體中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韓文",
}

IMAGE_SIZES = ("1024x1024", "1792x1024", "1024x1792")


def translate(text: str, target: str = "en", source: str = "auto") -> str:
    """忠實翻譯，保留專有名詞、數字與換行；只回譯文。"""
    text = (text or "").strip()
    if not text:
        return ""
    if not ai_generator.is_available():
        raise RuntimeError("需要設定 GROQ_API_KEY 才能翻譯")
    src = "自動偵測" if source == "auto" else LANG_NAMES.get(source, source)
    tgt = LANG_NAMES.get(target, target)
    prompt = (
        f"你是專業翻譯。將下列{src}文字忠實翻譯成{tgt}。"
        "保留專有名詞、數字、換行與原本語氣；只輸出譯文，不要解釋或加註。\n\n"
        + text[:8000]
    )
    result = ai_generator.generate("custom", {"prompt": prompt}).strip()
    if result.startswith(("❌", "⚠️")):
        raise RuntimeError(result)
    return result


def image_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", ""))


def generate_image(prompt: str, size: str = "1024x1024"):
    """回傳 (png_bytes, revised_prompt)；需 OPENAI_API_KEY。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("請輸入圖片描述")
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("需要設定 OPENAI_API_KEY 才能生成圖片")
    if size not in IMAGE_SIZES:
        raise ValueError(f"size 必須是 {', '.join(IMAGE_SIZES)}")

    import requests
    model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "prompt": prompt[:4000],
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        },
        timeout=120,
    )
    if not resp.ok:
        raise RuntimeError(f"生圖 API 失敗（{resp.status_code}）: {resp.text[:200]}")
    data = (resp.json().get("data") or [{}])[0]
    raw = data.get("b64_json")
    if not raw:
        raise RuntimeError("生圖 API 未回傳圖片內容")
    return base64.b64decode(raw), data.get("revised_prompt") or prompt


def search(q: str, scope: str = "all", limit: int = 5):
    """整合搜尋：gov=政府開放資料、kb=知識庫、web=網路、all=gov+kb。"""
    q = (q or "").strip()
    if not q:
        return []
    limit = min(max(limit, 1), 10)
    items = []

    if scope in ("all", "gov"):
        try:
            from . import govdata
            found = govdata.search(q, per_page=limit)
            for it in found.get("items", []):
                items.append({
                    "type": "gov",
                    "title": it.get("title", ""),
                    "url": f"/govdata?nid={it.get('nid', '')}",
                    "detail": f"{it.get('agency', '')}｜{it.get('formats', '')}",
                })
        except Exception as e:
            logger.warning(f"gov search failed: {e}")

    if scope in ("all", "kb"):
        try:
            like = f"%{q}%"
            rows = fetch(
                "SELECT keywords, answer FROM kb_entries "
                "WHERE keywords LIKE ? OR answer LIKE ? LIMIT ?",
                [like, like, limit],
            )
            for row in rows:
                try:
                    keys = json.loads(row["keywords"])
                    title = "、".join(keys[:3]) if isinstance(keys, list) else str(keys)
                except Exception:
                    title = row["keywords"]
                items.append({
                    "type": "kb",
                    "title": title or "知識庫條目",
                    "url": "/api/kb/query",
                    "detail": (row["answer"] or "")[:120],
                })
        except Exception as e:
            logger.warning(f"kb search failed: {e}")

    if scope == "web":
        try:
            from .web_roamer import WebRoamer
            for it in WebRoamer(data_dir=DATA_DIR).search(q, max_results=limit):
                items.append({
                    "type": "web",
                    "title": it.get("title", ""),
                    "url": it.get("url", ""),
                    "detail": it.get("engine", "web"),
                })
        except Exception as e:
            logger.warning(f"web search failed: {e}")

    return items[:limit]
