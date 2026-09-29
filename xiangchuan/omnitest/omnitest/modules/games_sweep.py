"""games — per-game full sweep (每一頁、每一個子遊戲頁面的運行狀況).

Phase 1 (async HTTP, rate-limited):
  for every game/product in the catalog:
    * detail endpoint returns required fields
    * url-issuance endpoint returns playable URL (if configured)
Phase 2 (real browser):
  for every game/product:
    * detail page renders, console clean, expected name in DOM
    * play page boots the player (iframe / video / canvas / native),
      runtime observation (traffic / websocket / odds / stream health),
      screenshot + blank-screen analysis

Per-game verdict = worst of (api-detail, api-url, info-ui, play-ui).

Configurable via Target fields:
  games_play_type      = "iframe" | "video" | "canvas" | "native"
  games_play_selector  = CSS selector for play area
  games_info_selector  = CSS selector for detail page content
  games_observation    = "traffic" | "ws" | "odds" | "stream" | "none"
  games_catalog_path   = dot-path to item list in API response
  games_id_field       = field name for item ID
  games_name_field     = field name for item display name
"""
from __future__ import annotations

import asyncio
import re
import time

from .base import ModuleContext, register


@register("games", needs_browser=True,
          help="Sweep every game/product: API data + detail page + play-page runtime "
               "(iframe/video/canvas/native boot, live traffic, WebSockets, console)")
def run(ctx: ModuleContext):
    rep = ctx.reporter
    target = ctx.target
    opts = ctx.options
    max_games = int(opts.get("max_games", 0))
    iframe_wait = float(opts.get("game_wait", 12.0))
    observe_s = float(opts.get("game_observe", 6.0))

    if not target.games_list_endpoint:
        rep.add("config", "FAIL",
                detail="Target.games_list_endpoint not set (add games_* fields to profile)")
        return

    ep_list = next((e for e in target.endpoints if e.name == target.games_list_endpoint), None)
    ep_detail = next((e for e in target.endpoints if e.name == target.games_detail_endpoint), None)
    ep_url = next((e for e in target.endpoints if e.name == target.games_url_endpoint), None)
    if ep_list is None:
        rep.add("config", "FAIL", detail=f"endpoint '{target.games_list_endpoint}' not found")
        return

    # --- configuration from target profile ---
    catalog_path = target.games_catalog_path or "data"
    id_field = target.games_id_field or "gameId"
    name_field = target.games_name_field or "gameName"
    play_type = target.games_play_type or "iframe"
    play_sel = target.games_play_selector or _DEFAULT_SELECTOR[play_type]
    info_sel = target.games_info_selector or ".game-info, .detail, main, body"
    obs_mode = target.games_observation or "traffic"
    detail_extra = target.games_detail_extra_fields or []

    rep.metric("play_type", play_type)
    rep.metric("observation", obs_mode)

    # ==================== phase 1: API per-game checks ====================
    games: list[dict] = []
    from ..core.util import make_client, TokenBucket
    from ..core.config import dig as _dig

    async def fetch_catalog() -> None:
        async with make_client(headers=dict(target.global_headers)) as client:
            r = await client.request(ep_list.method, target.api_url(ep_list),
                                     json=dict(ep_list.json_body or {}))
            data = r.json()
            rows = _dig(data, catalog_path) if "." in catalog_path else data.get(catalog_path)
            if not isinstance(rows, list) or not rows:
                rep.add("catalog", "FAIL", detail=f"no item list via {ep_list.name}: "
                        f"HTTP {r.status_code} :: {(r.text or '')[:150]}")
                return
            for row in rows:
                gid = row.get(id_field)
                if gid is not None:
                    games.append({"id": int(gid) if str(gid).isdigit() else gid,
                                  "name": str(row.get(name_field, ""))})
            rep.metric("catalog_size", len(games))

    asyncio.run(fetch_catalog())
    if not games:
        return
    if max_games > 0:
        games = games[:max_games]

    api_results: dict = {}

    async def api_phase() -> None:
        bucket = TokenBucket(5.0)
        sem = asyncio.Semaphore(4)
        async with make_client(headers=dict(target.global_headers), timeout=30) as client:

            async def one(g: dict) -> None:
                res = {"detail": "", "url": "", "url_ms": 0}
                async with sem:
                    await bucket.take()
                    if ep_detail is not None:
                        body = dict(ep_detail.json_body or {})
                        body.update({id_field: g["id"]})
                        try:
                            r = await client.request(ep_detail.method, target.api_url(ep_detail),
                                                     json=body, headers=dict(ep_detail.headers))
                            j = r.json()
                            d = j.get("data") or j.get("result") or j
                            okd = j.get("code") in (0, 200, None)
                            # check required fields
                            for fld in ["gameName", "name", "title"] + detail_extra:
                                if fld in d and not d[fld]:
                                    okd = False
                            res["detail"] = "ok" if okd else f"incomplete(code={j.get('code')})"
                        except Exception as e:
                            res["detail"] = f"{type(e).__name__}"
                    await bucket.take()
                    if ep_url is not None:
                        body = dict(ep_url.json_body or {})
                        body.update({id_field: g["id"]})
                        if target.games_account:
                            body["account"] = target.games_account
                        t0 = time.perf_counter()
                        try:
                            r = await client.request(ep_url.method, target.api_url(ep_url),
                                                     json=body, headers=dict(ep_url.headers))
                            res["url_ms"] = int((time.perf_counter() - t0) * 1000)
                            j = r.json()
                            u = ""
                            d = j.get("data") or j.get("result") or {}
                            if isinstance(d, dict):
                                u = d.get("url") or d.get("playUrl") or d.get("streamUrl") or ""
                            res["url"] = ("ok" if (j.get("code") in (0, 200, None) and u)
                                          else f"no-url(code={j.get('code')})")
                        except Exception as e:
                            res["url"] = type(e).__name__
                api_results[g["id"]] = res

            await asyncio.gather(*(one(g) for g in games))

    asyncio.run(api_phase())

    # ==================== phase 2: browser sweep ====================
    from .e2e_ui import _make_driver
    base = target.base_url.rstrip("/")
    allow = [re.compile(p, re.I) for p in target.console_error_allowlist]
    art_dir = opts.get("artifacts", "omnitest_artifacts")
    import os
    os.makedirs(f"{art_dir}/games", exist_ok=True)

    driver = _make_driver()
    ui: dict = {}

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

    def goto_hash(route: str, first: bool) -> list[str]:
        url_needed = base + route
        if first:
            driver.get(url_needed)
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

    try:
        first_nav = True
        total = len(games)
        for idx, g in enumerate(games, 1):
            gid, gname = g["id"], g["name"]
            ures = {"info": "ok", "play": "", "boot_ms": 0}
            print(f"[games] {idx}/{total} #{gid} {gname}", flush=True)

            # --- detail page ---
            errs = goto_hash(f"#/gameInfo/{gid}", first_nav)
            first_nav = False
            body_txt = driver.execute_script(
                f"return (document.querySelector('{info_sel}')||{{textContent:''}})"
                ".textContent.slice(0,4000);") or ""
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

            # --- play page ---
            try:
                driver.get_log("performance")
            except Exception:
                pass
            errs = goto_hash(f"#/game/{gid}", False)
            t0 = time.perf_counter()
            player_ok, src_host, empty_state = False, "", False

            # --- player boot detection (varies by play_type) ---
            while time.perf_counter() - t0 < iframe_wait:
                boot = _detect_boot(driver, play_type, play_sel, base)
                state = boot.get("state", "")
                if state == "empty":
                    empty_state = True
                    break
                if state == "ok":
                    player_ok = True
                    src_host = boot.get("host", "")
                    ures["boot_ms"] = int((time.perf_counter() - t0) * 1000)
                    break
                time.sleep(0.4)

            # --- live runtime observation ---
            reqs = ws = game_reqs = 0
            stream_state = ""
            odds_changes = 0
            if player_ok and obs_mode != "none":
                obs_end = time.perf_counter() + observe_s
                last_odds = ""
                while time.perf_counter() < obs_end:
                    try:
                        for entry in driver.get_log("performance"):
                            try:
                                import json as _json
                                m = _json.loads(entry["message"])["message"]
                            except Exception:
                                continue
                            meth = m.get("method", "")
                            if meth == "Network.webSocketCreated":
                                ws += 1
                            elif meth == "Network.requestWillBeSent":
                                u = ((m.get("params") or {}).get("request") or {}).get("url", "")
                                reqs += 1
                                if src_host and src_host.split(":")[0] in u:
                                    game_reqs += 1
                            elif meth == "Network.responseReceived":
                                u = ((m.get("params") or {}).get("response") or {}).get("url", "")
                                if "odds" in u.lower() or "price" in u.lower():
                                    odds_changes += 1
                    except Exception:
                        pass
                    # video stream health check
                    if play_type == "video" and obs_mode == "stream":
                        stream_state = _check_video_stream(driver, play_sel)
                    time.sleep(0.5)
                errs += drain_console()

                if play_type == "iframe":
                    still = driver.execute_script(
                        f"const f=document.querySelector('{play_sel}');return !!f;")
                elif play_type == "video":
                    still = driver.execute_script(
                        f"const v=document.querySelector('{play_sel}');"
                        "return v && !v.paused && v.readyState >= 2;")
                else:
                    still = True

                ures["runtime"] = f"req={reqs}(game:{game_reqs}) ws={ws}"
                if obs_mode == "odds":
                    ures["runtime"] += f" odds-changes={odds_changes}"
                if stream_state:
                    ures["runtime"] += f" stream={stream_state}"
            else:
                still = True

            # --- visual proof: screenshot + blank-screen analysis ---
            shot_path = f"{art_dir}/games/{gid}.png"
            blank = -1.0
            screenshot_el = play_sel if play_type != "iframe" else ".game-view"
            if player_ok:
                try:
                    el = driver.find_element("css selector", screenshot_el)
                    el.screenshot(shot_path)
                    blank = _blank_ratio(shot_path)
                    ures["blank"] = f"{blank:.0%}" if blank >= 0 else "n/a"
                    if blank > 0.985 and reqs <= 1 and ws == 0:
                        ures["play"] = "blank-screen"
                    elif blank > 0.995 and ures["play"] == "":
                        ures["play"] = "blank-screen?"
                except Exception:
                    pass

            if empty_state:
                ures["play"] = "empty-state"
            elif not player_ok:
                ures["play"] = f"{play_type}-timeout"
            elif player_ok and not still:
                ures["play"] = f"{play_type}-died"
            elif reqs == 0 and ws == 0 and obs_mode == "traffic":
                ures["play"] = "no-runtime-traffic"
            if errs and ures["play"] == "":
                ures["play"] = f"console:{len(errs)}"

            # --- verdict ---
            a = api_results.get(gid, {})
            problems = [p for p in (
                a.get("detail") if a.get("detail") not in ("ok", "") else "",
                a.get("url") if a.get("url") not in ("ok", "") else "",
                ures["info"] if ures["info"] != "ok" else "",
                ures["play"],
            ) if p]
            overall = "PASS" if not problems else (
                "WARN" if all(p.startswith(("broken-img", "console:", "name-missing",
                                             "no-runtime-traffic", "blank-screen?"))
                              for p in problems) else "FAIL")
            detail = (f"api detail={a.get('detail','?')} url={a.get('url','?')}"
                      f"{a.get('url_ms', 0)}ms | ui info={ures['info']} "
                      f"play={ures['play'] or 'live'}{ures['boot_ms']}ms "
                      f"{ures.get('runtime', '')} blank={ures.get('blank', 'n/a')} "
                      f"host={src_host[:36]}")
            rep.add(f"game {gid} {gname}"[:60], overall, detail=detail)
            ui[gid] = ures
            if overall != "PASS":
                try:
                    driver.save_screenshot(f"{art_dir}/games/{gid}.png")
                except Exception:
                    pass
    finally:
        driver.quit()

    # ==================== summary ====================
    n_pass = sum(1 for g in games if _verdict(g["id"], api_results, ui) == "PASS")
    n_warn = sum(1 for g in games if _verdict(g["id"], api_results, ui) == "WARN")
    n_fail = len(games) - n_pass - n_warn
    rep.metric("games_tested", len(games))
    rep.metric("pass", n_pass)
    rep.metric("warn", n_warn)
    rep.metric("fail", n_fail)
    fails = [g["id"] for g in games if _verdict(g["id"], api_results, ui) == "FAIL"]
    rep.add("rollup", "PASS" if n_fail == 0 else ("WARN" if n_fail <= len(games) * .05 else "FAIL"),
            detail=(f"{n_pass}/{len(games)} fully healthy"
                    + (f"; failing ids: {fails[:20]}" if fails else "")))


# ==================== player boot detection ====================

_DEFAULT_SELECTOR = {
    "iframe": ".game-view iframe",
    "video": "video",
    "canvas": "canvas",
    "native": "main, .content, .game-container",
}


def _detect_boot(driver, play_type: str, selector: str, base: str) -> dict:
    """Detect player boot based on play_type. Returns {state, host}."""
    if play_type == "iframe":
        return _detect_iframe(driver, selector)
    elif play_type == "video":
        return _detect_video(driver, selector)
    elif play_type == "canvas":
        return _detect_canvas(driver, selector)
    else:  # native
        return _detect_native(driver, selector)


def _detect_iframe(driver, selector: str) -> dict:
    try:
        js = (
            "const f=document.querySelector('" + selector + "');"
            "if(!f){const e=document.querySelector('.game-empty');"
            "  return e?['empty',0,'','']:[null,0,'',''];}"
            "let n=-1; try{n=f.contentWindow.length}catch(_e){}"
            "const s=(f.getAttribute('src')||'');"
            "let host=''; try{host=new URL(s, location.href).host}catch(_e){}"
            "return ['ok', n, host, ''];"
        )
        st = driver.execute_script(js)
        state, n, host, _ = st
        if state == "empty":
            return {"state": "empty"}
        if state == "ok" and n >= 0:
            return {"state": "ok", "host": host}
    except Exception:
        pass
    return {"state": ""}


def _detect_video(driver, selector: str) -> dict:
    try:
        js = (
            "const v=document.querySelector('" + selector + "');"
            "if(!v) return [null, ''];"
            "const src = v.src || v.currentSrc || '';"
            "let host=''; try{host=new URL(src, location.href).host}catch(_e){}"
            "const ready = v.readyState;"
            "return ready >= 2 ? ['ok', host] : ['loading', host];"
        )
        state, host = driver.execute_script(js)
        if state == "ok":
            return {"state": "ok", "host": host}
        if state == "loading":
            return {"state": "loading", "host": host}
    except Exception:
        pass
    return {"state": ""}


def _detect_canvas(driver, selector: str) -> dict:
    try:
        js = (
            "const c=document.querySelector('" + selector + "');"
            "if(!c) return [null, 0, 0];"
            "return ['ok', c.width, c.height];"
        )
        state, w, h = driver.execute_script(js)
        if state == "ok" and w > 0 and h > 0:
            return {"state": "ok", "host": f"canvas {w}x{h}"}
    except Exception:
        pass
    return {"state": ""}


def _detect_native(driver, selector: str) -> dict:
    try:
        js = (
            "const el=document.querySelector('" + selector + "');"
            "if(!el) return [null, ''];"
            "const txt = el.textContent || '';"
            "return txt.length > 50 ? ['ok', ''] : ['empty-content', ''];"
        )
        state, _ = driver.execute_script(js)
        if state == "ok":
            return {"state": "ok", "host": "native"}
    except Exception:
        pass
    return {"state": ""}


def _check_video_stream(driver, selector: str) -> str:
    """Check video stream health: playing / buffering / stalled."""
    try:
        js = (
            "const v=document.querySelector('" + selector + "');"
            "if(!v) return 'no-video';"
            "if(v.error) return 'error';"
            "if(v.paused) return 'paused';"
            "if(v.readyState < 3) return 'buffering';"
            "return 'playing';"
        )
        return driver.execute_script(js)
    except Exception:
        return "unknown"


def _blank_ratio(png_path: str) -> float:
    """Ratio of near-black+near-white pixels; ~1.0 means blank/stuck screen."""
    try:
        from PIL import Image
        im = Image.open(png_path).convert("L").resize((160, 90))
        px = list(im.getdata())
        dark = sum(1 for p in px if p < 16)
        light = sum(1 for p in px if p > 240)
        return (dark + light) / len(px)
    except Exception:
        return -1.0


def _verdict(gid, api_results, ui) -> str:
    a = api_results.get(gid, {})
    u = ui.get(gid, {})
    probs = []
    if a.get("detail") not in ("ok", ""):
        probs.append(a["detail"])
    if a.get("url") not in ("ok", ""):
        probs.append(a["url"])
    if u.get("info", "ok") != "ok":
        probs.append(u["info"])
    if u.get("play"):
        probs.append(u["play"])
    if not probs:
        return "PASS"
    soft = all(p.startswith(("broken-img", "console:", "name-missing",
                             "no-runtime-traffic", "blank-screen?"))
               for p in probs)
    return "WARN" if soft else "FAIL"


_LANG_MAP = {"cn": "zh_cn", "hk": "zh_tw", "kr": "ko_kr", "us": "en_us", "th": "th_th",
             "vn": "vi_vn", "hi": "en_in", "pt": "pt_pt", "es": "es_es",
             "ja": "ja_jp", "my": "my_mm", "ru": "ru_ru"}


def _lang(target) -> str:
    return _LANG_MAP.get((target.global_headers.get("language") or "us").lower(), "en_us")
