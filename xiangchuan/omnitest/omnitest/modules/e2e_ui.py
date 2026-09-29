"""e2e — real-browser page validation (Selenium): rendering, console errors,
broken images, dead links. SPA hash-route aware.
"""
from __future__ import annotations

import re
import time

from .base import ModuleContext, register


def _make_driver(headless: bool = True):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
    return webdriver.Chrome(options=opts)


def _wait_dom_quiet(driver, timeout: float = 12.0, quiet_ms: float = 700.0) -> None:
    driver.execute_script(
        "window.__omniMut = 0;"
        "new MutationObserver(m => { window.__omniMut++; window.__omniLast = Date.now(); })"
        ".observe(document.documentElement, {childList:true, subtree:true, attributes:true});"
        "window.__omniLast = Date.now();"
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        last = driver.execute_script("return window.__omniLast || 0")
        if time.time() * 1000 - last > quiet_ms:
            return
        time.sleep(0.15)


@register("e2e", needs_browser=True,
          help="Browser-render every route: console errors, broken assets, dead links")
def run(ctx: ModuleContext):
    rep = ctx.reporter
    target = ctx.target
    base = target.base_url.rstrip("/")
    allow = [re.compile(p, re.I) for p in target.console_error_allowlist]
    art_dir = ctx.options.get("artifacts", "omnitest_artifacts")
    import os
    os.makedirs(art_dir, exist_ok=True)

    driver = _make_driver()
    try:
        for route in target.seed_paths:
            url = base + route
            try:
                driver.get(url)
                _wait_dom_quiet(driver)
                time.sleep(1.0)
            except Exception as e:
                rep.add(f"render {route}", "FAIL", detail=f"{type(e).__name__}: {e}")
                continue

            # console errors
            severe = []
            try:
                for entry in driver.get_log("browser"):
                    if entry.get("level") == "SEVERE":
                        msg = entry.get("message", "")
                        if not any(a.search(msg) for a in allow):
                            severe.append(msg[:200])
            except Exception:
                pass
            rep.add(f"console {route}", "FAIL" if severe else "PASS",
                    detail=("; ".join(severe[:3]) if severe else "clean"))

            # broken images
            broken = driver.execute_script(
                "return [...document.images]"
                ".filter(i => i.src && (!i.complete || i.naturalWidth === 0))"
                ".map(i => i.src.slice(0,120))")
            rep.add(f"images {route}", "FAIL" if broken else "PASS",
                    detail=(f"{len(broken)} broken :: {broken[0]}" if broken else "ok"))
            rep.metric(f"img.{route}", len(broken))

            # dead internal links (in-page HEAD fetch, capped)
            dead = driver.execute_script(
                """const out=[];
                  const anchors=[...document.querySelectorAll('a[href]')].slice(0,40);
                  const base=location.origin;
                  for(const a of anchors){
                    const h=a.getAttribute('href')||'';
                    if(!h || h.startsWith('#')) continue;
                    try{
                      const u=new URL(h, location.href);
                      if(u.origin!==base) continue;
                      if(u.protocol.startsWith('http')){
                        out.push(u.href);
                      }
                    }catch(e){}
                  }
                  return [...new Set(out)].slice(0,25);""")
            checked = driver.execute_script(
                """const urls=arguments[0];
                   return Promise.all(urls.map(u=>fetch(u,{method:'HEAD',mode:'same-origin'})
                     .then(r=>[u,r.status]).catch(e=>[u,-1])));""", dead) if dead else []
            bad = [(u, s) for u, s in checked if s not in (200, 204, 301, 302, 304)]
            rep.add(f"links {route}", "FAIL" if bad else ("WARN" if len(dead)==0 else "PASS"),
                    detail=(f"{len(bad)} dead :: {bad[:2]}" if bad else f"{len(checked)} checked"))

            # title sanity
            title = (driver.title or "").strip()
            rep.add(f"title {route}", "PASS" if title else "FAIL",
                    detail=title[:80] or "<empty>")

        # screenshot final state of first route as artifact sample
        try:
            driver.get(base + (target.seed_paths[0] if target.seed_paths else "/"))
            _wait_dom_quiet(driver, 8)
            shot = f"{art_dir}/e2e_sample_{int(time.time())}.png"
            driver.save_screenshot(shot)
            rep.artifacts.append(shot)
        except Exception:
            pass
    finally:
        driver.quit()
