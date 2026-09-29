"""OMNITEST CLI — run any combination of test modules against any target."""
from __future__ import annotations

import argparse
import importlib
import inspect
import random
import sys
import time

from .core.config import Target
from .core.gate import check as gate_check
from .core.reporter import ModuleReport, exit_code, render, export_json, export_csv, build_collage
from .modules.base import MODULE_REGISTRY

CANONICAL_ORDER = [
    "discover", "smoke", "e2e", "api", "value", "vuln", "games", "games-observe",
    "games-integrity", "tamper-verify", "human", "load", "login-storm",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="omnitest",
        description="Universal full-spectrum website testing platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python -m omnitest list-modules\n"
            "  python -m omnitest discover https://example.com --out omnitest/targets/new_target.py\n"
            "  python -m omnitest run --target omnitest.targets.gfg_win --modules smoke,api,value\n"
            "  python -m omnitest run --target omnitest.targets.gfg_win --modules e2e,human "
            "--users 6 --minutes 10\n"
            "  python -m omnitest run --target omnitest.targets.gfg_win --modules load "
            '--stages "60:100,120:1000" --processes 8 --i-am-authorized\n'
            "  python -m omnitest run --target omnitest.targets.gfg_win --modules login-storm "
            "--users 50000 --storm-hold 300 --i-am-authorized\n"
            "  python -m omnitest run --target omnitest.targets.wikipedia "
            "--modules smoke,e2e,value\n"
            "  python -m omnitest run --target omnitest.targets.gfg_win --modules games "
            "--game-wait 10 --game-observe 6 --collage\n"
            "  python -m omnitest run --target omnitest.targets.gfg_win --modules smoke "
            "--watch 3600 --watch-out omnitest_artifacts/watch\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-modules", help="show available modules")

    d = sub.add_parser("discover", help="crawl a URL and emit a starter target profile")
    d.add_argument("url")
    d.add_argument("--max-pages", type=int, default=120)
    d.add_argument("--out", default=None)
    _common_flags(d)

    r = sub.add_parser("run", help="run selected modules against a target profile")
    r.add_argument("--target", required=True,
                   help="dotted path(es) to module(s) exposing TARGET, comma-separated "
                        "for multi-domain runs (or .py file paths)")
    r.add_argument("--parallel", type=int, default=1,
                   help="how many targets to test concurrently (multi-target only)")
    r.add_argument("--modules", required=True,
                   help=f"comma list from: {','.join(CANONICAL_ORDER)}")
    r.add_argument("--base-url", default=None, help="override target base_url")
    r.add_argument("--seed-path", action="append", default=[], dest="seed_paths",
                   help="append/override extra seed routes (repeatable)")
    _common_flags(r)
    r.add_argument("--stages", default="30:20",
                   help='load stages "seconds:rps,seconds:rps"')
    r.add_argument("--processes", type=int, default=1)
    r.add_argument("--max-concurrent", type=int, default=20000)
    r.add_argument("--users", type=int, default=8, help="human-sim users / login-storm accounts")
    r.add_argument("--storm-users", type=int, default=None,
                   help="override account count for login-storm only (defaults to --users)")
    r.add_argument("--max-games", type=int, default=0,
                   help="games module: 0 = sweep ALL games in catalog")
    r.add_argument("--game-wait", type=float, default=12.0,
                   help="games module: max seconds to wait for provider iframe boot")
    r.add_argument("--game-observe", type=float, default=6.0,
                   help="games module: seconds watching live runtime (network/ws/console)")
    r.add_argument("--observe-repeats", type=int, default=2,
                   help="games-observe: open each game N times for stability test")
    r.add_argument("--observe-languages", default="en,zh_cn,zh_tw,ja,ko",
                   help="games-observe: comma-separated locales to probe (default en,zh_cn,zh_tw,ja,ko)")
    r.add_argument("--minutes", type=float, default=5.0)
    r.add_argument("--storm-hold", type=float, default=60.0,
                   help="login-storm session hold seconds")
    r.add_argument("--latency-budget-ms", type=float, default=1500.0)
    r.add_argument("--http2", dest="http2", action="store_true",
                   help="load engine: use HTTP/2 multiplexing (default HTTP/1.1; h2 "
                        "in httpx is error-prone under concurrency vs CloudFront)")
    r.add_argument("--scenario", default=None, choices=["browse", "raw", "api-mix", "login-storm"],
                   help="load engine scenario override (default: api-mix if endpoints else browse)")
    r.add_argument("--ttfb-budget-ms", type=float, default=3000.0)
    r.add_argument("--headless", dest="headless", action="store_true", default=True)
    r.add_argument("--no-headless", dest="headless", action="store_false")

    r.add_argument("--allow-prod-login-storm", action="store_true",
                   help="explicit site-owner consent to run login-storm against production")
    r.add_argument("--export", default="json,csv",
                   help="comma-separated export formats: json, csv (default: json,csv)")
    r.add_argument("--no-export", action="store_true",
                   help="disable automatic JSON/CSV export")
    r.add_argument("--collage", action="store_true", default=True,
                   help="auto-generate games screenshot collage PNG (default: on)")
    r.add_argument("--no-collage", action="store_true",
                   help="skip games screenshot collage generation")
    r.add_argument("--watch", type=float, default=0,
                   help="re-run full suite every N seconds (0 = disabled)")
    r.add_argument("--watch-out", default=None,
                   help="directory for watch-mode log files (default: omnitest_artifacts/watch)")
    return p


def _common_flags(sp):
    sp.add_argument("--timeout", type=float, default=15.0)
    sp.add_argument("--max-rps", type=float, default=15.0,
                    help="politeness cap for light modules")
    sp.add_argument("--artifacts", default="omnitest_artifacts")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.add_argument("--i-am-authorized", action="store_true",
                    help="confirm signed authorization is in place (heavy modules)")


def load_target(spec: str) -> Target:
    """Accept dotted module path or filesystem .py path exposing TARGET."""
    import importlib

    if spec.endswith(".py"):
        import importlib.util
        mod_spec = importlib.util.spec_from_file_location("omni_target_file", spec)
        mod = importlib.util.module_from_spec(mod_spec)
        sys.path.insert(0, ".")
        mod_spec.loader.exec_module(mod)  # type: ignore[union-attr]
    else:
        mod = importlib.import_module(spec)
    target = getattr(mod, "TARGET", None)
    if not isinstance(target, Target):
        raise SystemExit(f"'{spec}' does not expose TARGET = Target(...)")
    return target


def make_discover_target(url: str) -> Target:
    from .core.util import clamp_host_url

    return Target(name="discover_adhoc", base_url=clamp_host_url(url), seed_paths=["/"])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_registry()

    from rich.console import Console
    console = Console(highlight=False)

    if args.cmd == "list-modules":
        from rich.table import Table
        t = Table(title="OMNITEST modules", header_style="bold cyan")
        t.add_column("Module")
        t.add_column("Heavy")
        t.add_column("Browser")
        t.add_column("Description", ratio=3)
        for name in CANONICAL_ORDER:
            spec = MODULE_REGISTRY[name]
            t.add_row(name, "yes" if spec.heavy else "", "yes" if spec.needs_browser else "", spec.help)
        console.print(t)
        return 0

    rng = random.Random(time.time_ns())
    reports: list[ModuleReport] = []
    options: dict = {}

    if args.cmd == "discover":
        targets = [make_discover_target(args.url)]
        chosen = ["discover"]
        options = {"max_pages": args.max_pages, "out": args.out, "max_rps": args.max_rps}
    else:
        specs = [s.strip() for s in args.target.split(",") if s.strip()]
        targets = [load_target(s) for s in specs]
        for target in targets:
            if getattr(args, "base_url", None):
                target.base_url = args.base_url
            if getattr(args, "seed_paths", None):
                for sp_ in args.seed_paths:
                    if sp_ not in target.seed_paths:
                        target.seed_paths.append(sp_)
        requested = [m.strip() for m in args.modules.split(",") if m.strip()]
        unknown = [m for m in requested if m not in MODULE_REGISTRY]
        if unknown:
            raise SystemExit(f"unknown modules: {unknown}; valid: {CANONICAL_ORDER}")
        chosen = sorted(set(requested), key=CANONICAL_ORDER.index)
        options = {
            "max_rps": args.max_rps, "timeout": args.timeout,
            "verbose": args.verbose, "artifacts": args.artifacts,
            "stages": args.stages, "processes": args.processes,
            "max_concurrent": args.max_concurrent, "users": args.users,
            "minutes": args.minutes, "storm_hold": args.storm_hold,
            "headless": args.headless, "latency_budget_ms": args.latency_budget_ms,
            "ttfb_budget": args.ttfb_budget_ms,
            "http2": getattr(args, "http2", False),
            "scenario": getattr(args, "scenario", None),
            "storm_users": getattr(args, "storm_users", None) or args.users,
            "max_games": getattr(args, "max_games", 0),
            "game_wait": getattr(args, "game_wait", 12.0),
            "game_observe": getattr(args, "game_observe", 6.0),
            "observe_repeats": getattr(args, "observe_repeats", 2),
            "observe_languages": getattr(args, "observe_languages", "en,zh_cn,zh_tw,ja,ko"),
        }

    multi = len(targets) > 1
    if multi:
        console.rule(f"[bold]OMNITEST → {len(targets)} targets × [{','.join(chosen)}] "
                     f"(parallel={getattr(args, 'parallel', 1)})")
    else:
        console.rule(f"[bold]OMNITEST → {targets[0].name} ({targets[0].base_url})")

    def pipeline(target) -> list[ModuleReport]:
        t_reports: list[ModuleReport] = []
        prefix = f"{target.name}:" if multi else ""
        for name in chosen:
            rep = ModuleReport(module=f"{prefix}{name}")
            try:
                gate_check(name, target,
                           authorized_flag=getattr(args, "i_am_authorized", False),
                           allow_prod_storm=getattr(args, "allow_prod_login_storm", False))
            except PermissionError as e:
                rep.add("gate", "FAIL", detail=str(e))
                t_reports.append(rep)
                continue
            t_reports.append(rep)
            ctx = _ctx(target, options, rep, console, rng)
            console.print(f"[bold cyan]▶[/] [bold]{target.name}[/] running [bold]{name}[/] …")
            fn = _load_module_fn(name)
            try:
                if inspect.iscoroutinefunction(fn):
                    import asyncio
                    asyncio.run(fn(ctx))
                else:
                    fn(ctx)
            except Exception as e:
                rep.add("module-crash", "FAIL", detail=f"{type(e).__name__}: {e}")
        return t_reports

    parallel = int(getattr(args, "parallel", 1) or 1)
    if parallel > 1 and len(targets) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(parallel, len(targets))) as pool:
            for t_reports in pool.map(pipeline, targets):
                reports.extend(t_reports)
    else:
        for target in targets:
            reports.extend(pipeline(target))

    render(reports, console, verbose=getattr(args, "verbose", False))

    # --- export + collage hooks ---
    art_dir = getattr(args, "artifacts", "omnitest_artifacts")
    if not getattr(args, "no_export", False):
        export_fmts = [f.strip() for f in getattr(args, "export", "json,csv").split(",") if f.strip()]
        if "json" in export_fmts:
            p_ = export_json(reports, f"{art_dir}/results.json")
            console.print(f"  exported: [underline]{p_}[/]")
        if "csv" in export_fmts:
            p_ = export_csv(reports, f"{art_dir}/results.csv")
            console.print(f"  exported: [underline]{p_}[/]")
    if getattr(args, "collage", False) and not getattr(args, "no_collage", False):
        games_found = any(r.module.endswith("games") or "games" in r.module for r in reports)
        if games_found:
            collage_out = f"{art_dir}/games_collage.png"
            try:
                p_ = build_collage(art_dir, collage_out)
                if p_:
                    console.print(f"  collage:  [underline]{p_}[/]")
            except Exception as e:
                console.print(f"  [yellow]collage skipped: {e}[/]")

    # --- watch mode ---
    watch_sec = getattr(args, "watch", 0) or 0
    if watch_sec > 0:
        import os, time as _time
        watch_dir = getattr(args, "watch_out", None) or f"{art_dir}/watch"
        os.makedirs(watch_dir, exist_ok=True)
        console.print(f"[bold yellow]⏳ watch mode: re-running every {watch_sec:.0f}s → {watch_dir}/[/]")
        cycle = 0
        while True:
            cycle += 1
            console.rule(f"[bold]WATCH CYCLE {cycle} — {_time.strftime('%H:%M:%S')}[/]")
            reports.clear()
            multi = len(targets) > 1
            if parallel > 1 and len(targets) > 1:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=min(parallel, len(targets))) as pool:
                    for t_reports in pool.map(pipeline, targets):
                        reports.extend(t_reports)
            else:
                for target in targets:
                    reports.extend(pipeline(target))
            render(reports, console, verbose=getattr(args, "verbose", False))
            ts = _time.strftime("%Y%m%d_%H%M%S")
            export_json(reports, f"{watch_dir}/results_{ts}.json")
            export_csv(reports, f"{watch_dir}/results_{ts}.csv")
            console.print(f"[dim]next run in {watch_sec:.0f}s … (Ctrl+C to stop)[/]")
            try:
                _time.sleep(watch_sec)
            except KeyboardInterrupt:
                console.print("[bold]watch stopped.[/]")
                break

    code = exit_code(reports)
    console.print(f"exit={code}")
    return code


def _ctx(target, options, rep, console, rng):
    from .modules.base import ModuleContext

    return ModuleContext(target=target, options=options, reporter=rep,
                         console=console, rng=rng)


mapping = {
    "discover": ("omnitest.modules.discover", "run"),
    "smoke": ("omnitest.modules.smoke", "run"),
    "api": ("omnitest.modules.api_test", "run"),
    "value": ("omnitest.modules.value_test", "run"),
    "vuln": ("omnitest.modules.vuln_scan", "run"),
    "games": ("omnitest.modules.games_sweep", "run"),
    "games-observe": ("omnitest.modules.games_observe", "run"),
    "games-integrity": ("omnitest.modules.games_integrity", "run"),
    "tamper-verify": ("omnitest.modules.tamper_verify", "run"),
    "load": ("omnitest.modules.load_test", "run_sync"),
    "login-storm": ("omnitest.modules.load_test", "run_login_storm"),
    "e2e": ("omnitest.modules.e2e_ui", "run"),
    "human": ("omnitest.modules.human_sim", "run"),
}


def ensure_registry() -> None:
    """Trigger decorator registration so list-modules shows everything."""
    for mod_name, _ in mapping.values():
        importlib.import_module(mod_name)


def _load_module_fn(name: str):
    mod_name, fn_name = mapping[name]
    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)


if __name__ == "__main__":
    raise SystemExit(main())
