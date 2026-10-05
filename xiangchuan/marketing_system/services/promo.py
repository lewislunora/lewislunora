"""免費推廣工具組：把站內既有內容轉成可貼的宣傳素材。

- rss_items(): 產生 RSS 2.0（訂閱 + 被聚合器抓取）
- share_kit(): 為最新內容產生各平台的成稿貼文（含 UTM 追蹤連結）
- weekly_digest(): 每週一次的彙整貼文

設計原則：不依賴任何付費服務或平台 token，使用者複製貼上就能發；
需要全自動發佈時，再接 Telegram / Bluesky 等免費 API。
"""

import html
import re
from datetime import datetime, timedelta

from ..database import fetch, fetch_one

BASE_URL = "https://lewislunora.onrender.com"

PLATFORMS = [
    ("threads", "Threads / IG 貼文", 300),
    ("line", "LINE 社群", 300),
    ("facebook_group", "Facebook 社團 / 粉專", 500),
    ("x", "X（Twitter）", 250),
    ("discord", "Discord 社群", 400),
    ("dcard", "Dcard 看板", 500),
    ("xiaohongshu", "小紅書", 400),
    ("reddit", "Reddit", 400),
    ("hn", "Show HN / 技術社群", 250),
]


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _utm(path: str, source: str, campaign: str = "auto") -> str:
    sep = "&" if "?" in path else "?"
    return f"{BASE_URL}{path}{sep}utm_source={source}&utm_medium=social&utm_campaign={campaign}"


def latest_content(limit_each: int = 5) -> list:
    """攤平最新內容：SEO 文章、短文、小說章節。"""
    items = []
    for r in fetch(
        "SELECT slug, title, summary, created_at FROM seo_articles "
        "WHERE status='published' ORDER BY created_at DESC LIMIT ?",
        [limit_each],
    ):
        items.append({
            "kind": "article",
            "title": r["title"],
            "summary": r["summary"] or "",
            "url_path": f"/thoughts/{r['slug']}",
            "created_at": r["created_at"],
        })
    for r in fetch(
        "SELECT id, content, created_at FROM feed_posts WHERE post_type='short' "
        "ORDER BY created_at DESC LIMIT ?",
        [limit_each],
    ):
        items.append({
            "kind": "short",
            "title": _clip(r["content"], 40),
            "summary": r["content"],
            "url_path": "/thoughts/",
            "created_at": r["created_at"],
        })
    for r in fetch(
        "SELECT id, title, summary, chapter_count FROM novels WHERE status='serializing' "
        "ORDER BY chapter_count DESC LIMIT 2"
    ):
        items.append({
            "kind": "novel",
            "title": f"《{r['title']}》連載中（已 {r['chapter_count']} 章）",
            "summary": r["summary"] or "",
            "url_path": "/novels.html",
            "created_at": "",
        })
    items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return items


def share_kit(limit: int = 3) -> dict:
    """為最新 N 筆內容產生各平台成稿貼文。"""
    items = latest_content(limit_each=limit)
    kits = []
    for it in items[:limit]:
        body = _clip(it["summary"] or it["title"], 160)
        link_default = _utm(it["url_path"], "share_kit")
        posts = []
        for key, label, limit_chars in PLATFORMS:
            link = _utm(it["url_path"], key)
            if key in ("threads", "line", "x"):
                text = f"{body}\n\n{link}"
            elif key == "hn":
                text = f"{it['title']}｜翔川 Neo（繁中）\n{link}"
            elif key == "xiaohongshu":
                text = f"📌 {it['title']}\n\n{body}\n\n#AI自動化 #維運 #台灣工程 #效率工具\n{link}"
            elif key == "dcard":
                text = f"【心得分享】{it['title']}\n{body}\n\n想繼續看這類實戰：{link}"
            elif key == "reddit":
                text = f"{it['title']}\n\n{body}\n\n{link}"
            else:
                text = f"{it['title']}\n\n{body}\n\n👉 {link}"
            posts.append({
                "platform": key,
                "label": label,
                "chars": len(text),
                "within_limit": len(text) <= limit_chars,
                "text": text,
            })
        kits.append({
            "kind": it["kind"],
            "title": it["title"],
            "created_at": it["created_at"],
            "url": link_default,
            "posts": posts,
        })
    return {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "items": kits}


def weekly_digest() -> dict:
    """近 7 天內容彙整：一篇貼文講完這週產出。"""
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    posts = fetch(
        "SELECT content, created_at FROM feed_posts WHERE created_at >= ? ORDER BY created_at DESC LIMIT 20",
        [since],
    )
    articles = fetch(
        "SELECT slug, title, summary FROM seo_articles WHERE created_at >= ? ORDER BY created_at DESC LIMIT 10",
        [since],
    )
    kb = fetch_one("SELECT COUNT(*) AS c FROM kb_entries")["c"]
    chapters = fetch_one("SELECT COALESCE(SUM(chapter_count),0) AS c FROM novels")["c"]
    datasets = fetch_one("SELECT COUNT(*) AS c FROM gov_datasets WHERE status='ok'")["c"]
    lines = [f"📈 本週更新（{datetime.now().strftime('%m/%d')}）", ""]
    if articles:
        lines.append("📝 長文：")
        lines += [f"・{a['title']}" for a in articles[:5]]
        lines.append("")
    if posts:
        lines.append("✍️ 短文（最新 3 則）：")
        lines += [f"・{_clip(p['content'], 60)}" for p in posts[:3]]
        lines.append("")
    stats = f"小說累計 {chapters} 章｜客服知識庫 {kb} 筆"
    if datasets:
        stats += f"｜開放資料已分析 {datasets} 個資料集"
    lines += [stats, "", f"免費試用 → {_utm('/', 'digest')}"]
    return {"since": since, "stats": stats, "text": "\n".join(lines),
            "articles": len(articles), "posts": len(posts)}


def rss_xml(limit: int = 20) -> str:
    """RSS 2.0：供訂閱與外部聚合器抓取。"""
    items = latest_content(limit_each=limit)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>翔川 Neo｜AI 自動化與維運實戰</title>",
        f"<link>{BASE_URL}/</link>",
        f"<description>AI 自動化、網站維運、開放資料分析與每日連載——每天更新的繁中實戰內容。</description>",
        "<language>zh-TW</language>",
    ]
    for it in items:
        link = _utm(it["url_path"], "rss")
        desc = html.escape(_clip(it["summary"] or it["title"], 200))
        parts += [
            "<item>",
            f"<title>{html.escape(it['title'])}</title>",
            f"<link>{html.escape(link)}</link>",
            f"<guid isPermaLink=\"false\">{it['url_path']}-{it.get('created_at','')}</guid>",
            f"<description>{desc}</description>",
            "</item>",
        ]
    parts.append("</channel></rss>")
    return "\n".join(parts)