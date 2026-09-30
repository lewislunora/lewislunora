#!/usr/bin/env python3
"""Lewislunora 平台 MCP Server。

透過標準 MCP 通訊協定，讓 AI 智能體（Claude Desktop / CLI / 自製 client）可以：
- 查詢平台健康狀態與內容快照
- 搜尋客服知識庫、看最新動態／小說／討論串
- 直接發佈一條動態到 feed

可用 transport：stdio（預設）或 sse（--transport sse --host 0.0.0.0 --port 8001）
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime, timedelta

from marketing_system.config import GROQ_API_KEY
from marketing_system.database import execute, fetch, fetch_one

APP_URL = os.environ.get("MCP_APP_URL", "http://platform-app:8742")

try:
    from fastmcp.server import FastMCP
except ImportError:  # fastmcp < 2.x
    from fastmcp import FastMCP

mcp = FastMCP("lewislunora-platform")


def _http_json(method: str, path: str, payload: dict | None = None, timeout: int = 15):
    url = f"{APP_URL.rstrip('/')}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


@mcp.tool()
def platform_health() -> dict:
    """回傳平台 API 健康狀態（來自應用服務 /api/status）。"""
    try:
        return _http_json("GET", "/api/status") | {"reachable": True}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


@mcp.tool()
def content_snapshot() -> dict:
    """回傳平台各內容表目前的筆數快照。"""
    def count(table: str) -> int:
        try:
            return fetch_one(f"SELECT COUNT(*) AS c FROM {table}")["c"]
        except Exception:
            return 0
    return {
        "feed_posts": count("feed_posts"),
        "seo_articles": count("seo_articles"),
        "novels": count("novels"),
        "novel_chapters": count("novel_chapters"),
        "community_threads": count("community_threads"),
        "kb_entries": count("kb_entries"),
        "users": count("users"),
    }


@mcp.tool()
def kb_search(query: str) -> dict:
    """在客服知識庫中搜尋與 query 相關的條目，回傳前 10 筆。"""
    rows = fetch(
        "SELECT id, keywords, answer, language FROM kb_entries "
        "WHERE keywords LIKE ? OR answer LIKE ? OR language LIKE ? LIMIT 10",
        [f"%{query}%", f"%{query}%", f"%{query}%"],
    )
    return {"query": query, "hits": [dict(r) for r in rows]}


@mcp.tool()
def feed_recent(limit: int = 5) -> dict:
    """回傳最近幾則平台動態（feed）。上限 20 筆。"""
    limit = max(1, min(int(limit), 20))
    rows = fetch(
        "SELECT id, author, content, post_type, created_at "
        "FROM feed_posts ORDER BY created_at DESC, id DESC LIMIT ?",
        [limit],
    )
    return {"items": [dict(r) for r in rows]}


@mcp.tool()
def novel_status() -> dict:
    """回傳連載小說清單與各書章節數。"""
    rows = fetch("SELECT id, title, summary, chapter_count, status FROM novels ORDER BY id")
    return {"novels": [dict(r) for r in rows]}


@mcp.tool()
def threads_recent(limit: int = 5) -> dict:
    """回傳最近幾則社群討論串。上限 20 筆。"""
    limit = max(1, min(int(limit), 20))
    rows = fetch(
        "SELECT id, title, author_name, created_at FROM community_threads "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        [limit],
    )
    return {"items": [dict(r) for r in rows]}


@mcp.tool()
def daily_report() -> dict:
    """回傳今天（UTC）平台自動產出的內容量。"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    def today_count(table: str, col: str = "created_at") -> int:
        try:
            return fetch_one(f"SELECT COUNT(*) AS c FROM {table} WHERE substr({col},1,10)=?", [today])["c"]
        except Exception:
            return 0
    return {
        "date": today,
        "feed_today": today_count("feed_posts"),
        "seo_today": today_count("seo_articles"),
        "chapters_today": today_count("novel_chapters"),
        "threads_today": today_count("community_threads"),
        "groq_configured": bool(GROQ_API_KEY),
    }


@mcp.tool()
def publish_feed(content: str, author: str = "MCP") -> dict:
    """發佈一則平台動態（feed）。content 必填，最多 2000 字。"""
    content = content.strip()
    if not content:
        return {"ok": False, "error": "content 不能為空"}
    try:
        resp = _http_json("POST", "/api/feed", {"content": content, "author": author, "post_type": "ai"})
        return {"ok": True, "post": resp.get("post")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run()