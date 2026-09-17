"""AI 短內容引擎：像 IG / Threads 的短貼文自動產出與同步發布。"""
import random
import logging
from ..config import GROQ_API_KEY, GROQ_MODEL, DATA_DIR
from ..database import fetch_one, fetch, execute

logger = logging.getLogger(__name__)

SHORT_TOPICS = [
    ("維運", "半夜系統當機，MTTR 30 分鐘的團隊都在做什麼？"),
    ("維運", "備份了 10 年的公司，9 成沒真的還原過一次"),
    ("維運", "發版不用拜拜——Blue/Green 部署讓舊版秒退回"),
    ("AI", "一人公司不需要工程團隊——這套 AI 系統就夠"),
    ("AI", "AI 客服為什麼沒效？90% 的人少了回饋機制"),
    ("AI", "我讓 AI 每天寫一章小說，第七天它自己埋了伏筆"),
    ("小說", "重生回 2004，只想逃離維運坑的主角又加班了"),
    ("小說", "機房撿到的伺服器跟我說：你的備份上週起就沒成功過"),
    ("生活", "被資遣的第 30 天，我發現最值錢的是這 11 年"),
    ("生活", "與其煩惱流量，不如去認識 10 個比你強的人"),
    ("時事", "2026 中文內容市場：短貼文拼的是『每天被想起』"),
    ("時事", "一人公司最該外包的不是會計，是客服"),
]

SHORT_FEED_COPY = {
    "維運": "回頭看今天做人要的……不是。這篇講的是系統該怎麼活下來。",
    "AI": "AI 不是魔法，是紀律。",
    "小說": "今天更新一章——看完記得來留言。",
    "生活": "寫給同樣在谷底爬的人。",
    "時事": "聊聊現在這個市場。",
}

PLATFORM_OPENING_LINES = {
    "threads": "聊聊",
    "facebook": "這篇值得存起來",
    "instagram": "IG 上的各位",
    "x": "",
}


def _pick_topic():
    cat, topic = random.choice(SHORT_TOPICS)
    follow = SHORT_FEED_COPY.get(cat, "")
    return cat, topic, follow


def _generate_short(cat, topic):
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY 未設定"
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        prompt = (
            f"你是中文短內容高手，目標是要讓讀者『每天都想回來』。\n"
            f"請用 60~120 字寫一篇貼文，主題：{topic}。\n"
            f"領域：{cat}。\n"
            f"風格：像 IG / Threads 上會被按讚轉發的那種——開頭一句話抓住人、中間有具體細節、\n"
            f"最後一句話留個鉤子讓人想留言。不用 hashtag、不要 emoji 連發。\n"
            f"不要寫成廣告，寫成『一個懂行的人分享經驗』。\n"
            f"務必使用繁體中文，不要使用簡體字。"
        )
        resp = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.85,
        )
        body = resp.choices[0].message.content.strip()
        return body, ""
    except Exception as e:
        logger.error(f"short content generate failed: {e}")
        return None, str(e)


def _publish_to_platforms(body, skip_post=None):
    """把同一篇同步發布到已連線的外部平台。回傳已發布的平台清單。"""
    published = []
    # 平台開場白不同，避免同時發一樣的內容
    variants = {}
    for platform, opening in PLATFORM_OPENING_LINES.items():
        if opening:
            variants[platform] = f"{opening}：{body}"
        else:
            variants[platform] = body

    from ..api.server import connectors, get_connectors  # lazy import 避免循環
    for platform, variant in variants.items():
        if platform == skip_post:
            continue
        conn = connectors.get(platform) or (get_connectors() or {}).get(platform)
        if not conn:
            continue
        try:
            conn.post(variant)
            published.append(platform)
            # 記錄到 promo_queue（審計）
            execute(
                "INSERT INTO promo_queue (platform, body, status) VALUES (?, ?, 'done')",
                (platform, variant),
            )
        except Exception as e:
            logger.warning(f"publish to {platform} failed: {e}")
    return published


def generate_and_publish(skip_post=None):
    """產一篇短內容 → 寫進網站 feed → 同步發布到外部平台。

    回傳 {correct, ok, post, published, error}。
    """
    cat, topic, follow = _pick_topic()
    body, err = _generate_short(cat, topic)
    if not body:
        return {"ok": False, "error": err or "產生失敗", "topic": topic}

    post_id = execute(
        "INSERT INTO feed_posts (user_id, content, post_type, author) VALUES (?, ?, ?, ?)",
        (None, body, "short", "AI 每日短想"),
    )
    published = _publish_to_platforms(body, skip_post=skip_post)
    return {
        "ok": True,
        "post_id": post_id,
        "topic": topic,
        "body": body,
        "published": published,
        "follow": follow,
    }

# 每日自動產文的排程鉤子（從 server 呼叫）
def auto_short_daily(max_per_day=2):
    from ..database import fetch
    today = fetch(
        "SELECT COUNT(*) AS c FROM feed_posts WHERE post_type='short' AND date(created_at)=date('now')"
    )[0]["c"]
    if today >= max_per_day:
        return {"ok": True, "skipped": True, "today": today}
    result = generate_and_publish()
    return result