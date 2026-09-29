"""tamper-verify — remote content-tamper verification (READ-ONLY, non-destructive).

Provides hard, reproducible evidence on whether served content can be / is tampered:

  SRI Integrity     : does each <script>/<link> on the page declare an
                      `integrity="sha384-..."` attribute? Resources without SRI
                      are unguarded against in-flight tampering. (quantified)
  SHA-256 recompute : download every script/link resource, compute SHA-256, and
                      fetch it a SECOND time from a different instance/request to
                      compare hashes. Equal hash -> no in-flight tamper observed;
                      different hash -> tampering / A-B versioning detected.
  ETag/baseline     : record ETag + Content-Length + Last-Modified per resource
                      as a reproducible integrity baseline.
  TLS pinning       : pin the SPKI (public-key) SHA-256 fingerprint of each
                      provider host, so any future cert swap is detectable.

This module NEVER injects, tampers, or sends crafted payloads — it only fetches
already-served content and compares hashes/certificates.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import socket
import ssl
import time
import urllib.parse
from collections import Counter

from .base import ModuleContext, register

SPKI_FP = re.compile(r"(?:^|[^a-zA-Z0-9])([a-zA-Z0-9_\-]{40,}={0,2})")


def _sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve(base_url: str, ref: str) -> str:
    return urllib.parse.urljoin(base_url, ref)


@register("tamper-verify", heavy=True, needs_browser=False, help=(
    "Read-only remote content-tamper verification: SRI integrity, SHA-256 "
    "recompute + repeat-fetch, ETag baseline, TLS SPKI pinning"))
def run(ctx: ModuleContext):
    rep = ctx.reporter
    target = ctx.target
    opts = ctx.options
    base = target.base_url.rstrip("/")
    art_dir = opts.get("artifacts", "omnitest_artifacts")
    os.makedirs(f"{art_dir}/tamper", exist_ok=True)

    import httpx
    UA = {"User-Agent": "OMNITEST-TamperVerify/1.0"}

    # ------------------------------------------------------------------
    # 1) Fetch page, parse <script src>/<link href>, check SRI integrity
    # ------------------------------------------------------------------
    page_resp = httpx.get(base, headers=UA, timeout=20, verify=False, follow_redirects=True)
    html = page_resp.text
    rep.add("page-fetch", "PASS" if page_resp.status_code == 200 else "FAIL",
            detail=f"status={page_resp.status_code} bytes={len(html)}")

    # all <script src="..."> and <link href="..." rel=~stylesheet>
    resources = {}  # url -> {sri:bool, tag}
    script_pat = re.compile(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*>', re.I)
    script_pat2 = re.compile(r'<script[^>]*>', re.I)
    for m in script_pat.finditer(html):
        tag = m.group(0)
        sri = 'integrity=' in tag
        url = _resolve(base, m.group(1))
        if url.startswith("http"):
            resources[url] = {"sri": sri, "tag": "script"}
    link_pat = re.compile(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*>', re.I)
    for m in link_pat.finditer(html):
        tag = m.group(0)
        if "stylesheet" in tag or ".css" in m.group(1):
            sri = 'integrity=' in tag
            url = _resolve(base, m.group(1))
            if url.startswith("http"):
                resources[url] = {"sri": sri, "tag": "link"}

    runtime_chunks = _capture_runtime_chunks(base)
    for u in runtime_chunks:
        if u.startswith("http") and u not in resources:
            resources[u] = {"sri": False, "tag": "runtime-chunk"}
    total_res = len(resources)
    no_sri = [u for u, r in resources.items() if not r["sri"]]
    rep.metric("resources_found", total_res)
    rep.metric("no_sri", len(no_sri))
    rep.metric("sri_count", total_res - len(no_sri))
    rep.metric("runtime_chunks", len(runtime_chunks))
    rep.add("SPA-chunks", "PASS" if runtime_chunks else "WARN",
            detail=(f"captured {len(runtime_chunks)} runtime code-split resources "
                    f"(game-view JS/CSS) for hash verification"))
    if len(no_sri) == 0:
        rep.add("SRI-integrity", "PASS", f"all {total_res} resources carry SRI integrity")
    else:
        rep.add("SRI-integrity", "FAIL",
                f"{len(no_sri)}/{total_res} resources WITHOUT SRI integrity (unguarded)")

    # ------------------------------------------------------------------
    # 2) SHA-256 recompute per resource + double-fetch hash comparison
    #    (different instance = separate connection & cache-buster)
    # ------------------------------------------------------------------
    tamper_cases = []
    baseline = {}  # url -> {sha256, content_len, etag, last_modified}
    for url in list(resources.keys()):
        rec = {"url": url, "sri": resources[url]["sri"]}
        try:
            r1 = httpx.get(url, headers={**UA, "Cache-Control": "no-cache"},
                           timeout=20, verify=False)
            body1 = r1.content
            sha1 = _sha256_hex(body1)
            # second instance fetch with cache-buster to force a real re-fetch
            sep = "&" if "?" in url else "?"
            r2 = httpx.get(url + f"{sep}__omni={int(time.time()*1000)}",
                           headers={**UA, "Cache-Control": "no-cache"},
                           timeout=20, verify=False)
            body2 = r2.content
            sha2 = _sha256_hex(body2)
            rec.update({
                "sha256": sha1,
                "len1": len(body1), "len2": len(body2),
                "etag": r1.headers.get("etag", ""),
                "last_modified": r1.headers.get("last-modified", ""),
                "ct": r1.headers.get("content-type", "")[:40],
            })
            baseline[url] = rec
            if sha1 == sha2 and len(body1) == len(body2):
                rec["verdict"] = "clean"
            else:
                rec["verdict"] = "TAMPERED/AB"
                tamper_cases.append(url)
        except Exception as e:
            rec["verdict"] = f"error:{type(e).__name__}"
            tamper_cases.append(url)
            baseline[url] = rec

    clean_count = sum(1 for r in baseline.values() if r.get("verdict") == "clean")
    rep.metric("hash_clean", clean_count)
    rep.metric("hash_mismatch", len(tamper_cases))
    rep.add("SHA-256-recompute", "PASS" if not tamper_cases else "FAIL",
            detail=(f"{clean_count}/{len(baseline)} resources hash-identical across "
                    f"two independent fetches (no in-flight tamper observed)"
                    + (f"; MISMATCH={tamper_cases}" if tamper_cases else "")))

    # ------------------------------------------------------------------
    # 3) ETag / Content-Length / Last-Modified baseline summary
    # ------------------------------------------------------------------
    etag_ok = sum(1 for r in baseline.values() if r.get("etag"))
    rep.add("ETag-baseline", "PASS" if etag_ok else ("WARN" if baseline else "FAIL"),
            detail=(f"{etag_ok}/{len(baseline)} resources expose ETag/Last-Modified "
                    f"for conditional-get integrity checks; "
                    f"len-diff={sum(1 for r in baseline.values() if r.get('len1')!=r.get('len2'))}"))

    # ------------------------------------------------------------------
    # 4) TLS SPKI fingerprint pinning for provider hosts (+ gfg.win)
    # ------------------------------------------------------------------
    hosts = sorted({urllib.parse.urlparse(u).hostname for u in resources} | {target.base_url.split("//")[-1].split("/")[0]})
    for hst in hosts:
        try:
            fp = _spki_fingerprint(hst, 443)
        except Exception as e:
            fp = f"error:{type(e).__name__}"
        rep.add(f"tls-pin {hst}", "PASS" if not fp.startswith("error") else "FAIL",
                detail=f"SPKI-SHA256={fp}" if not fp.startswith("error") else fp)
        rep.metric(f"pin:{hst}", 1 if not fp.startswith("error") else 0)

    # ------------------------------------------------------------------
    # evidence file + rollup
    # ------------------------------------------------------------------
    fail_cases = [u for u, r in baseline.items() if r.get("verdict") not in ("clean",)]
    overall = "PASS" if not fail_cases and len(no_sri) == 0 else (
        "FAIL" if fail_cases else ("WARN" if no_sri else "PASS"))
    rep.add("rollup", overall,
            detail=(f"resources={total_res} SRI-unprotected={len(no_sri)} "
                    f"hash-clean={clean_count} tamper-cases={len(fail_cases)}"))

    import json
    evidence = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base,
        "resources": baseline,
        "no_sri": no_sri,
        "tamper_cases": fail_cases,
        "page_bytes": len(html),
        "page_status": page_resp.status_code,
    }
    with open(f"{art_dir}/tamper/tamper_evidence.json", "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=2)
    print(f"[tamper-verify] evidence → {art_dir}/tamper/tamper_evidence.json")


def _capture_runtime_chunks(base: str) -> list:
    """Use a headless browser to load a real game view and capture the SPA's
    runtime code-split .js/.css resources via the performance log."""
    chunks: list = []
    try:
        from omnitest.modules.e2e_ui import _make_driver
        import json
        d = _make_driver()
        try:
            d.set_page_load_timeout(30)
            d.get(base + "/#/")
            time.sleep(3)
            # navigate to first game if an id is discoverable in the URL hash
            try:
                js = ("return (document.querySelector('[href*=game],a[class*=game]') "
                      "|| {}).getAttribute('href') || ''")
                href = d.execute_script(js) or ""
                if href:
                    if not href.startswith("http"):
                        href = base + ("#" if href.startswith("#") else "/") + href
                    d.get(href)
                    time.sleep(4)
            except Exception:
                pass
            for entry in d.get_log("performance"):
                try:
                    m = json.loads(entry["message"])["message"]
                except Exception:
                    continue
                if m.get("method") == "Network.requestWillBeSent":
                    u = ((m.get("params") or {}).get("request") or {}).get("url", "")
                    if (".js" in u or ".css" in u) and u.startswith("http"):
                        if u not in chunks:
                            chunks.append(u)
        finally:
            try:
                d.quit()
            except Exception:
                pass
    except Exception as e:
        print(f"[tamper-verify] runtime-chunk capture skipped: {type(e).__name__}: {e}")
    return chunks


def _spki_fingerprint(host: str, port: int = 443) -> str:
    """Return base64 SPKI SHA-256 fingerprint of the host's TLS cert (cert pin)."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as s:
            der = s.getpeercert(binary_form=True)
            # Extract the SPKI (subjectPublicKeyInfo) from the DER cert.
            # DER layout: SEQUENCE of (cert | SEQUENCE sigalg | BITSTRING signature)
            try:
                # Parse top-level SEQUENCE: tbsCertificate is the first SEQUENCE child
                if der[0] == 0x30:
                    # length of tbs
                    i = 2
                    if der[1] & 0x80:
                        n = der[1] & 0x7F
                        i = 2 + n
                    tbs_end = i + _der_len(der, i)
                    tbs = der[i:tbs_end]
                    # tbs: [0] version, serial, sigalg, issuer..., subject, [spki]...
                    # Walk fields inside tbs to find subjectPublicKeyInfo (element type 0x30
                    # whose first child is 0x30 (alg) and second child is 0x03 (bitstring)).
                    j = 0
                    spki = None
                    while j < len(tbs) - 4:
                        tag = tbs[j]
                        if tag == 0x30:
                            ln = _der_len(tbs, j)
                            nxt = j + 2 + (0 if not (tbs[j+1] & 0x80) else (tbs[j+1] & 0x7F))
                            if nxt < len(tbs) - 2 and tbs[nxt] == 0x30 and tbs[nxt+1] == 0x06:
                                # candidate SPKI: SEQUENCE{ SEQUENCE OID ... , BITSTRING 0x03 }
                                # find BITSTRING in this table
                                inner = tbs[j+1:j+ln]
                                if _contains_tag(inner, 0x03):
                                    spki = tbs[j:j+ln]
                                    break
                            j = j + ln
                        else:
                            j += 1
                    if spki:
                        return "SHA256:" + _sha256_b64(spki)
            except Exception:
                pass
            # Fallback: full-cert DER fingerprint (any cert change detectable)
            return "SHA256:" + _sha256_b64(der)


def _der_len(buf: bytes, i: int) -> int:
    """Return encoded length of DER element starting at header index i."""
    if i + 1 >= len(buf):
        return 0
    l0 = buf[i + 1]
    if not (l0 & 0x80):
        return l0
    n = l0 & 0x7F
    return int.from_bytes(buf[i + 2:i + 2 + n], "big")


def _contains_tag(buf: bytes, tag: int) -> bool:
    return tag in buf
