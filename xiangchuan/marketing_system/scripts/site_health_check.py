#!/usr/bin/env python3
"""網站體檢 — 自動化檢查線上內容與狀況。

用法：
  python site_health_check.py                     # 對線上站檢查，輸出報告
  python site_health_check.py --base http://127.0.0.1:8796   # 對本機檢查
  python site_health_check.py --json              # JSON 輸出（排程/告警用）

檢查四層：
  1) 版本與服務裡程（deploy 指紋、AI、Telegram/LINE/平台）
  2) 內容存量與「每天自動更新引擎」當天產出
  3) 主要頁面 HTTP 健康
  4) 公開 GET API 健康
嚴重問題（5xx/空內容/引擎停擺）回非 0 退出碼，方便 cron 告警。
"""
import argparse
import json
import sys
import urllib.request
import urllib.error
import datetime as _dt

DEFAULT_BASE = "https://lewislunora.onrender.com"

PAGES = [
    "/", "/index.html", "/product/", "/pricing.html", "/novels.html",
    "/social/", "/thoughts/", "/community/", "/matching.html",
    "/guides/", "/games/", "/ai-code-review/", "/app.html",
    "/ai-chat.html", "/ai-character.html", "/ai-story.html",
    "/ai-fate.html", "/operations/", "/solopreneur/", "/99u/",
    "/ai-brand/", "/register.html", "/login.html", "/tos.html",
    "/privacy.html", "/service-terms.html", "/security-portfolio.html",
    "/student/", "/stock-trading/", "/sitemap.xml",
]

PUBLIC_GET = [
    "/api/status", "/api/config", "/api/feed", "/api/thoughts",
    "/api/seo-articles", "/api/novels", "/api/community/threads",
    "/api/kb", "/api/templates", "/api/content", "/api/comments",
    "/api/pages", "/api/license/status",
]

SEVERITY = {"ok": 0, "warn": 1, "crit": 2}


def http_get(base, path, timeout=15):
    url = base if path.startswith("http") else base + path
    req = urllib.request.Request(url, headers={"User-Agent": "site-health-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def get_json(base, path, timeout=15):
    status, body = http_get(base, path, timeout)
    if status >= 400:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def today_str(offset_hours=0):
    return (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=offset_hours)).date().isoformat()


def main():
    ap = argparse.ArgumentParser(description="翔川 Neo 網站體檢")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--json", action="store_true", help="JSON 輸出")
    ap.add_argument("--fast", action="store_true", help="只跑內容＋狀態層")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args()
    base = args.base.rstrip("/")
    t = args.timeout

    report = {"base": base, "checked_at": _dt.datetime.now().isoformat(timespec="seconds")}
    problems = []
    warns = []

    def level(label):
        """印 severity 字樣。"""
        return label

    # ---------------- 1) 版本與服務 ----------------
    status = get_json(base, "/api/status", t)
    if status is None:
        problems.append("crit: /api/status 無法讀取（網站可能不在線上）")
        status = {}
    svc = {
        "fingerprint": status.get("build_fingerprint", "?"),
        "ai_available": bool(status.get("ai_available")),
        "smtp": bool(status.get("smtp_configured")),
        "telegram_set": bool(status.get("telegram_bot_token_set")),
        "line_set": bool(status.get("line_notify_configured")),
        "platforms": {},
        "scheduler": bool((status.get("scheduler") or {}).get("running") or status.get("scheduler")),
    }
    sf = status.get("platform_webhooks") or {}
    svc["platforms"] = {k: bool(v) for k, v in sf.items()}
    if not svc["ai_available"]:
        warns.append("warn: ai_available=False（GROQ 不可用，每日自動產文會停）")
    if not svc["telegram_set"]:
        warns.append("warn: Telegram bot token 未設定")
    if not svc["line_set"]:
        warns.append("warn: LINE Notify 未設定")
    for k, v in svc["platforms"].items():
        if not v:
            warns.append(f"warn: 平台 {k} 未連線（平台帳密未填）")

    # ---------------- 2) 內容存量 + 當天自動產出 ----------------
    content = {}
    feed = get_json(base, "/api/feed?page=1&per_page=50", t) or {}
    feed_items = feed.get("items") or []
    content["feed_total"] = feed.get("total", len(feed_items))
    content["feed_latest"] = (feed_items[0].get("created_at", "") if feed_items else "")
    content["feed_today"] = sum(
        1 for x in feed_items if (x.get("created_at") or "").split("T")[0][:10] == today_str()
    )
    latest_date = content["feed_latest"][:10]
    if latest_date:
        try:
            age = (_dt.date.today() - _dt.date.fromisoformat(latest_date)).days
        except ValueError:
            age = 0
        if age > 2:
            warns.append(f"warn: 短內容最後更新距今 {age} 天（{latest_date}），自動引擎可能停擺")

    seo = get_json(base, "/api/thoughts", t) or {}
    seo_items = seo.get("items") or []
    content["seo_total"] = len(seo_items)
    content["seo_latest_title"] = (seo_items[0].get("title", "") if seo_items else "")
    content["seo_latest_at"] = (seo_items[0].get("created_at", "") if seo_items else "")
    content["seo_today"] = sum(
        1 for x in seo_items if (x.get("created_at") or "").split("T")[0][:10] == today_str()
    )

    novels = get_json(base, "/api/novels", t) or {}
    nv = novels.get("items") or []
    content["novel_count"] = len(nv)
    content["novel_chapters"] = sum(int(x.get("chapter_count") or 0) for x in nv)
    content["novel_by_title"] = [
        {"title": x.get("title", "")[:16], "chapters": int(x.get("chapter_count") or 0)}
        for x in nv
    ]
    if content["novel_chapters"] == 0 and content["novel_count"] > 0:
        warns.append("warn: 有小說但章節數 0（每日連載引擎尚未產出）")

    threads = get_json(base, "/api/community/threads?per_page=5", t) or {}
    content["community_total"] = threads.get("total", 0)

    kb = get_json(base, "/api/kb", t) or {}
    content["kb_total"] = len(kb.get("items") or [])
    if content["kb_total"] == 0:
        warns.append("warn: 知識庫 0 筆，AI 客服無內容可答")

    # 每日引擎判讀
    feed_ok = content["feed_total"] >= 3
    seo_ok = content["seo_total"] >= 1
    novel_ok = content["novel_chapters"] >= 1
    engine_state = "ok"
    if not (feed_ok and seo_ok and novel_ok):
        engine_state = "warn"
        problems.append("warn: 自動更新引擎未全數產出內容（feed/SEO/小說至少一方掛零）")

    # ---------------- 3) 頁面 HTTP 健康 ----------------
    pages = {}
    pageload = []
    if not args.fast:
        for p in PAGES:
            try:
                s, _ = http_get(base, p, t)
            except urllib.error.HTTPError as e:
                s = e.code
            except Exception:
                s = 0
            pages[p] = s
        bad_pages = [p for p, s in pages.items() if s >= 500]
        notfound = [p for p, s in pages.items() if s == 404]
        if bad_pages:
            problems.append(f"crit: {len(bad_pages)} 個頁面 5xx → {bad_pages[:5]}")
        if len(notfound) > 2:
            warns.append(f"warn: {len(notfound)} 個頁面 404 → {notfound[:5]}")
        pageload = pages

    # ---------------- 4) 公開 GET API 健康 ----------------
    apis = {}
    if not args.fast:
        for a in PUBLIC_GET:
            try:
                s, _ = http_get(base, a, t)
            except urllib.error.HTTPError as e:
                s = e.code
            except Exception:
                s = 0
            apis[a] = s
        bad_api = [a for a, s in apis.items() if s >= 400]
        if bad_api:
            problems.append(f"crit: {len(bad_api)} 個公開 API 異常 → {bad_api[:5]}")

    # ---------------- 彙整 ----------------
    crits = [p for p in problems if p.startswith("crit")]
    warns_all = [p for p in problems if p.startswith("warn")] + warns
    verdict = "PASS" if not crits and len(warns_all) == 0 else ("WARN" if not crits else "FAIL")
    exit_code = SEVERITY["crit"] if crits else (SEVERITY["warn"] if warns_all else 0)

    out = {
        "verdict": verdict,
        "checked_at": report["checked_at"],
        "service": svc,
        "content": content,
        "engine_state": engine_state,
        "pages_checked": pageload,
        "api_checked": apis,
        "problems": crits + warns_all,
        "exit_code": exit_code,
    }

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        sys.exit(exit_code)

    # 純文字報告
    print("=" * 62)
    print(f"翔川 Neo 網站體檢  base={base}")
    print(f"檢查時間 {out['checked_at']}   判定: {verdict}")
    print("=" * 62)

    print("\n【1】版本與服務")
    print(f"  build_fingerprint : {svc['fingerprint']}")
    print(f"  AI (GROQ)         : {'✓ 可用' if svc['ai_available'] else '✗ 不可用'}")
    print(f"  SMTP 設定         : {bool(svc['smtp'])}")
    print(f"  Telegram token    : {bool(svc['telegram_set'])}")
    print(f"  LINE Notify       : {bool(svc['line_set'])}")
    pl = svc["platforms"] or {}
    part = ", ".join(f"{k}={'✓' if v else '✗'}" for k, v in (pl or {}).items())
    print(f"  平台連線          : {part or '(無設定)'}")

    print("\n【2】內容存量")
    print(f"  短內容 feed   : {content['feed_total']} 則（最後更新 {content['feed_latest'][:16]}）")
    print(f"  SEO 文章      : {content['seo_total']} 篇　最新《{content['seo_latest_title'][:24]}》 @{content['seo_latest_at'][:16]}")
    print(f"  小說          : {content['novel_count']} 部 共 {content['novel_chapters']} 章")
    for n in content["novel_by_title"]:
        print(f"    · {n['title']}  {n['chapters']} 章")
    print(f"  社群話題      : {content['community_total']} 則")
    print(f"  客服知識庫    : {content['kb_total']} 筆")
    print(f"  當天自動產出  : feed +{content['feed_today']}　SEO +{content['seo_today']}")

    if not args.fast:
        ok = sum(1 for s in pageload.values() if s == 200)
        print("\n【3】頁面健康  {ok}/{len(pageload)} 頁要求通過")
        bad_shown = 0
        for p, s in pageload.items():
            if s != 200:
                print(f"   {s} {p}")
                bad_shown += 1
                if bad_shown >= 8:
                    print("   …（其餘省略）")
                    break
        okapi = sum(1 for s in apis.values() if s < 400)
        print(f"\n【4】公開 API  {okapi}/{len(apis)} 正常")
        for a, s in apis.items():
            if s >= 400:
                print(f"   {s} {a}")

    print("\n【問題與建議】")
    if not (crits + warns_all):
        print("  全部通過。")
    for w in crits + warns_all:
        print("  ⚠ " + w[5:])
    print()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()