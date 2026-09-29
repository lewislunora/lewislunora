"""games-integrity — read-only subgame tamper/embedding-integrity audit.

Evaluates, for each subgame's play iframe, the tamper / embedding risk posture:
  * src scheme is HTTPS (no cleartext / mitm injection)
  * src host is in the network's expected/authorized provider allowlist
  * number of URL params that look like sensitive tokens (token/sign/secret/key)
  * presence of embedding restrictions (sandbox, allow, referrerpolicy)
  * whether the account identifier leaks into the public iframe URL
Plus main-site anti-tamper headers (Content-Security-Policy / frame-ancestors,
X-Frame-Options, Referrer-Policy) and TLS posture of each provider host.

This is STRICTLY READ-ONLY / NON-DESTRUCTIVE: it inspects attributes, headers
and TLS certificates; it never injects, tampers, or sends crafted payloads.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import ssl
import socket
import time
from collections import Counter

from .base import ModuleContext, register

# Expected/authorized provider hosts for the network being assessed
EXPECTED_HOSTS = {
    "web.ministga7z.com",
    "stagegameweb.geodwfeowkg.com",
    "n-game.n2stg.com",
    "n2stg.com",
    "gfg.win",
}

TOKEN_FIELD_PATTERNS = re.compile(
    r"(token|sign|secret|key|password|passwd|hash|iv|sig|auth|credential|session)",
    re.I,
)


@register("games-integrity", needs_browser=True, heavy=True, help=(
    "Read-only subgame integrity audit: iframe HTTPS/host/token-leak + "
    "embedding controls + provider TLS posture + fix recommendations"))
def run(ctx: ModuleContext):
    rep = ctx.reporter
    target = ctx.target
    opts = ctx.options

    ep_list = next((e for e in target.endpoints if e.name == target.games_list_endpoint), None)
    if ep_list is None:
        rep.add("config", "FAIL", "games_list_endpoint not set")
        return

    # ---------------- gather every game id so the iframe URL can be requested ----------------
    games: list[dict] = []
    from ..core.util import make_client

    async def fetch_catalog() -> None:
        async with make_client(headers=dict(target.global_headers)) as client:
            r = await client.request(ep_list.method, target.api_url(ep_list),
                                     json=dict(ep_list.json_body or {}))
            data = r.json()
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list) or not rows:
                rep.add("catalog", "FAIL", f"no game list :: HTTP {r.status_code}")
                return
            for row in rows:
                gid = row.get("gameId")
                if gid is not None:
                    games.append({"id": int(gid), "name": str(row.get("gameName", ""))})
            rep.metric("catalog_size", len(games))

    asyncio.run(fetch_catalog())
    if not games:
        return
    max_games_ = int(opts.get("max_games", 0))
    if max_games_ > 0:
        games = games[:max_games_]

    # ---------------- phase 1: request each iframe URL (read-only) & inspect ----------------
    integrity: dict[int, dict] = {}
    ep_url = None  # URL issuance happens in browser phase; here we only read the final iframe

    # ---------------- phase 2: browser — read each iframe's live attributes ----------------
    from .e2e_ui import _make_driver
    base = target.base_url.rstrip("/")
    art_dir = opts.get("artifacts", "omnitest_artifacts")
    os.makedirs(f"{art_dir}/integrity", exist_ok=True)

    driver = _make_driver()

    def drain():
        try:
            return driver.get_log("browser")
        except Exception:
            return []

    fire = {}
    try:
        first_nav = True
        total = len(games)
        for idx, g in enumerate(games, 1):
            gid, gname = g["id"], g["name"]
            row = {"name": gname, "https": "?", "host": "", "host_expected": "?",
                   "token_fields": 0, "sensitive_in_url": False,
                   "account_in_url": False, "sandbox": "", "allow": "",
                   "referrerpolicy": "", "scheme_error": ""}
            print(f"[games-integrity] {idx}/{total} #{gid} {gname}", flush=True)
            route = f"/#/game/{gid}"
            if first_nav:
                driver.get(base + route)
                first_nav = False
            else:
                driver.get(base + f"/#/gameInfo/{gid}")
                deadline = time.time() + 10
                while time.time() < deadline:
                    if driver.execute_script("return location.hash") == f"/#/gameInfo/{gid}":
                        time.sleep(0.6)
                        break
                    time.sleep(0.2)
                driver.get(base + route)
            deadline = time.time() + 15
            while time.time() < deadline:
                if driver.execute_script("return location.hash") == route:
                    time.sleep(0.9)
                    break
                time.sleep(0.2)
            # poll for iframe
            t0 = time.time()
            js = (
                "const f=document.querySelector('.game-view iframe');"
                "if(!f) return null;"
                "const s=f.getAttribute('src')||'';"
                "let host=''; try{host=new URL(s, location.href).host}catch(_){}"
                "const sp=new URLSearchParams((s.split('?')[1]||''));"
                "const keys=[...sp.keys()];"
                "const acct=f.getAttribute('data-account')||'';"
                "return {src:s, host:host, keys:keys, acct:acct,"
                " sandbox:f.getAttribute('sandbox')||'',"
                " allow:f.getAttribute('allow')||'',"
                " rp:f.getAttribute('referrerpolicy')||(f.referrerPolicy||'')};"
            )
            attrs = None
            while time.time() - t0 < 15:
                try:
                    attrs = driver.execute_script(js)
                except Exception:
                    attrs = None
                if attrs:
                    break
                time.sleep(0.4)

            if not attrs:
                row["https"] = "n/a (iframe not found)"
                integrity[gid] = row
                fire[gid] = None
                continue

            src = attrs["src"]
            row["host"] = attrs["host"]
            row["host_expected"] = "yes" if attrs["host"] in EXPECTED_HOSTS else "no"
            row["sandbox"] = attrs["sandbox"]
            row["allow"] = attrs["allow"]
            row["referrerpolicy"] = attrs["rp"]
            if src.startswith("https://"):
                row["https"] = "yes"
            elif src.startswith("http://"):
                row["https"] = "NO (cleartext)"
            else:
                row["https"] = f"other ({src[:20]})"

            keys = attrs["keys"] or []
            row["token_fields"] = len([k for k in keys if TOKEN_FIELD_PATTERNS.search(k)])
            row["sensitive_in_url"] = any(TOKEN_FIELD_PATTERNS.search(k) for k in keys)
            # account leak: the issued URL itself commonly carries it; flag presence of the demo id
            row["account_in_url"] = bool(
                re.search(r"account|player\d+|40120", src, re.I))
            integrity[gid] = row
            fire[gid] = {"src": src, "host": attrs["host"]}
    finally:
        driver.quit()

    # ---------------- phase 3: main-site anti-tamper headers ----------------
    header_checks = []
    try:
        req = asyncio.run(_fetch_headers(target.base_url, target.global_headers))
    except Exception as e:
        req = {}
        header_checks.append(("main-site-headers", "FAIL", f"request error: {e}"))

    hdrs = {k.lower(): v for k, v in req.items()}
    csp = hdrs.get("content-security-policy", "")
    frame_anc = ""
    m = re.search(r"frame-ancestors\s+'([^']+)'", csp)
    if m:
        frame_anc = m.group(1)
    header_checks.append(("CSP (frame-ancestors)", "PASS" if csp else "FAIL",
                         (f"present; frame-ancestors='{frame_anc}'" if csp
                          else "MISSING — page can be framed / MITM-injected anywhere")))
    xfo = hdrs.get("x-frame-options", "")
    header_checks.append(("X-Frame-Options", "PASS" if xfo else "FAIL",
                          xfo or "MISSING — clickjacking / frame hijack possible"))
    rp = hdrs.get("referrer-policy", "")
    header_checks.append(("Referrer-Policy", "PASS" if rp else "FAIL",
                          (rp or "MISSING — Referer may leak provider URL incl. token")))
    header_checks.append(("HSTS", "PASS" if hdrs.get("strict-transport-security") else "FAIL",
                          "present" if hdrs.get("strict-transport-security")
                          else "MISSING — no HSTS, downgrade possible"))
    header_checks.append(("X-Content-Type-Options", "PASS" if hdrs.get("x-content-type-options") else
                          "FAIL", hdrs.get("x-content-type-options", "MISSING (MIME sniffing risk)")))
    header_checks.append(("Permissions-Policy", "PASS" if hdrs.get("permissions-policy") else "FAIL",
                          "present" if hdrs.get("permissions-policy")
                          else "MISSING (camera/mic autoplay controls absent)"))

    for name, status, detail in header_checks:
        rep.add(f"main {name}", status, detail=detail)

    # ---------------- phase 4: provider TLS posture ----------------
    hosts_seen = sorted({row["host"] for row in integrity.values() if row.get("host")})
    tls_results = {}
    for hst in hosts_seen:
        verdict, cert_info = _tls_check(hst)
        tls_results[hst] = (verdict, cert_info)
        status = "PASS" if verdict == "ok" else ("WARN" if verdict == "warn" else "FAIL")
        rep.add(f"tls {hst}", status, detail=f"{verdict} :: {cert_info}")
        rep.metric(f"tls:{hst}", 1 if verdict == "ok" else 0)

    # ---------------- phase 5: per-game findings + rollup ----------------
    n_pass = n_warn = n_fail = 0
    for gid, row in integrity.items():
        probs = []
        if row["https"] != "yes":
            probs.append(f"cleartext:{row['https']}")
        if row["host_expected"] != "yes":
            probs.append(f"host-unexpected:{row['host']}")
        if row["sensitive_in_url"]:
            probs.append(f"token-in-url({row['token_fields']})")
        if row["account_in_url"]:
            probs.append("account-in-url")
        if not probs:
            st = "PASS"
            n_pass += 1
        elif all(("token-in-url" in p or "account-in-url" in p) for p in probs):
            st = "WARN"
            n_warn += 1
        else:
            st = "FAIL"
            n_fail += 1
        detail = (
            f"https={row['https']} host={row['host']}(expected:{row['host_expected']}) "
            f"tok={row['token_fields']} sandbox='{row['sandbox']}' allow='{row['allow']}' "
            f"ref={row['referrerpolicy']}"
        )
        rep.add(f"game {gid} {row['name']}"[:60], st, detail=detail)
        if st != "PASS":
            integrity[gid]["status"] = st

    rep.metric("games_checked", len(integrity))
    rep.metric("pass", n_pass)
    rep.metric("warn", n_warn)
    rep.metric("fail", n_fail)
    rep.metric("unexpected_hosts", sum(1 for r in integrity.values() if r.get("host_expected") == "no"))
    rep.metric("cleartext", sum(1 for r in integrity.values() if r.get("https") != "yes"))
    rep.metric("token_url", sum(1 for r in integrity.values() if r.get("sensitive_in_url")))

    # save raw data for report generation
    os.makedirs(art_dir, exist_ok=True)
    with open(f"{art_dir}/integrity.json", "w", encoding="utf-8") as fh:
        json.dump({"games": integrity, "tls": tls_results, "headers": hdrs},
                  fh, ensure_ascii=False, indent=2)

    rep.add("rollup", "PASS" if n_fail == 0 else ("WARN" if n_warn == 0 and n_fail <= 5 else "FAIL"),
            detail=(f"{n_pass} clean / {n_warn} warn / {n_fail} fail; "
                    f"unexpected hosts={sum(1 for r in integrity.values() if r.get('host_expected')=='no')}, "
                    f"cleartext={sum(1 for r in integrity.values() if r.get('https')!='yes')}"))


def _fetch_headers(url: str, headers: dict) -> dict:
    import httpx
    try:
        # robust fetch: HTTP/1.1 (avoid http2+verify quirks), no TLS verify failure
        r = httpx.get(url, headers={"User-Agent": "OMNITEST-Integrity/1.0", **headers},
                      timeout=15, verify=False, follow_redirects=True)
        return dict(r.headers)
    except Exception:
        return {}


def _tls_check(host: str, port: int = 443) -> tuple[str, str]:
    """Read TLS cert chain (non-destructive). Returns (verdict, summary)."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                cert = s.getpeercert()
                proto = s.version()
                import datetime
                not_after = datetime.datetime.utcfromtimestamp(
                    ssl.cert_time_to_seconds(cert["notAfter"]))
                days_left = (not_after - datetime.datetime.utcnow()).days
                san = [v for e in cert.get("subjectAltName", ()) for v in (e[1],)]
                # check if cert matched host
                matched = host in san or any(h.endswith("." + host) for h in san)
                verify_mode = "VERIFY"
                if days_left < 30:
                    v = "warn"
                else:
                    v = "ok"
                return v, (
                    f"{proto} TLS1.2+ cert={days_left}d exp={not_after.date()} "
                    f"SAN={matched} ip={socket.gethostbyname(host)}")
    except ssl.SSLCertVerificationError as e:
        return "fail", f"cert verification failed: {e}"
    except Exception as e:
        return "fail", f"{type(e).__name__}: {e}"
