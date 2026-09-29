"""smoke — full-page HTTP-level checks for every configured route (全面頁面測試).

SPA hash routes are validated by loading the shell + verifying the JS bundle
that renders them; DOM-level validation lives in the e2e module.
"""
from __future__ import annotations

import asyncio
import time

from .base import ModuleContext, register


@register("smoke", help="HTTP smoke test every seed route: status, latency, size, error pages")
async def run(ctx: ModuleContext):
    from ..core.util import make_client, TokenBucket, is_trace

    rep = ctx.reporter
    target = ctx.target
    bucket = TokenBucket(ctx.options.get("max_rps", 20))
    timeout_s = float(ctx.options.get("timeout", 15))
    ttfb_budget_ms = float(ctx.options.get("ttfb_budget", 3000))

    async with make_client(headers=dict(target.global_headers), timeout=timeout_s) as client:
        sem = asyncio.Semaphore(16)

        async def check(url: str, label: str) -> None:
            async with sem:
                await bucket.take()
                t0 = time.perf_counter()
                try:
                    r = await client.get(url)
                except Exception as e:
                    rep.add(label, "FAIL", detail=f"{type(e).__name__}: {e}")
                    return
                ms = (time.perf_counter() - t0) * 1000
                body = r.text or ""
                trace = is_trace(body)
                problems = []
                if r.status_code >= 500:
                    problems.append(f"HTTP {r.status_code}")
                elif r.status_code != 200:
                    problems.append(f"HTTP {r.status_code}")
                if ms > ttfb_budget_ms:
                    problems.append(f"TTFB {ms:.0f}ms > {ttfb_budget_ms:.0f}ms")
                if trace:
                    problems.append(f"trace:{trace}")
                if not body.strip():
                    problems.append("empty body")
                status = "FAIL" if any("HTTP 5" in p or p.startswith("trace") for p in problems) else (
                    "WARN" if problems else "PASS")
                rep.add(label, status,
                        detail=("; ".join(problems) if problems else f"{ms:.0f}ms {len(body):,}B"),
                        data={"status": r.status_code, "ms": round(ms)})
                rep.metric(f"bytes.{label}", len(body))

        tasks = []
        for p in target.seed_paths:
            http_path = p.split("#")[0] or "/"
            tasks.append(check(target.base_url.rstrip("/") + http_path, f"route {p}"))
        tasks.append(check(target.base_url.rstrip("/") + "/favicon.ico", "favicon"))
        await asyncio.gather(*tasks)
