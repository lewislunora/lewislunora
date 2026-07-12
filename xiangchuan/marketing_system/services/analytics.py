"""
Simple self-hosted web analytics with IP geolocation.
Logs page views, referrers, user agents, and visitor countries.
"""
import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta

import requests as http

from ..database import execute, fetch, fetch_one

logger = logging.getLogger(__name__)

_geo_cache_lock = threading.Lock()
GEO_API = "http://ip-api.com/json/{ip}?fields=status,country,city"


def _geo_lookup(ip: str) -> dict:
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return {"country": "", "city": ""}
    cached = fetch_one("SELECT country, city FROM geo_cache WHERE ip=?", [ip])
    if cached:
        return {"country": cached["country"], "city": cached["city"]}
    try:
        resp = http.get(GEO_API.format(ip=ip), timeout=3)
        data = resp.json()
        if data.get("status") == "success":
            result = {"country": data.get("country", ""), "city": data.get("city", "")}
            with _geo_cache_lock:
                execute(
                    "INSERT OR REPLACE INTO geo_cache (ip, country, city) VALUES (?, ?, ?)",
                    [ip, result["country"], result["city"]],
                )
            return result
    except Exception as e:
        logger.debug(f"Geo lookup failed for {ip}: {e}")
    return {"country": "", "city": ""}


def track(page: str, referrer: str = "", user_agent: str = "", ip: str = ""):
    geo = _geo_lookup(ip)
    execute(
        "INSERT INTO page_views (page, referrer, user_agent, ip, country) VALUES (?, ?, ?, ?, ?)",
        [page, referrer[:500], user_agent[:500], ip, geo.get("country", "")],
    )


def track_async(page: str, referrer: str = "", user_agent: str = "", ip: str = ""):
    threading.Thread(
        target=track,
        args=[page, referrer, user_agent, ip],
        daemon=True,
    ).start()


def summary(since_hours: int = 24) -> dict:
    cutoff = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    total = fetch_one(
        "SELECT COUNT(*) as cnt FROM page_views WHERE visited_at >= ?", [cutoff]
    )
    total_all = fetch_one("SELECT COUNT(*) as cnt FROM page_views")
    by_page = fetch(
        "SELECT page, COUNT(*) as cnt FROM page_views "
        "WHERE visited_at >= ? GROUP BY page ORDER BY cnt DESC LIMIT 20",
        [cutoff],
    )
    by_country = fetch(
        "SELECT country, COUNT(*) as cnt FROM page_views "
        "WHERE visited_at >= ? AND country != '' "
        "GROUP BY country ORDER BY cnt DESC LIMIT 20",
        [cutoff],
    )
    by_ref = fetch(
        "SELECT referrer, COUNT(*) as cnt FROM page_views "
        "WHERE visited_at >= ? AND referrer != '' "
        "GROUP BY referrer ORDER BY cnt DESC LIMIT 10",
        [cutoff],
    )
    hourly = fetch(
        "SELECT substr(visited_at, 12, 2) as hr, COUNT(*) as cnt "
        "FROM page_views WHERE visited_at >= ? "
        "GROUP BY hr ORDER BY hr",
        [cutoff],
    )

    return {
        "total": total["cnt"] if total else 0,
        "total_all": total_all["cnt"] if total_all else 0,
        "since_hours": since_hours,
        "pages": [dict(r) for r in by_page],
        "countries": [dict(r) for r in by_country],
        "referrers": [dict(r) for r in by_ref],
        "hourly": [dict(r) for r in hourly],
    }
