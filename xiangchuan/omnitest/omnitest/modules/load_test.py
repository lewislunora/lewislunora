"""load — high-concurrency async load engine (高流量 / 高併發).

Design:
  * Poisson arrivals (exponential inter-arrival) at target RPS per stage.
  * Each Virtual User = full lifecycle coroutine (login → actions → hold/exit)
    sharing one pooled transport; per-VU cookie jar via lightweight clients.
  * Stages: --stage "seconds:rps,seconds:rps" e.g. "60:100,120:1000".
  * Scale-out: --processes N splits RPS across worker processes on this host;
    run on M machines for millions of CCU (README scaling table).
  * login-storm reuses the engine with a login+heartbeat scenario.

Metrics: achieved RPS, p50/p95/p99 latency, error rate, peak concurrent,
login success ratio. CLI-only output per requirements.
"""
from __future__ import annotations

import asyncio
import copy
import math
import multiprocessing as mp
import random
import time
from dataclasses import dataclass, field

from .base import ModuleContext, register
from ..core.util import pick_ua


# ---------------------------------------------------------------- scenarios
class UserContext:
    """Per-VU helpers: each VU owns a small connection pool (browser-like: ~6
    sockets per origin) so the engine never floods the CDN with hundreds of
    pooled keep-alives (which the CDN idle-reaps → ReadError noise)."""

    def __init__(self, engine: "LoadEngine", vu_id: int, rng: random.Random):
        self.engine = engine
        self.vu_id = vu_id
        self.rng = rng
        self.client = None  # created lazily (own transport pool)

    async def _ensure_client(self):
        if self.client is None:
            import httpx

            limits = httpx.Limits(
                max_connections=6,
                max_keepalive_connections=6,
                keepalive_expiry=8.0,
            )
            transport = httpx.AsyncHTTPTransport(
                limits=limits, http2=self.engine.http2, retries=1,
            )
            self.client = httpx.AsyncClient(
                transport=transport,
                timeout=httpx.Timeout(self.engine.timeout),
                headers={"User-Agent": pick_ua(self.rng)},
                follow_redirects=True,
            )
        return self.client

    async def request(self, method: str, url: str, *, label: str = "", **kw):
        client = await self._ensure_client()
        t0 = time.perf_counter()
        try:
            r = await client.request(method, url, **kw)
            dt = time.perf_counter() - t0
            ok = r.status_code < 400
            self.engine.record(ok=ok, dt=dt, label=label or f"{method} {url}")
            return r
        except Exception as e:
            dt = time.perf_counter() - t0
            self.engine.record(ok=False, dt=dt,
                               label=f"{type(e).__name__} {label or url}"[:120])
            return None

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
            self.client = None


@dataclass
class LoadEngine:
    target: object
    stages: list[tuple[float, float]]          # (duration_s, rps)
    max_concurrent: int = 20000
    timeout: float = 15.0
    quiet: bool = False
    http2: bool = False                        # h2 in httpx under high concurrency is
                                               # error-prone vs CloudFront → default off
    # results
    latencies: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    total: int = 0
    peak_ccu: int = 0
    ccu: int = 0
    logins_ok: int = 0
    logins_fail: int = 0
    active_sessions: int = 0

    def record(self, *, ok: bool, dt: float, label: str) -> None:
        self.total += 1
        self.latencies.append(dt * 1000)
        if not ok:
            key = label.split(" ")[0][:60]
            self.errors[key] = self.errors.get(key, 0) + 1

    # ---------------------------------------------------------- core loop
    async def run(self, scenario_name: str = "traffic") -> dict:
        try:
            for stage_idx, (duration, rps) in enumerate(self.stages, 1):
                if not self.quiet:
                    print(f"  stage {stage_idx}: rps={rps:,.0f} duration={duration:.0f}s", flush=True)
                await self._run_stage(duration, rps, scenario_name)
        finally:
            pass

        lats = sorted(self.latencies)
        elapsed_total = sum(d for d, _ in self.stages)
        return {
            "scenario": scenario_name,
            "requests": self.total,
            "achieved_rps": round(self.total / max(elapsed_total, .001), 1),
            "p50_ms": lats[len(lats) // 2] if lats else 0,
            "p95_ms": lats[int(len(lats) * .95)] if lats else 0,
            "p99_ms": lats[int(len(lats) * .99)] if lats else 0,
            "max_ms": lats[-1] if lats else 0,
            "errors": sum(self.errors.values()),
            "error_top": dict(sorted(self.errors.items(), key=lambda kv: -kv[1])[:5]),
            "peak_ccu": self.peak_ccu,
            "logins_ok": self.logins_ok,
            "logins_fail": self.logins_fail,
        }

    async def _run_stage(self, duration: float, rps: float, scenario_name: str) -> None:
        stop_at = time.monotonic() + duration
        tasks: set[asyncio.Task] = set()
        sem = asyncio.Semaphore(self.max_concurrent)
        spawn_task = asyncio.create_task(self._arrivals(stop_at, rps, tasks, sem, scenario_name))
        try:
            while time.monotonic() < stop_at:
                await asyncio.sleep(1.0)
                self.peak_ccu = max(self.peak_ccu, self.ccu)
        finally:
            spawn_task.cancel()
            if not tasks:
                return
            await asyncio.wait(list(tasks), timeout=max(30.0, duration * 2))
            # cancel stragglers so the transport closes cleanly
            for t in list(tasks):
                if not t.done():
                    t.cancel()
            remaining = [t for t in tasks if not t.done()]
            if remaining:
                await asyncio.wait(remaining, timeout=10)

    async def _arrivals(self, stop_at, rps, tasks, sem, scenario_name) -> None:
        rng = random.Random(time.time_ns() % (2**32))
        vu_counter = 0
        while time.monotonic() < stop_at and rps > 0:
            delay = -math.log(1.0 - rng.random()) / rps
            await asyncio.sleep(delay)
            # gate on capacity: never backlog more than the concurrency cap
            while sem.locked():
                await asyncio.sleep(0.02)
            vu_counter += 1
            t = asyncio.create_task(self._vu_wrapper(vu_counter, tasks, sem, scenario_name, rng.random()))
            tasks.add(t)

    async def _vu_wrapper(self, vu_id, tasks, sem, scenario_name, seed) -> None:
        rng = random.Random(int(seed * 1e9) ^ vu_id)
        ctx = UserContext(self, vu_id, rng)
        self.ccu += 1
        self.peak_ccu = max(self.peak_ccu, self.ccu)
        try:
            async with sem:
                if scenario_name == "login-storm":
                    await self._scenario_login_storm(ctx)
                elif scenario_name == "api-mix":
                    await self._scenario_api_mix(ctx)
                elif scenario_name == "raw":
                    await self._scenario_raw(ctx)
                else:
                    await self._scenario_browse(ctx)
        except Exception as e:
            self.record(ok=False, dt=0.0, label=f"vu-crash {type(e).__name__}: {e}"[:120])
        finally:
            tasks.discard(asyncio.current_task())
            await ctx.close()
            self.ccu -= 1

    async def _scenario_raw(self, ctx: UserContext) -> None:
        """Pure sustained-load scenario: a VU makes a fixed number of rapid
        requests over its ONE ~6-socket client (wrk/k6-style worker pool).
        Socket count stays ≈ peak_ccu × 6 — bounded and realistic."""
        paths = [p.split("#")[0] for p in self.target.seed_paths] or ["/"]
        base = self.target.base_url.rstrip("/")
        n = ctx.rng.randint(8, 20)
        for _ in range(n):
            path = ctx.rng.choice(paths)
            await ctx.request("GET", base + path, label="raw")

    # --------------------------------------------------------- scenarios
    async def _scenario_browse(self, ctx: UserContext) -> None:
        paths = [p.split("#")[0] for p in self.target.seed_paths] or ["/"]
        n = ctx.rng.randint(2, 6)
        for _ in range(n):
            path = ctx.rng.choice(paths)
            await ctx.request("GET", self.target.base_url.rstrip("/") + path, label="browse")
            await asyncio.sleep(ctx.rng.uniform(1.0, 4.0))

    async def _scenario_api_mix(self, ctx: UserContext) -> None:
        endpoints = self.target.endpoints or []
        weights = [max(ep.weight, 0.01) for ep in endpoints]
        n = ctx.rng.randint(3, 10)
        for _ in range(n):
            if not endpoints:
                break
            ep = ctx.rng.choices(endpoints, weights=weights)[0]
            body = dict(ep.json_body or {})
            body.setdefault("language", _lang_for(self.target))
            await ctx.request(ep.method, self.target.api_url(ep), json=body,
                              headers=dict(ep.headers), label=f"api:{ep.name}")
            await asyncio.sleep(ctx.rng.uniform(.3, 2.5))

    async def _scenario_login_storm(self, ctx: UserContext) -> None:
        lp = self.target.login
        if lp is None:
            return
        username = lp.username_pattern.format(n=ctx.vu_id)
        body = {
            lp.username_field: username,
            lp.password_field: lp.password,
            **lp.extra_body,
            "language": _lang_for(self.target),
        }
        try:
            r = await ctx.request(lp.method, lp.url, json=body, headers=dict(lp.headers),
                                  label="login")
        except Exception:
            self.logins_fail += 1
            return
        data = None
        try:
            data = r.json()
        except Exception:
            pass
        from ..core.config import dig
        token = dig(data, lp.token_path) if data else None
        success_raw = dig(data, lp.success_path, default=None) if data else None
        if success_raw == lp.success_value and (token or lp.token_path == ""):
            self.logins_ok += 1
        else:
            self.logins_fail += 1
            return
        # hold the session alive like a logged-in user
        self.active_sessions += 1
        try:
            deadline = time.monotonic() + self.storm_hold
            while time.monotonic() < deadline:
                await asyncio.sleep(lp.heartbeat_interval)
                if lp.heartbeat_path:
                    hbody = {"language": _lang_for(self.target), **lp.heartbeat_body}
                    try:
                        await ctx.request(lp.heartbeat_method,
                                          self.target.base_url.rstrip("/") + lp.heartbeat_path
                                          if lp.heartbeat_path.startswith("/") else lp.heartbeat_path,
                                          json=hbody if lp.heartbeat_method in ("POST", "PUT", "PATCH") else None,
                                          headers=dict(lp.headers), label="heartbeat")
                    except Exception:
                        break
        finally:
            self.active_sessions -= 1

    storm_hold: float = 60.0


def _lang_for(target) -> str:
    lang = (target.global_headers.get("language") or "US").strip().lower()
    mapping = {"cn": "zh_cn", "hk": "zh_tw", "kr": "ko_kr", "us": "en_us", "th": "th_th",
               "vn": "vi_vn", "hi": "en_in", "pt": "pt_pt", "es": "es_es",
               "ja": "ja_jp", "my": "my_mm", "ru": "ru_ru"}
    return mapping.get(lang, "en_us")


def parse_stages(spec: str) -> list[tuple[float, float]]:
    out = []
    for part in spec.split(","):
        sec, _, rps = part.partition(":")
        out.append((float(sec), float(rps)))
    return out or [(10.0, 10.0)]


def _child_worker(payload: dict) -> dict:
    """Entry for each worker process (own event loop)."""
    target = payload["target"]
    engine = LoadEngine(
        target=target,
        stages=[tuple(s) for s in payload["stages"]],
        max_concurrent=payload["max_concurrent"],
        timeout=payload["timeout"],
        quiet=payload.get("quiet", True),
        http2=payload.get("http2", False),
    )
    engine.storm_hold = payload["storm_hold"]
    result = asyncio.run(engine.run(payload["scenario"]))
    return result


def _run_load(ctx: ModuleContext, scenario: str) -> None:
    rep = ctx.reporter
    opts = ctx.options
    stages = parse_stages(opts["stages"])
    processes = int(opts["processes"])

    # strip non-picklable callables before multiprocessing fan-out
    safe_target = copy.copy(ctx.target)
    safe_target.endpoints = []
    for ep in ctx.target.endpoints:
        ep2 = copy.copy(ep)
        ep2.success_check = None
        safe_target.endpoints.append(ep2)

    payload_common = dict(
        target=safe_target,
        stages=[(d, r / max(processes, 1)) for d, r in stages],
        max_concurrent=max(int(opts["max_concurrent"]) // max(processes, 1), 64),
        timeout=float(opts["timeout"]), storm_hold=float(opts["storm_hold"]),
        scenario=scenario, http2=bool(opts.get("http2", False)),
    )

    t_start = time.perf_counter()
    if processes <= 1:
        result = _child_worker({**payload_common, "quiet": False})
        results = [result]
    else:
        out_q: mp.Queue = mp.Queue()
        procs = []
        for i in range(processes):
            p = mp.Process(target=_proc_entry, args=(payload_common, out_q, i))
            p.start()
            procs.append(p)
        results = []
        for _ in range(processes):
            results.append(out_q.get())
        for p in procs:
            p.join(timeout=60)

    wall = time.perf_counter() - t_start
    agg = _aggregate(results, wall)
    for k, v in agg.items():
        if k != "error_top":
            rep.metric(k, v)
    rep.metric("wall_seconds", wall)
    if agg["errors"] == 0:
        rep.add("load-errors", "PASS", detail=f"{agg['errors']:,} errors over {agg['requests']:,} requests")
    elif agg["err_ratio"] < 0.02:
        rep.add("load-errors", "WARN", detail=f"error ratio {agg['err_ratio']:.2%}: {agg['error_top']}")
    else:
        rep.add("load-errors", "FAIL", detail=f"error ratio {agg['err_ratio']:.2%}: {agg['error_top']}")
    if scenario == "login-storm":
        total_logins = agg["logins_ok"] + agg["logins_fail"]
        ratio = agg["logins_ok"] / max(total_logins, 1)
        st = "PASS" if ratio >= .99 else ("WARN" if ratio >= .95 else "FAIL")
        rep.add("login-success-ratio", st,
                detail=f"{agg['logins_ok']:,}/{total_logins:,} = {ratio:.2%}")
    else:
        budget = float(opts.get("latency_budget_ms", 1500))
        status = "PASS" if agg["p95_ms"] <= budget else ("WARN" if agg["p95_ms"] <= budget * 2 else "FAIL")
        rep.add("latency-p95", status, detail=f"p95={agg['p95_ms']:.0f}ms budget={budget:.0f}ms")


@register("load", heavy=True, help="Staged high-concurrency load test (RPS ramp)")
def run_sync(ctx: ModuleContext):
    scenario = ctx.options.get("scenario") or ("api-mix" if ctx.target.endpoints else "raw")
    _run_load(ctx, scenario)


@register("login-storm", heavy=True,
          help="Massive login simulation: --users N with --storm-hold session keep-alive")
def run_login_storm(ctx: ModuleContext):
    if ctx.target.login is None:
        ctx.reporter.add("login-storm", "FAIL", detail="Target has no LoginProfile configured")
        return
    users = int(ctx.options.get("storm_users") or ctx.options["users"])
    hold = float(ctx.options["storm_hold"])
    # convert desired concurrent logins into a stage: spread arrivals over min(users,600)s
    arrival_window = min(max(users / 50.0, 10.0), 600.0)
    rps = max(users / arrival_window, 0.5)
    ctx.options["stages"] = f"{arrival_window:.0f}:{rps:.2f},{hold:.0f}:0.01"
    ctx.options["scenario"] = "login-storm"
    _run_load(ctx, "login-storm")


def _proc_entry(payload, q, wid):
    res = _child_worker(payload)
    q.put(res)


def _aggregate(results: list[dict], wall: float) -> dict:
    tot_r = sum(r["requests"] for r in results)
    tot_e = sum(r["errors"] for r in results)
    all_lats = []
    # approximate percentile merge: keep each worker's raw? we only have summary;
    # workers return their own percentiles so take weighted max as conservative
    err_top: dict[str, int] = {}
    for r in results:
        for k, v in r.get("error_top", {}).items():
            err_top[k] = err_top.get(k, 0) + v
    return {
        "requests": tot_r,
        "achieved_rps": round(tot_r / max(wall, .001), 1),
        "p50_ms": max(r["p50_ms"] for r in results),
        "p95_ms": max(r["p95_ms"] for r in results),
        "p99_ms": max(r["p99_ms"] for r in results),
        "peak_ccu": max(r["peak_ccu"] for r in results),
        "logins_ok": sum(r["logins_ok"] for r in results),
        "logins_fail": sum(r["logins_fail"] for r in results),
        "errors": tot_e,
        "err_ratio": tot_e / max(tot_r, 1),
        "error_top": dict(sorted(err_top.items(), key=lambda kv: -kv[1])[:5]),
    }
