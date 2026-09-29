"""games-observe — enhanced per-game observation for gfg.win.

Extends the base `games` sweep with four watch capabilities:
  1. Multi-language  : re-query detail/url API in several locales
                        (en/zh_cn/zh_tw/ja/ko) and verify they respond.
  2. Extended runtime : longer real-time window; count WebSocket frames and
                        per-provider-host request split.
  3. Host grouping    : classify the play iframe's src host into known
                        provider buckets (web.ministga7z.com / stagegameweb /
                        n2stg / other / unknown).
  4. Repeat stability : open each game K times, catching intermittent
                        blank-screen / iframe-drop / boot failures.

Usage:
  python -m omnitest run --target omnitest.targets.gfg_win --modules games-observe \
      --game-wait 10 --game-observe 8 --observe-repeats 2
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import Counter

from .base import ModuleContext, register
from .games_sweep import _blank_ratio, _DEFAULT_SELECTOR


@register("games-observe", needs_browser=True, help=(
    "Enhanced per-game observation for gfg.win: multi-language API, extended "
    "WS/traffic watch, play-source host grouping, repeat-stability test"))
def run(ctx: ModuleContext):
    rep = ctx.reporter
    target = ctx.target
    opts = ctx.options
    max_games = int(opts.get("max_games", 0))
    iframe_wait = float(opts.get("game_wait", 12.0))
    observe_s = float(opts.get("game_observe", 8.0))
    repeats = int(opts.get("observe_repeats", opts.get("observe-repeats", 2)) or 2)
    languages = [l.strip() for l in
                 opts.get("observe_languages", opts.get("observe-languages",
                 "en,zh_cn,zh_tw,ja,ko")).split(",") if l.strip()]

    ep_list = next((e for e in target.endpoints if e.name == target.games_list_endpoint), None)
    ep_detail = next((e for e in target.endpoints if e.name == target.games_detail_endpoint), None)
    ep_url = next((e for e in target.endpoints if e.name == target.games_url_endpoint), None)
    if ep_list is None:
        rep.add("config", "FAIL",
                detail="games_list_endpoint not set; this observe run targets gfg.win")
        return

    play_type = target.games_play_type or "iframe"
    play_sel = target.games_play_selector or _DEFAULT_SELECTOR[play_type]
    lang_map = {"en": "en_us", "zh_cn": "zh_cn", "zh_tw": "zh_tw",
                "ja": "ja_jp", "ko": "ko_kr"}

    # ---------------- phase 1: catalog + per-game API (multi-lang) ----------------
    games: list[dict] = []
    from ..core.util import make_client, TokenBucket

    async def fetch_catalog() -> None:
        async with make_client(headers=dict(target.global_headers)) as client:
            r = await client.request(ep_list.method, target.api_url(ep_list),
                                     json=dict(ep_list.json_body or {}))
            data = r.json()
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list) or not rows:
                rep.add("catalog", "FAIL",
                        detail=f"no game list: HTTP {r.status_code} :: {(r.text or '')[:150]}")
                return
            for row in rows:
                gid = row.get("gameId")
                if gid is not None:
                    games.append({"id": int(gid),
                                  "name": str(row.get("gameName", ""))})
            rep.metric("catalog_size", len(games))

    asyncio.run(fetch_catalog())
    if not games:
        return
    if max_games > 0:
        games = games[:max_games]

    api_results: dict[int, dict] = {}

    async def api_phase() -> None:
        bucket = TokenBucket(8.0)
        sem = asyncio.Semaphore(4)
        async with make_client(headers=dict(target.global_headers), timeout=30) as client:

            async def one(g: dict) -> None:
                res = {"detail_ok": 0, "detail_bad": 0, "url_ok": 0, "url_bad": 0,
                       "url_ms": 0, "lang_results": []}
                async with sem:
                    for lang in (["en"] + languages) if languages else ["en"]:
                        await bucket.take()
                        if ep_detail is not None:
                            body = dict(ep_detail.json_body or {})
                            body.update({"language": lang_map.get(lang, lang),
                                         "gameId": g["id"]})
                            try:
                                r = await client.request(ep_detail.method,
                                                         target.api_url(ep_detail),
                                                         json=body,
                                                         headers=dict(ep_detail.headers))
                                j = r.json()
                                d = j.get("data") or {}
                                ok = (j.get("code") == 0 and d.get("gameName")
                                      and bool(d.get("gameDescription")))
                            except Exception:
                                ok = False
                            res["detail_ok" if ok else "detail_bad"] += 1
                            if lang != languages[0] and ep_detail:
                                res["lang_results"].append(f"{lang}:{'ok' if ok else 'X'}")
                        await bucket.take()
                        if ep_url is not None:
                            body = dict(ep_url.json_body or {})
                            body.update({"language": lang_map.get(lang, lang),
                                         "gameId": g["id"],
                                         "account": target.games_account})
                            t0 = time.perf_counter()
                            try:
                                r = await client.request(ep_url.method, target.api_url(ep_url),
                                                         json=body,
                                                         headers=dict(ep_url.headers))
                                j = r.json()
                                u = ((j.get("data") or {}).get("url")) or ""
                                ok = (j.get("code") == 0 and u.startswith("https://"))
                            except Exception:
                                ok = False
                            res["url_ok" if ok else "url_bad"] += 1
                            if lang == languages[0]:
                                res["url_ms"] = int((time.perf_counter() - t0) * 1000)
                api_results[g["id"]] = res

            await asyncio.gather(*(one(g) for g in games))

    asyncio.run(api_phase())

    # ---------------- phase 2: browser + repeat stability ----------------
    from .e2e_ui import _make_driver
    base = target.base_url.rstrip("/")
    allow = [re.compile(p, re.I) for p in target.console_error_allowlist]
    art_dir = opts.get("artifacts", "omnitest_artifacts")
    os.makedirs(f"{art_dir}/games", exist_ok=True)

    driver = _make_driver()
    ui: dict[int, dict] = {}
    host_counter: Counter = Counter()

    def drain_console():
        out = []
        try:
            for entry in driver.get_log("browser"):
                if entry.get("level") == "SEVERE":
                    msg = entry.get("message", "")
                    if not any(a.search(msg) for a in allow):
                        out.append(msg[:160])
        except Exception:
            pass
        return out

    def _wait_hash(route: str) -> None:
        deadline = time.time() + 15
        while time.time() < deadline:
            cur = driver.execute_script("return location.hash || ''")
            if cur == route:
                time.sleep(0.9)
                break
            time.sleep(0.2)

    def goto_hash(route: str, first: bool) -> list[str]:
        if first:
            driver.get(base + route)
        else:
            driver.execute_script(f"location.hash={route!r};")
        deadline = time.time() + 15
        while time.time() < deadline:
            cur = driver.execute_script("return location.hash || ''")
            if cur == route:
                time.sleep(0.9)
                break
            time.sleep(0.2)
        return drain_console()

    def detect_iframe() -> tuple[str, str]:
        js = (
            "const f=document.querySelector('" + play_sel + "');"
            "if(!f) return [null,''];"
            "const s=(f.getAttribute('src')||'');"
            "let host=''; try{host=new URL(s, location.href).host}catch(_e){}"
            "return ['ok', host];"
        )
        try:
            st = driver.execute_script(js)
        except Exception:
            return "", ""
        if st and st[0] == "ok":
            return "ok", st[1] or ""
        return "", ""

    def classify_host(host: str) -> str:
        if "ministga7z" in host:
            return "web.ministga7z"
        if "stagegameweb" in host:
            return "stagegameweb"
        if "n2stg" in host:
            return "n2stg"
        if not host:
            return "unknown"
        return "other"

    #     # cross-object reference so helper closures can access per-run state
    run_state = {"reqs": 0, "ws": 0, "host_pkt": Counter()}

    def observe_runtime(host: str, seconds: float) -> None:
        obs_end = time.perf_counter() + seconds
        while time.perf_counter() < obs_end:
            try:
                for entry in driver.get_log("performance"):
                    try:
                        m = json.loads(entry["message"])["message"]
                    except Exception:
                        continue
                    meth = m.get("method", "")
                    if meth == "Network.webSocketCreated":
                        run_state["ws"] += 1
                    elif meth == "Network.requestWillBeSent":
                        u = ((m.get("params") or {}).get("request") or {}).get("url", "")
                        run_state["reqs"] += 1
                        if host:
                            h = u.split("//")[-1].split("/")[0] if "//" in u else ""
                            if host.split(":")[0] in h:
                                run_state["host_pkt"][host.split(":")[0]] += 1
                    elif meth == "Network.webSocketFrameReceived":
                        run_state["ws"] += 1
            except Exception:
                pass
            time.sleep(0.5)

    try:
        first_nav = True
        total = len(games)
        for idx, g in enumerate(games, 1):
            gid, gname = g["id"], g["name"]
            ures = {"info": "ok", "play": "", "boot_ms": 0, "host": "",
                    "repeats": 0, "clean": 0, "issues": []}
            print(f"[games-observe] {idx}/{total} #{gid} {gname}", flush=True)

            # --- detail page ---
            errs = goto_hash(f"#/gameInfo/{gid}", first_nav)
            first_nav = False
            body_txt = driver.execute_script(
                "return (document.querySelector('.game-info, .detail, main, body')"
                "||{textContent:''}).textContent.slice(0,4000);") or ""
            name_ok = gname.lower().split("-")[0][:12] in body_txt.lower() if gname else True
            banner_broken = driver.execute_script(
                """const imgs=[...document.images].filter(i=>i.src&&(!i.complete||i.naturalWidth===0));
                   return imgs.length;""")
            if errs:
                ures["info"] = f"console:{len(errs)}"
            elif not name_ok:
                ures["info"] = "name-missing"
            elif banner_broken:
                ures["info"] = f"broken-img:{banner_broken}"

            # --- repeat stability on play page ---
            clean_reps = 0
            issues_seen: list[str] = []
            best_host = ""
            for rep_i in range(repeats):
                try:
                    driver.get_log("performance")
                except Exception:
                    pass
                # force a real reload: navigate to detail route first so the SPA
                # actually tears down and reboots the play iframe each time
                if rep_i == 0:
                    driver.get(f"{base}/#/game/{gid}")
                else:
                    driver.get(f"{base}/#/gameInfo/{gid}")
                    _wait_hash(f"#/gameInfo/{gid}")
                    driver.get(f"{base}/#/game/{gid}")
                _wait_hash(f"#/game/{gid}")
                t0 = time.perf_counter()
                booted = False
                host = ""
                while time.perf_counter() - t0 < iframe_wait:
                    st, h = detect_iframe()
                    if st == "ok":
                        booted = True
                        host = h
                        break
                    time.sleep(0.4)
                if not booted:
                    issues_seen.append(f"rep{rep_i+1}:boot-fail")
                    continue
                if rep_i == 0:
                    ures["boot_ms"] = int((time.perf_counter() - t0) * 1000)
                best_host = host
                # extended observation
                run_state["reqs"] = run_state["ws"] = 0
                run_state["host_pkt"].clear()
                observe_runtime(host, observe_s)
                errs_now = drain_console()

                shot = f"{art_dir}/games/{gid}.png"
                blank = -1.0
                try:
                    el = driver.find_element("css selector", ".game-view")
                    el.screenshot(shot)
                    blank = _blank_ratio(shot)
                except Exception:
                    pass

                if errs_now:
                    issues_seen.append(f"rep{rep_i+1}:console")
                elif blank > 0.985 and run_state["reqs"] <= 1 and run_state["ws"] == 0:
                    issues_seen.append(f"rep{rep_i+1}:blank")
                elif run_state["reqs"] == 0 and run_state["ws"] == 0:
                    issues_seen.append(f"rep{rep_i+1}:no-traffic")
                else:
                    clean_reps += 1

            ures["repeats"] = repeats
            ures["clean"] = clean_reps
            ures["host"] = best_host
            if best_host:
                host_counter[classify_host(best_host)] += 1
            if issues_seen:
                ures["issues"] = issues_seen

            # --- verdict ---
            a = api_results.get(gid, {})
            det = a.get("detail_bad", 0)
            url = a.get("url_bad", 0)
            probs = []
            if det > 0:
                probs.append(f"api-detail {det}/{len(languages)}bad")
            if url > 0:
                probs.append(f"api-url {url}/{len(languages)}bad")
            if ures["info"] != "ok":
                probs.append(ures["info"])
            stability_ok = ures["clean"] == repeats
            if not stability_ok:
                probs.append(f"unstable {ures['clean']}/{repeats}")

            overall = "PASS" if not probs else "WARN" if stability_ok else "FAIL"
            if not probs and stability_ok:
                overall = "PASS"
            elif det == 0 and url == 0 and ures["info"] == "ok" and not stability_ok:
                overall = "WARN" if ures['clean'] >= repeats - 1 else "FAIL"

            lang_str = "".join(a.get("lang_results", []))
            iss_str = ("," .join(ures.get("issues", [])) if ures.get("issues") else "stable")
            detail = (f"api{det},{url}bad | ui={ures['info']} "
                      f"boot={ures['boot_ms']}ms repeats={ures['clean']}/{repeats}"
                      f"[{iss_str}] {lang_str} host={ures['host'][:36]}")
            rep.add(f"game {gid} {gname}"[:60], overall, detail=detail)
            ui[gid] = ures
            if overall != "PASS":
                try:
                    driver.save_screenshot(f"{art_dir}/games/{gid}.png")
                except Exception:
                    pass
    finally:
        driver.quit()

    # ---------------- summary ----------------
    n_pass = sum(1 for g in games if _observe_verdict(g["id"], api_results, ui) == "PASS")
    n_warn = sum(1 for g in games if _observe_verdict(g["id"], api_results, ui) == "WARN")
    n_fail = len(games) - n_pass - n_warn
    rep.metric("games_tested", len(games))
    rep.metric("pass", n_pass)
    rep.metric("warn", n_warn)
    rep.metric("fail", n_fail)
    rep.metric("repeats", repeats)
    rep.metric("languages", len(languages))
    for k, v in sorted(host_counter.items()):
        rep.metric(f"host:{k}", v)
    fails = [g["id"] for g in games if _observe_verdict(g["id"], api_results, ui) == "FAIL"]
    rep.add("rollup", "PASS" if n_fail == 0 else ("WARN" if n_fail <= len(games) * .05 else "FAIL"),
            detail=(f"{n_fail} unstable / {n_warn} warn / {n_pass} pass; "
                    f"unstable ids: {fails[:20]}"))


def _observe_verdict(gid, api_results, ui) -> str:
    a = api_results.get(gid, {})
    u = ui.get(gid, {})
    if a.get("detail_bad", 0) > 0 or a.get("url_bad", 0) > 0:
        return "FAIL"
    if u.get("info", "ok") != "ok":
        return "WARN"
    clean = u.get("clean", 0)
    reps = u.get("repeats", 1)
    if clean == reps:
        return "PASS"
    return "WARN" if clean >= reps - 1 else "FAIL"
