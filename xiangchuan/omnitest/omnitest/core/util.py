"""Shared helpers: async client factory, token bucket, quantiles, UA pool."""
from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Iterable

USER_AGENTS = [
    # desktop
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/127.0",
    # mobile
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36",
]

TRACE_MARKERS = (
    "Traceback (most recent call last)",
    "SQLSTATE",
    "ORA-",
    "MySQLSyntaxErrorException",
    "You have an error in your SQL syntax",
    "Warning: mysql_",
    "Unclosed quotation mark",
    "PSQLException",
    "System.Exception",
    "at java.",
    "NullPointerException",
    "stack trace",
    "<html><head><title>Error",
)

SQL_ERROR_HINTS = (
    "you have an error in your sql syntax",
    "warning: mysql",
    "unclosed quotation mark",
    "quoted string not properly terminated",
    "sqlstate",
    "ora-00933",
    "ora-01756",
    "psqlException",
    "sqlite3.operationalerror",
    "postgresql",
)


def pick_ua(rng: random.Random | None = None) -> str:
    rng = rng or random
    return rng.choice(USER_AGENTS)


def make_client(
    *,
    timeout: float = 20.0,
    max_connections: int = 2000,
    max_keepalive: int = 500,
    http2: bool = True,
    headers: dict | None = None,
):
    """Build an httpx.AsyncClient with production-grade pooling."""
    import httpx

    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive,
        keepalive_expiry=30.0,
    )
    timeout_cfg = httpx.Timeout(timeout, connect=min(timeout, 10.0))
    transport = httpx.AsyncHTTPTransport(
        limits=limits, http2=http2, retries=1,
    )
    base_headers = {
        "User-Agent": pick_ua(),
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
        **(headers or {}),
    }
    return httpx.AsyncClient(
        transport=transport, timeout=timeout_cfg, headers=base_headers, follow_redirects=True
    )


class TokenBucket:
    """Global politeness limiter shared across coroutines."""

    def __init__(self, rate_per_sec: float):
        self.rate = max(rate_per_sec, 0.001)
        self._capacity = max(rate_per_sec, 1.0)
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def take(self, n: float = 1.0) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(self._capacity, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                wait = (n - self._tokens) / self.rate
            await asyncio.sleep(wait)


def percentile(values: Iterable[float], q: float) -> float:
    data = sorted(values)
    if not data:
        return 0.0
    idx = min(len(data) - 1, max(0, math.ceil(q * len(data)) - 1))
    return data[idx]


def human_delay(rng: random.Random, lo: float = 2.0, hi: float = 12.0) -> float:
    """Roughly log-normal dwell times like real humans."""
    mu = math.log(max(lo * hi, 0.0001)) / 2
    sigma = math.log(max(hi / lo, 1.01)) / 2.5
    return max(lo * 0.4, min(hi * 1.6, rng.lognormvariate(mu, sigma)))


def jitter(rng: random.Random, base: float, spread_pct: float = 0.25) -> float:
    return base * (1 + rng.uniform(-spread_pct, spread_pct))


def is_trace(text: str) -> str | None:
    low = text[:4000].lower()
    for marker in TRACE_MARKERS:
        if marker.lower() in low:
            return marker
    return None


def is_sql_error(text: str) -> str | None:
    low = text[:4000].lower()
    for hint in SQL_ERROR_HINTS:
        if hint.lower() in low:
            return hint
    return None


def clamp_host_url(url: str) -> str:
    return url.rstrip("/")
