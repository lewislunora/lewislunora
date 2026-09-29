"""vuln — passive posture audit + light active probes (漏洞測試).

Passive: security headers, cookie flags, TLS, CORS wildcard, dir-listing,
         sensitive file exposure, cache headers on API.
Active (read-only canaries): reflected-XSS marker, error-based SQLi
         fingerprint, open-redirect probe, IDOR sequential-id heuristic.
No destructive payloads. Rate-limited. Gated by authorization.
"""
from __future__ import annotations

import asyncio
import re
import ssl
import time
from urllib.parse import urlsplit, urlencode

from .base import ModuleContext, register

SENSITIVE_PATHS = [
    ".env", ".git/config", ".git/HEAD", "backup.sql", "db.sql", "dump.sql",
    "config.php.bak", "wp-config.php.bak", ".DS_Store", "server-status",
    "actuator/env", "debug/vars", "admin/", "phpinfo.php",
]

SECURITY_HEADERS = {
    "strict-transport-security": ("HSTS missing", "WARN"),
    "content-security-policy": ("CSP missing (XSS risk ↑)", "WARN"),
    "x-content-type-options": ("X-Content-Type-Options missing", "WARN"),
    "x-frame-options": ("X-Frame-Options/CSP frame-ancestors missing (clickjack)", "WARN"),
    "referrer-policy": ("Referrer-Policy missing", "WARN"),
}

XSS_CANARY = "omni735<xssprobe>"
SQLI_PROBES = ["'", "1' OR '1'='1", "1 UNION SELECT NULL--"]
REDIRECT_PARAMS = ["next", "redirect", "returnUrl", "url", "continue", "goto"]


@register("vuln", heavy=True, help="Security posture audit + read-only probes")
async def run(ctx: ModuleContext):
    from ..core.util import make_client, TokenBucket, is_sql_error

    rep = ctx.reporter
    target = ctx.target
    base = target.base_url.rstrip("/")
    bucket = TokenBucket(ctx.options.get("max_rps", 8))
    split = urlsplit(base)
    host = split.hostname or ""

    async with make_client(headers=dict(target.global_headers), timeout=20) as client:

        # ---------- TLS ----------
        try:
            loop = asyncio.get_running_loop()
            ctx_ssl = ssl.create_default_context()

            def _tls():
                with ctx_ssl.wrap_socket(
                    __import__("socket").create_connection((host, 443), timeout=10),
                    server_hostname=host,
                ) as s:
                    cert = s.getpeercert()
                    proto = s.version() or "?"
                return cert, proto

            cert, proto = await loop.run_in_executor(None, _tls)
            not_after = cert.get("notAfter")
            days_left = 99999
            if not_after:
                exp = ssl.cert_time_to_seconds(not_after)
                days_left = int((exp - time.time()) // 86400)
            status = "FAIL" if days_left < 14 else ("WARN" if days_left < 30 else "PASS")
            rep.add("TLS certificate", status, detail=f"{proto}, expires in {days_left}d ({not_after})")
            if proto == "TLSv1":
                rep.add("TLS version", "FAIL", detail="TLSv1 is deprecated")
        except Exception as e:
            rep.add("TLS", "WARN", detail=f"no TLS/443 or check failed: {e}")

        # ---------- headers on main page ----------
        r = await client.get(base)
        low_headers = {k.lower(): v for k, v in r.headers.items()}
        for hname, (desc, sev) in SECURITY_HEADERS.items():
            present = hname in low_headers or (
                hname == "x-frame-options" and "frame-ancestors" in low_headers.get("content-security-policy", "")
            )
            rep.add(f"header:{hname}", "PASS" if present else sev,
                    detail=(low_headers.get(hname, desc))[:120])
        cookies = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else []
        for c in cookies[:8]:
            flags = []
            cl = c.lower()
            for flag in ("secure", "httponly", "samesite"):
                if flag not in cl:
                    flags.append(flag)
            if flags:
                rep.add("cookie-flags", "WARN", detail=f"missing {','.join(flags)} :: {c.split(';')[0][:60]}")

        # ---------- CORS ----------
        cr = await client.get(base, headers={"Origin": "https://evil.example.com"})
        acao = cr.headers.get("access-control-allow-origin", "")
        if acao in ("*", "https://evil.example.com"):
            rep.add("cors", "FAIL", detail=f"reflects arbitrary origin: {acao}")
        elif acao:
            rep.add("cors", "PASS", detail=f"ACAO={acao}")
        else:
            rep.add("cors", "PASS", detail="no ACAO reflection")

        # ---------- sensitive files (GET only) ----------
        sem = asyncio.Semaphore(6)

        async def probe(path):
            async with sem:
                await bucket.take()
                try:
                    pr = await client.get(f"{base}/{path}")
                except Exception:
                    return
                if pr.status_code == 200 and len(pr.text or "") > 0:
                    text = pr.text[:200].lower()
                    boring = path in ("admin/",) and ("<html" in text or "<!doctype" in text)
                    if not boring:
                        rep.add(f"exposure:/{path}", "FAIL",
                                detail=f"HTTP 200 len={len(pr.text):,}")

        await asyncio.gather(*(probe(p) for p in SENSITIVE_PATHS))

        # ---------- directory listing ----------
        lr = await client.get(f"{base}/assets/")
        if lr.status_code == 200 and re.search(r"Index of /|<title>Directory listing", lr.text or "", re.I):
            rep.add("dir-listing:/assets/", "FAIL", detail="autoindex enabled")

        # ---------- reflected XSS canary on seed pages ----------
        for p in target.seed_paths[:6]:
            sep = "&" if "?" in p else "?"
            u = f"{base}{p}{sep}q={urlencode({'': XSS_CANARY})[1:]}"
            await bucket.take()
            xr = await client.get(u)
            if XSS_CANARY.replace("<", "&lt;") not in (xr.text or "") and XSS_CANARY in (xr.text or ""):
                rep.add(f"xss-reflection:{p}", "FAIL", detail="canary echoed unencoded")

        # ---------- error-based SQLi fingerprints on endpoints ----------
        for ep in target.endpoints:
            body = dict(ep.json_body or {})
            if not body:
                continue
            first_key = next(iter(body))
            for probe_val in SQLI_PROBES:
                mbody = dict(body)
                orig = mbody[first_key]
                mbody[first_key] = probe_val if isinstance(orig, str) else orig
                await bucket.take()
                sr = await client.request(ep.method, target.api_url(ep), json=mbody,
                                          headers=dict(ep.headers))
                text = (sr.text or "")[:3000]
                hint = is_sql_error(text)
                if hint:
                    rep.add(f"sqli-fingerprint:{ep.name}", "FAIL",
                            detail=f"[{hint}] with payload {probe_val!r}")
            rep.add(f"sqli-probe:{ep.name}", "PASS", detail="no DB error leakage")

        # ---------- open redirect heuristics ----------
        for p in target.seed_paths[:4]:
            for rp in REDIRECT_PARAMS:
                u = f"{base}{p}{'&' if '?' in p else '?'}{rp}=https://evil.example.com"
                await bucket.take()
                rr = await client.get(u, follow_redirects=False)
                loc = rr.headers.get("location", "")
                if rr.status_code in (301, 302, 303, 307) and "evil.example.com" in loc:
                    rep.add(f"open-redirect:{p}:{rp}", "FAIL", detail=f"Location={loc}")

    rep.add("scope-notice", "WARN",
            detail="OMNITEST vuln module performs light checks only; pair with full "
                   "authenticated pentest per signed scope for compliance-grade assessment.")
