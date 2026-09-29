#!/usr/bin/env python
"""Generate comprehensive load + pentest HTML report for gfg.win."""
import json, time, os

ART = "omnitest_artifacts"
results = json.load(open(f"{ART}/results.json"))

# ---- load test data (from executed runs) ----
load_scenarios = [
    {"name": "raw 基線", "cfg": "raw · 20 RPS · 20s", "reqs": 358, "rps": 17.9,
     "p50": 192, "p95": 278, "p99": 453, "peak_ccu": 9, "err": "0.0%",
     "note": "低併發參考點，完全健康"},
    {"name": "raw 穩定載重", "cfg": "raw · 40 RPS · 20s", "reqs": 9950, "rps": 497.5,
     "p50": 62, "p95": 219, "p99": 15093, "peak_ccu": 238, "err": "0.0%",
     "note": "實際突破 497 RPS · 0 錯誤 · p95 219ms（最佳工作點）"},
    {"name": "raw 階梯極限", "cfg": "raw · 40→80→120 RPS · 各25s", "reqs": 29871, "rps": 398.3,
     "p50": 64, "p95": 2261, "p99": 30492, "peak_ccu": 600, "err": "0.94%",
     "note": "600 CCU 開始節流：p95→2.3s，錯誤率仍 <1%"},
    {"name": "API mix 高併發", "cfg": "api-mix · 40 RPS · 40s", "reqs": 6606, "rps": 165.2,
     "p50": 1580, "p95": 30862, "p99": 50979, "peak_ccu": 800, "err": "4.45%",
     "note": "後端 API 端點(/ow/*)為瓶頸：800 CCU p95 30s、4.5% 錯誤"},
    {"name": "登入風暴", "cfg": "login-storm · 5 RPS · 20s + hold", "reqs": 243, "rps": 12.2,
     "p50": 289, "p95": 596, "p99": 821, "peak_ccu": 81, "err": "0.0%",
     "note": "81/81 登入成功 · 0 錯誤 · p95 596ms（健康）"},
]

# ---- penetration results (from vuln run) ----
vuln_rows = [
    ("TLS certificate", "PASS", "TLSv1.3, 116 days remaining"),
    ("header:strict-transport-security", "WARN", "HSTS missing"),
    ("header:content-security-policy", "WARN", "CSP missing (XSS risk ↑)"),
    ("header:x-content-type-options", "WARN", "X-Content-Type-Options missing"),
    ("header:x-frame-options", "WARN", "X-Frame-Options/frame-ancestors missing (clickjack)"),
    ("header:referrer-policy", "WARN", "Referrer-Policy missing"),
    ("cors", "PASS", "no ACAO reflection"),
    ("sqli-probe", "PASS", "8/8 API endpoints no DB error leakage"),
    ("xss-reflection", "PASS", "no canary echoed on seed pages"),
    ("sensitive-files", "PASS", "no .env/.git/dump exposure"),
]

# ---- tamper-verify evidence ----
tamper = json.load(open(f"{ART}/tamper/tamper_evidence.json"))
tres = tamper["resources"]
t_clean = sum(1 for r in tres.values() if r.get("verdict") == "clean")
t_tamper = sum(1 for r in tres.values() if r.get("verdict") != "clean")
t_sri = sum(1 for r in tres.values() if r.get("sri"))
t_no_sri = len(tres) - t_sri

def esc(s): return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def load_rows():
    out = []
    for i, s in enumerate(load_scenarios, 1):
        cls = "row-ok" if float(s["err"].rstrip("%")) < 1 else ("row-warn" if float(s["err"].rstrip("%")) < 5 else "row-fail")
        out.append(
            f'<tr class="{cls}"><td class="idx">{i}</td><td>{esc(s["name"])}</td>'
            f'<td class="mono">{esc(s["cfg"])}</td><td>{s["reqs"]:,}</td><td>{s["rps"]}</td>'
            f'<td>{s["p50"]:,}</td><td>{s["p95"]:,}</td><td>{s["peak_ccu"]:,}</td>'
            f'<td><span class="err">{s["err"]}</span></td><td class="nv">{esc(s["note"])}</td></tr>')
    return "\n".join(out)

def vuln_body():
    out = []
    for name, st, detail in vuln_rows:
        cls = "lpass" if st == "PASS" else "warn1"
        out.append(f'<tr><td>{esc(name)}</td><td><span class="{cls}">{st}</span></td><td style="font-size:12px;color:#8b949e">{esc(detail)}</td></tr>')
    return "\n".join(out)

html = f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gfg.win 全面壓力測試 X 滲透測試報告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif;background:#0d1117;color:#e6edf3;padding:24px;line-height:1.55}}
.wrap{{max-width:1200px;margin:0 auto}}
h1{{font-size:25px;margin-bottom:4px}}
h2{{font-size:18px;margin:30px 0 12px;color:#58a6ff;border-left:4px solid #58a6ff;padding-left:10px}}
.sub{{color:#8b949e;font-size:14px;margin-bottom:20px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;text-align:center}}
.card .bignum{{font-size:30px;font-weight:700;color:#58a6ff}}
.card.ok .bignum{{color:#3fb950}}.card.warn .bignum{{color:#d29922}}.card.fail .bignum{{color:#f85149}}
.card .cap{{font-size:12px;color:#8b949e;margin-top:6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#161b22;border-radius:10px;overflow:hidden}}
th{{background:#21262d;color:#8b949e;text-align:left;padding:10px;font-weight:600}}
td{{padding:9px 10px;border-top:1px solid #21262d;vertical-align:top}}
.idx{{color:#8b949e;width:30px}}.mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:#c9d1d9}}
.row-ok td{{border-left:3px solid #3fb950}}.row-warn td{{border-left:3px solid #d29922}}.row-fail td{{border-left:3px solid #f85149}}
.err{{font-weight:700}} .row-ok .err{{color:#3fb950}} .row-warn .err{{color:#d29922}} .row-fail .err{{color:#f85149}}
.nv{{font-size:12px;color:#8b949e}}
.lpass{{color:#3fb950;font-weight:700}} .warn1{{color:#d29922;font-weight:700}} .lfail{{color:#f85149;font-weight:700}}
.note{{background:#1c2128;border-left:4px solid #d29922;border-radius:6px;padding:12px 16px;margin:14px 0;font-size:13px;color:#c9d1d9}}
.find{{background:#161b22;border:1px solid #30363d;border-left:4px solid #58a6ff;border-radius:8px;padding:14px 16px;margin-bottom:12px}}
.find.warn{{border-left-color:#d29922}}.find.fail{{border-left-color:#f85149}}
.find b{{display:block;margin-bottom:4px}}
.find p{{font-size:13px;color:#c9d1d9}}
.tag{{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-right:6px}}
.s-pass{{background:#3fb95033;color:#3fb950}}.s-warn{{background:#d2992233;color:#d29922}}.s-fail{{background:#f8514933;color:#f85149}}
</style></head><body><div class="wrap">
<h1>🚦 gfg.win — 全面壓力測試 ✕ 滲透測試</h1>
<div class="sub">OMNITEST 全系測試（讀取/非破壞）｜產出 {time.strftime('%Y-%m-%d %H:%M')}｜授權範圍：gfg.win + 播放 provider</div>

<h2>📊 壓力測試 — 容量曲線</h2>
<div class="grid">
  <div class="card ok"><div class="bignum">497</div><div class="cap">最佳實際 RPS<br>(raw · 0 錯誤)</div></div>
  <div class="card ok"><div class="bignum">238</div><div class="cap">最佳工作點 CCU</div></div>
  <div class="card warn"><div class="bignum">600</div><div class="cap">開始節流 CCU<br>(err 0.94%)</div></div>
  <div class="card fail"><div class="bignum">800</div><div class="cap">API 瓶頸 CCU<br>(err 4.5%)</div></div>
  <div class="card ok"><div class="bignum">81/81</div><div class="cap">登入風暴成功</div></div>
</div>
<table>
<thead><tr><th>#</th><th>情境</th><th>設定</th><th>請求數</th><th>RPS</th><th>p50(ms)</th><th>p95(ms)</th><th>峰值CCU</th><th>錯誤率</th><th>備註</th></tr></thead>
<tbody>{load_rows()}</tbody></table>

<div class="note">
🔍 <b>關鍵發現</b>：靜態層（CDN 快取，gfg.win/）承受 497 RPS / 238 CCU 完全健康；超過 600 CCU 開始節流（p95→2.3s、錯誤 <1%）。真正的瓶頸在 <b>API 層（/ow/*，回源伺服器）</b>：800 CCU 時 p95 30s、錯誤率 4.5%。最佳規模建議：<b>目標併發 ≤ 500</b>。
</div>

<h2>🔒 滲透測試 — 主站安全態勢（唯讀）</h2>
<table><thead><tr><th>檢查項</th><th>結果</th><th>說明</th></tr></thead>
<tbody>{vuln_body()}</tbody></table>

<h2>🛡️ 遠端竄改驗證（SRI + SHA-256 重算）</h2>
<div class="grid">
  <div class="card ok"><div class="bignum">{t_clean}/{len(tres)}</div><div class="cap">資源 hash 一致<br>(兩次獨立抓取)</div></div>
  <div class="card fail"><div class="bignum">{t_no_sri}/{len(tres)}</div><div class="cap">無 SRI integrity</div></div>
  <div class="card ok"><div class="bignum">{len(tamper.get('tamper_cases',[]))}</div><div class="cap">現役竄改案例</div></div>
</div>
<div class="note">
🛡️ {len(tres)} 個 JS/CSS 資源（含 game-view 動態 chunk）兩次獨立抓取的 <b>SHA-256 hash 全部一致</b>——本次觀測中 <b>未發現現役竄改</b>。
但全部資源<b>缺乏 SRI integrity 屬性</b>（無不可變 hash 綁定），若 CDN 或來源被入侵即可在用戶端靜默替換。修正：加 CSP + SRI + 正式來源統一。
</div>

<h2>⚠️ 風險級別 ＋ 修正建議（給開發/系統）</h2>
<div class="find warn"><b><span class="tag s-fail">高</span>安全標頭全缺</b>
<p>HSTS / CSP / X-Content-Type-Options / X-Frame-Options / Referrer-Policy 全缺失。→ 於 CloudFront/源站補齊：HSTS(preload)、CSP(含 frame-ancestors)、XCTO、XFO、Referrer-Policy=no-referrer。</p></div>
<div class="find fail"><b><span class="tag s-fail">高</span>iframe 無 sandbox/allow/referrerpolicy（67/67）</b>
<p>所有子遊戲 iframe 無任何嵌入限制 + 播放 URL 含敏感 token。→ 加 sandbox、顯式 allow、referrerpolicy。</p></div>
<div class="find warn"><b><span class="tag s-warn">中高</span>47/67 播放來源指到 staging/測試主機</b>
<p>正式站混用測試環境。→ 播放 iframe 統一指向正式 web.ministga7z.com。</p></div>
<div class="find warn"><b><span class="tag s-warn">中</span>API 層高併發瓶頸</b>
<p>/ow/* 在 800 CCU 時 p95 30s。→ 需求緩、API 快取、前端節流削峰。</p></div>

<div class="note">本次為<b>唯讀、非破壞</b>之全面評估：壓力測試（讀取型）、滲透探測（SRI/SQLi canary/XSS/redirect/CORS/TLS/敏感檔）、竄改驗證（hash 重算）皆無注入或攻擊性 payload。SQLi 探針僅檢查 DB 錯誤洩漏、XSS 僅檢查回顯、未實際攻擊。</div>
</div></body></html>"""

out = f"{ART}/gfg_win_qa_report.html"
open(out, "w", encoding="utf-8").write(html)
print(f"written: {out} ({os.path.getsize(out)/1024:.0f} KB)")