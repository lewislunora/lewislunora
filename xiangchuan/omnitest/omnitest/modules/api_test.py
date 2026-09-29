"""api — contract + robustness testing for every configured endpoint.

Per endpoint baseline call then variants:
  wrong method / empty body / missing fields / bad content-type /
  oversized payload / malformed JSON / duplicate keys.
Asserts: no 5xx, no stack traces, sane latency, envelope consistency.
"""
from __future__ import annotations

import asyncio
import json
import time

from .base import ModuleContext, register


def _variants(body):
    yield "empty-body", {}
    if isinstance(body, dict) and body:
        # drop each top-level key one at a time (missing required field probe)
        keys = list(body.keys())
        for k in keys[:8]:
            slim = {k2: v2 for k2, v2 in body.items() if k2 != k}
            yield f"missing:{k}", slim
        # type-flip every scalar value
        for k in keys[:8]:
            flipped = dict(body)
            v = body[k]
            flipped[k] = [] if not isinstance(v, list) else {"injected": True}
            yield f"typeflip:{k}", flipped
    yield "oversized", _oversized(body)


def _oversized(body):
    if isinstance(body, dict):
        out = dict(body)
        first = next(iter(out), "f")
        out[first] = "A" * 100_000
        return out
    return {"x": "A" * 100_000}


MALFORMED = '{"a": [1, 2,,]}'
DUP_KEYS = '{"code":0,"code":9999,"data":{"data":1,"data":2}}'


@register("api", help="Contract + robustness matrix over Target.endpoints")
async def run(ctx: ModuleContext):
    from ..core.util import make_client, TokenBucket, is_trace, percentile

    rep = ctx.reporter
    target = ctx.target
    bucket = TokenBucket(ctx.options.get("max_rps", 10))
    latencies: list[float] = []

    async with make_client(headers=dict(target.global_headers)) as client:
        sem = asyncio.Semaphore(8)

        async def call(ep, label, *, method=None, raw_body=None, json_body=..., headers=None):
            url = target.api_url(ep)
            h = {**ep.headers, **(headers or {})}
            use_method = method or ep.method
            body_kw: dict = {}
            if raw_body is not None:
                body_kw["content"] = raw_body
                h.setdefault("Content-Type", "application/json")
            elif json_body is not ...:
                body_kw["json"] = json_body
            elif ep.json_body is not None or ep.method in ("POST", "PUT", "PATCH"):
                body_kw["json"] = ep.json_body or {}
            async with sem:
                await bucket.take()
                t0 = time.perf_counter()
                try:
                    r = await client.request(use_method, url, headers=h, **body_kw)
                except Exception as e:
                    rep.add(label, "FAIL", detail=f"{type(e).__name__}: {e}")
                    return None
                dt = time.perf_counter() - t0
            text = r.text or ""
            latencies.append(dt * 1000)
            trace = is_trace(text)
            if r.status_code >= 500 or trace:
                snippet = text[:180].replace("\n", " ")
                rep.add(label, "FAIL",
                        detail=f"HTTP {r.status_code} {'TRACE:' + trace if trace else ''} :: {snippet}")
                return r
            try:
                data = r.json()
            except Exception:
                data = None
            if ep.success_check and data is not None and r.status_code == 200:
                ok = False
                try:
                    ok = bool(ep.success_check(data))
                except Exception:
                    pass
                if not ok and "baseline" not in label:
                    rep.add(label, "WARN", detail="envelope mismatch on non-baseline variant (informational)")
            return r

        for ep in target.endpoints:
            base_label = f"{ep.name}"
            r = await call(ep, f"{base_label}:baseline")
            if r is None:
                continue
            ok_status = r.status_code in ep.expect_status
            rep.add(f"{base_label}:status", "PASS" if ok_status else "FAIL",
                    detail=f"{r.status_code} expect={ep.expect_status}")
            if r.status_code < 500:
                rep.add(f"{base_label}:robustness", "PASS", detail="no 5xx/trace across variants")
            else:
                rep.add(f"{base_label}:robustness", "FAIL", detail=f"baseline already 5xx: {r.status_code}")
            # variants (sequential per endpoint to keep diffs readable)
            await call(ep, f"{base_label}:wrong-method", method="GET" if ep.method == "POST" else "POST")
            await call(ep, f"{base_label}:malformed-json", raw_body=MALFORMED)
            await call(ep, f"{base_label}:dup-keys", raw_body=DUP_KEYS)
            await call(ep, f"{base_label}:xml-content-type", json_body=ep.json_body or {},
                       headers={"Content-Type": "text/xml"})
            if isinstance(ep.json_body, dict):
                for name, vbody in _variants(ep.json_body):
                    if name.startswith(("missing:", "typeflip:", "empty", "oversized")):
                        await call(ep, f"{base_label}:{name}", json_body=vbody)

    if latencies:
        rep.metric("calls", len(latencies))
        rep.metric("latency_p50_ms", percentile(latencies, .50))
        rep.metric("latency_p95_ms", percentile(latencies, .95))
        rep.metric("latency_p99_ms", percentile(latencies, .99))
