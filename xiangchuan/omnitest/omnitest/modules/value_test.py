"""value — numeric & string boundary/equivalence fuzzing (數值測試).

For every scalar field in every endpoint body, inject boundary classes:
  ints: 0, -1, 2^31, 2^63, -2^63, 1e309 (inf), 0.1 float precision
  strings: empty / 10KB / unicode / SQL canary / format-string / JSON injection
Asserts graceful degradation: no 5xx, no stack trace, no SQL error leakage.
"""
from __future__ import annotations

import asyncio
import time

from .base import ModuleContext, register

INT_BOUNDARIES = [0, -1, 1, 2_147_483_647, -2_147_483_648,
                  9_223_372_036_854_775_807, -9_223_372_036_854_775_808]
FLOAT_BOUNDARIES = [0.0, -0.0, 0.1, 1e-308, 1.7976931348623157e308, 1e309, -1e309]
STR_BOUNDARIES = [
    "", "A" * 10_000, "🎰中文🚀", "Robert'); DROP TABLE Students;--",
    "' OR '1'='1", "{0}{1}", "{{7*7}}", "${jndi:ldap://x}", "../../etc/passwd",
    "\x00\x01\x02", '{"injected": true}',
]


def _scalar_cases(value):
    if isinstance(value, bool):
        return [("bool->int", 1), ("bool->str", "true")]
    if isinstance(value, int):
        return [(f"int={v}", v) for v in INT_BOUNDARIES] + [("int->float", FLOAT_BOUNDARIES[-2]), ("int->str", "999999999999999999999999")]
    if isinstance(value, float):
        return [(f"float={v!r}", v) for v in FLOAT_BOUNDARIES] + [("float->str", "nan"), ("float->int-str", "-0")]
    if isinstance(value, str):
        return [(f"str[{s[:12]!r}]", s) for s in STR_BOUNDARIES]
    return []


@register("value", help="Boundary-value + robustness fuzzing of endpoint payloads")
async def run(ctx: ModuleContext):
    from ..core.util import make_client, TokenBucket, is_trace, is_sql_error, percentile

    rep = ctx.reporter
    target = ctx.target
    bucket = TokenBucket(ctx.options.get("max_rps", 15))
    max_cases_per_field = int(ctx.options.get("max_cases_per_field", 10))
    latencies: list[float] = []
    injected = graceful = leaked = 0

    async with make_client(headers=dict(target.global_headers), timeout=25) as client:
        sem = asyncio.Semaphore(10)

        async def send(ep, body, label):
            nonlocal injected, graceful, leaked
            async with sem:
                await bucket.take()
                t0 = time.perf_counter()
                try:
                    r = await client.request(ep.method, target.api_url(ep),
                                             headers=dict(ep.headers), json=body)
                except Exception as e:
                    rep.add(label, "FAIL", detail=f"{type(e).__name__}: {e}")
                    return
                dt = time.perf_counter() - t0
            latencies.append(dt * 1000)
            injected += 1
            text = r.text or ""
            trace, sql = is_trace(text), is_sql_error(text)
            if r.status_code < 500 and not trace and not sql:
                graceful += 1
            else:
                leak_kind = "trace:" + trace if trace else ("sql:" + sql if sql else f"http {r.status_code}")
                leaked += 1
                rep.add(f"{ep.name}:{label}", "FAIL",
                        detail=f"leak [{leak_kind}] :: {text[:160]}".replace("\n", " "))
            rep.add(f"{ep.name}:{label}", "PASS", detail=f"{r.status_code} {dt * 1000:.0f}ms")

        for ep in target.endpoints:
            body = ep.json_body
            if not isinstance(body, dict) or not body:
                continue
            for field, value in list(body.items())[:6]:
                cases = _scalar_cases(value)[:max_cases_per_field]
                for cname, cval in cases:
                    mutated = dict(body)
                    mutated[field] = cval
                    await send(ep, mutated, f"{field}|{cname}")
            # structural mutations
            for label, sbody in (
                ("null-body", None), ("array-body", [body]),
                ("deep-nest", {"d": body}), ("extra-keys", {**body, "__omnitest__": {"x": [1] * 64}}),
            ):
                await send(ep, sbody, label)

    rep.metric("cases_injected", injected)
    rep.metric("graceful", graceful)
    rep.metric("leaks", leaked)
    if latencies:
        rep.metric("latency_p95_ms", percentile(latencies, .95))
    if injected:
        ratio = graceful / injected
        rep.add("graceful-handling-ratio", "PASS" if ratio >= .98 else ("WARN" if ratio >= .9 else "FAIL"),
                detail=f"{graceful}/{injected} = {ratio:.1%} handled without 5xx/trace/sql-leak")
