"""human — realistic user behaviour simulation (模擬真人測試).

Each virtual user runs a bounded session in its own Chrome instance:
  * gaussian dwell times between actions (log-normal, 2–12s)
  * smooth scrolling with random depth/pauses
  * mouse jitter/hovers over visible elements
  * random-walk navigation across same-domain links (SPA-safe)
  * occasional typing into search/input fields with per-key cadence
    (form submission only when Target.human_sim_allow_submit)
"""
from __future__ import annotations

import random
import threading
import time

from .base import ModuleContext, register


@register("human", needs_browser=True,
          help="Behavioural human simulation sessions (N users x M minutes)")
def run(ctx: ModuleContext):
    rep = ctx.reporter
    target = ctx.target
    n_users = int(ctx.options["users"])
    minutes = float(ctx.options["minutes"])
    headless = bool(ctx.options.get("headless", True))
    art_dir = ctx.options.get("artifacts", "omnitest_artifacts")
    import os
    os.makedirs(art_dir, exist_ok=True)

    results: list[dict] = []
    lock = threading.Lock()

    def session(uid: int) -> None:
        from ..modules.e2e_ui import _make_driver, _wait_dom_quiet
        from ..core.util import human_delay
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys

        rng = random.Random(uid * 7919 + int(time.time()))
        stats = {"actions": 0, "navs": 0, "js_errors": 0, "dead_clicks": 0}
        driver = None
        try:
            driver = _make_driver(headless=headless)
            driver.set_window_size(rng.choice([1440, 1366, 1920]), rng.choice([900, 768, 1080]))
            base = target.base_url.rstrip("/")
            visited: set[str] = set()
            session_end = time.time() + minutes * 60
            driver.get(base + rng.choice(target.seed_paths or ["/"]))
            _wait_dom_quiet(driver)

            while time.time() < session_end:
                # dwell like reading
                time.sleep(min(human_delay(rng, 2.0, 12.0), max(0.1, session_end - time.time())))
                act = rng.random()
                if act < 0.45:
                    # scroll behaviour
                    depth = rng.randint(300, 1400)
                    driver.execute_script(
                        "window.scrollBy({top: arguments[0], behavior:'smooth'});", depth)
                    time.sleep(rng.uniform(.4, 1.6))
                    if rng.random() < .5:
                        driver.execute_script("window.scrollBy({top:-arguments[0],behavior:'smooth'});",
                                              rng.randint(150, 500))
                    stats["actions"] += 1
                elif act < 0.7:
                    # mouse wander / hover
                    try:
                        els = driver.find_elements(
                            "css selector",
                            "a[href], button, img, input, select")[:25]
                        if els:
                            el = rng.choice(els)
                            size = el.size
                            if size.get("width") and size.get("height"):
                                ActionChains(driver).move_to_element_with_offset(
                                    el, rng.randint(-8, 8), rng.randint(-4, 4)
                                ).pause(rng.uniform(.2, .9)).perform()
                        stats["actions"] += 1
                    except Exception:
                        stats["dead_clicks"] += 1
                elif act < 0.92:
                    # navigate within domain (SPA hash-safe)
                    hrefs = driver.execute_script(
                        """return [...document.querySelectorAll('a[href]')]
                             .map(a=>a.getAttribute('href'))
                             .filter(h=>h&&(h.startsWith('/')||h.startsWith('#')))
                             .slice(0,60);""")
                    candidates = [
                        base + ("/#" + h.lstrip("#")) if h.startswith("#") else base + h
                        for h in hrefs
                    ] or []
                    fresh = [c for c in candidates if c not in visited]
                    if fresh:
                        pick = rng.choice(fresh)
                        visited.add(pick)
                        try:
                            driver.get(pick)
                            _wait_dom_quiet(driver, 10, 600)
                            stats["navs"] += 1
                        except Exception:
                            stats["dead_clicks"] += 1
                    stats["actions"] += 1
                else:
                    # type into an input (search-like), submit only if allowed
                    try:
                        inputs = [i for i in driver.find_elements("css selector", "input[type='text'], input:not([type])")
                                  if i.is_displayed() and i.is_enabled()]
                        if inputs and target.human_sim_allow_submit or (inputs and rng.random() < .35):
                            el = rng.choice(inputs)
                            query = rng.choice(["slot", "poker", "abc", "123", "中文"])
                            el.clear()
                            for ch in query:
                                el.send_keys(ch)
                                time.sleep(rng.uniform(.05, .18))
                            if target.human_sim_allow_submit:
                                el.send_keys(Keys.ENTER)
                        stats["actions"] += 1
                    except Exception:
                        stats["dead_clicks"] += 1

            try:
                logs = driver.get_log("browser")
                stats["js_errors"] = sum(1 for e in logs if e.get("level") == "SEVERE")
            except Exception:
                pass
            if uid <= 2:
                shot = f"{art_dir}/human_u{uid}_{int(time.time())}.png"
                try:
                    driver.save_screenshot(shot)
                    rep.artifacts.append(shot)
                except Exception:
                    pass
        finally:
            if driver:
                driver.quit()
            with lock:
                results.append(stats)

    threads = [threading.Thread(target=session, args=(i,), daemon=True)
               for i in range(n_users)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0

    tot_actions = sum(s["actions"] for s in results)
    tot_navs = sum(s["navs"] for s in results)
    tot_js = sum(s["js_errors"] for s in results)
    tot_dead = sum(s["dead_clicks"] for s in results)
    rep.metric("users", n_users)
    rep.metric("wall_seconds", round(wall, 1))
    rep.metric("actions", tot_actions)
    rep.metric("navigations", tot_navs)
    rep.metric("failed_interactions", tot_dead)
    rep.metric("js_errors", tot_js)
    rep.add("human-session", "PASS" if tot_actions > 0 and tot_dead <= tot_actions // 2 else (
        "WARN" if tot_actions > 0 else "FAIL"),
        detail=f"{tot_actions} actions, {tot_navs} navs, {tot_dead} failed interactions, "
               f"{tot_js} JS errors across {n_users} users x {minutes}min")
