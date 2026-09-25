"""SEO 長尾文章引擎 — 每天自動產一篇受維運/職場/小說主題的文章。

機會：學術區與業界少有「系統性、持續更新、繁體中文」的實戰維運文章，
Google 對「別人不寫、你寫得深」的長尾主題給健康的自然流量。
策略：每天用 GROQ 產一篇 800~1200 字繁體文章，寫入 seo_articles，
排進 sitemap 讓 Google 收錄。
"""
import logging
import re
from ..config import GROQ_API_KEY, GROQ_MODEL
from ..database import fetch, fetch_one, execute

logger = logging.getLogger(__name__)

# 長尾主題池：都是「明明很多人搜、卻少有人寫深」的維運/工程/職場庶民題
SEO_TOPICS = [
    "伺服器半夜告警的標準處理流程",
    "資料庫備份是真的還原得出的嗎",
    "工作十年為什麼還在做同樣的事",
    "Nginx 502 的 11 種原因與解法",
    "如何判斷雲端帳單是不是被偷打",
    "寫個監控告警叫負責人起床是否合理",
    "老舊系統該重寫還是繼續打補丁",
    "中午午休該不該關機省電",
    "從機房轉型雲端的第一個月怎麼過",
    "為什麼老是有人在半夜改程式",
    "碰一次就上手：Docker 部署自架服務",
    "工程師的焦慮：隨時怕被通知",
    "離職交接是悲劇還是機會",
    "一個優良 SLA 文件該長什麼樣",
    "當你發現同事刪了生產資料庫",
]


def _slugify(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s).strip("-")
    return s[:60] or f"article-{int(__import__('time').time())}"


def _call_groq(prompt: str, max_tokens: int = 2400) -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def _markdown_to_html(text: str) -> str:
    """極簡 MD→HTML：標題/段落/清單/粗體，夠 SEO 用。"""
    lines = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            lines.append("")
            continue
        if line.startswith("## "):
            lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("### "):
            lines.append(f"<h3>{line[4:]}</h3>")
        elif re.match(r"^\s*[-*]\s+", line):
            lines.append(f"<li>{re.sub(r'^\s*[-*]\s+', '', line)}</li>")
        elif line.startswith("```"):
            lines.append("<pre>")
        else:
            lines.append(f"<p>{line}</p>")
    html = "\n".join(lines)
    # 粗體 **text**
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # 換行相鄰 <li> 包進 <ul>
    html = re.sub(r"(<li>.*?</li>\n?)+", lambda m: f"<ul>\n{m.group(0)}</ul>", html, flags=re.S)
    return html


PUBLISHED_COUNT = None


def generate_seo_article(skip_existing: bool = True) -> dict | None:
    """產一篇長尾文章並寫入 seo_articles。回傳文章 dict 或 None。"""
    if not GROQ_API_KEY:
        return None
    global PUBLISHED_COUNT
    existing_slugs = {
        r["slug"] for r in fetch("SELECT slug FROM seo_articles")
    }
    unused = [t for t in SEO_TOPICS if _slugify(t) not in existing_slugs]
    if not unused:
        return None
    topic = unused[0]

    prompt = f"""你是資深維運工程師，寫繁體中文實戰文章。主題：《{topic}》。

要求：
- 開頭一句直接點題，不要廢話
- 內容要像「真的做過的人」，有具體做法、避坑、小撇步
- 全文 800~1200 字，分段、可加小標題
- 用 Markdown 格式（# 一級標題開頭、## 小節、可用 - 清單、**粗體**）
- 結尾一句給讀者的行動建議

只輸出文章正文。"""
    try:
        body = _call_groq(prompt)
    except Exception as e:
        logger.error(f"GROQ SEO article failed: {e}")
        return None
    if "<" not in body or len(body) < 200:
        return None

    title = body.splitlines()[0].lstrip("# ").strip()[:50] or topic
    slug = _slugify(title)
    if slug in existing_slugs:
        slug = f"{slug}-{int(__import__('time').time())}"
    html = _markdown_to_html(body)
    summary = html[:120].replace("<p>", "").replace("</p>", "") + "…"

    cid = execute(
        "INSERT INTO seo_articles (slug, title, category, summary, content_html, keyword) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [slug, title, "維運", summary, html, topic],
    )
    logger.info(f"SEO 文章已產出：「{title}」（id={cid}）")
    return fetch_one("SELECT * FROM seo_articles WHERE id=?", (cid,))


def auto_seo_daily(max_per_day: int = 1) -> dict:
    """scheduler 用：每天產 1 篇，網站全空時首篇立刻補。"""
    today = fetch(
        "SELECT COUNT(*) AS c FROM seo_articles WHERE date(created_at)=date('now')"
    )[0]["c"]
    total = fetch("SELECT COUNT(*) AS c FROM seo_articles")[0]["c"]
    if today >= max_per_day and total > 0:
        return {"ok": True, "skipped": True, "today": today}
    if total == 0 and today >= 1:
        return {"ok": True, "skipped": True, "today": today}
    art = generate_seo_article()
    return {"ok": True, "article": art}


def get_article(slug: str):
    return fetch_one("SELECT * FROM seo_articles WHERE slug=?", (slug,))


def list_articles(limit: int = 50):
    return fetch(
        "SELECT id, slug, title, category, summary, view_count, created_at "
        "FROM seo_articles ORDER BY id DESC LIMIT ?",
        (limit,),
    )


def build_sitemap_entries():
    """回傳 sitemap 需要的 <url> 片段，供 server 端動態組 sitemap。"""
    rows = fetch(
        "SELECT slug, updated_at FROM seo_articles ORDER BY id DESC"
    )
    return rows