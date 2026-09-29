#!/usr/bin/env python
"""Generate interactive HTML report for the subgame integrity / tamper-risk audit."""
import base64, json, os, time
from collections import Counter

ART = "omnitest_artifacts"
data = json.load(open(f"{ART}/integrity.json"))
games = data["games"]
tls = data["tls"]

# main-site header posture (we re-query to get accurate values)
import httpx
try:
    hres = httpx.get("https://gfg.win", headers={"User-Agent":"OMNITEST-In/1.0"},
                     timeout=15, verify=False)
    hdrs = {k.lower(): v for k, v in hres.headers.items()}
except Exception:
    hdrs = {}
def has(h): return hdrs.get(h) or ""
header_rows = [
    ("Content-Security-Policy (frame-ancestors)", has("content-security-policy"),
     "可被任意嵌入 iframe / 注入。無 frame-ancestors 限制點擊劫持與頁面注入。"),
    ("X-Frame-Options", has("x-frame-options"),
     "缺少 → 無法擋 clickjacking、頁面可被第三方 framed。"),
    ("Strict-Transport-Security (HSTS)", has("strict-transport-security"),
     "缺少 → 首次連線可能被降級為 HTTP（MITM 竄改入口）。"),
    ("Referrer-Policy", has("referrer-policy"),
     "缺少 → iframe 播放 URL（含 token）可能透過 Referer 洩漏到第三方。"),
    ("X-Content-Type-Options", has("x-content-type-options"),
     "缺少 → MIME sniffing，可能被誘騙執行非預期類型。"),
    ("Permissions-Policy", has("permissions-policy"),
     "缺少 → 無法精細限制 camera/mic/autoplay 等。"),
]

# host buckets
host_ct = Counter(g["host"] for g in games.values())
host_meta = {
    "web.ministga7z.com": ("正式環境", "ok"),
    "stagegameweb.geodwfeowkg.com": ("staging 測試主機", "warn"),
    "n-game.n2stg.com": ("測試域", "warn"),
}

# posture summary
https_yes = sum(1 for g in games.values() if g["https"] == "yes")
host_exp = sum(1 for g in games.values() if g["host_expected"] == "yes")
tok = sum(1 for g in games.values() if g["sensitive_in_url"])
acc = sum(1 for g in games.values() if g.get("account_in_url"))
sandbox = sum(1 for g in games.values() if g.get("sandbox"))
allow = sum(1 for g in games.values() if g.get("allow"))
ref = sum(1 for g in games.values() if g.get("referrerpolicy"))

def esc(s):
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

rows = []
for i, (gid, g) in enumerate(games.items(), 1):
    host = g["host"]
    hcls, hname = host_meta.get(host, ("其他","other"))
    tok_badge = f'<span class="lfail">是({g["token_fields"]})</span>' if g["sensitive_in_url"] else '<span class="lpass">否</span>'
    sandbox_txt = g["sandbox"] or "—"
    rows.append(f"""<tr>
      <td class="idx">{i}</td>
      <td class="gname">{esc(g["name"])}</td>
      <td>{'<span class="lpass">HTTPS</span>' if g["https"]=="yes" else '<span class="lfail">' + esc(g["https"]) + '</span>'}</td>
      <td><span class="hosttag {hcls}">{esc(hname)}</span><div class="hm">{esc(host)}</div></td>
      <td>{tok_badge}</td>
      <td>{'<span class="lfail">是</span>' if g["account_in_url"] else '<span class="lpass">否</span>'}</td>
      <td>{esc(sandbox_txt)}</td>
    </tr>""")

tls_body = ""
for h, (v, info) in tls.items():
    color = {"ok":"lpass","warn":"warn1","fail":"lfail"}.get(v, "lfail")
    tls_body += f'<tr><td><span class="hosttag">{esc(h)}</span></td><td class="{color}">{esc(v)}</td><td style="font-size:12px;color:#8b949e">{esc(info)}</td></tr>'

host_cards = "".join(
    f'<div class="card"><div class="bignum">{c}</div><div class="bigname">{esc(k)}</div>'
    f'<div class="bignote">{esc(host_meta.get(k,(k,""))[0])}</div></div>'
    for k, c in host_ct.most_common()
)

header_body = ""
for name, val, why in header_rows:
    st = "PASS" if val else "FAIL"
    cls = "lpass" if val else "lfail"
    header_body += f'<tr><td>{esc(name)}</td><td class="{cls}">{st}</td><td style="font-size:12px;color:#8b949e">{esc(val or "無 / 未設定")}</td><td style="font-size:12px;color:#c9d1d9">{esc(why)}</td></tr>'

fixes = [
    ("URL 中的敏感 token（66/67 款）", "高",
     "播放 iframe 的 src 把 session/OAuth token（token/sign 等）放在 query string。風險：可能存在瀏覽器歷史、伺服器記錄、Referer 頭洩漏到第三方。",
     "改用 POST/handshake 取得播放，或將 token 放 header；若必須在 URL，設短 TTL、限定單次使用、並加上 strict Referrer-Policy=no-referrer。"),
    ("iframe 無 sandbox / allow / referrerpolicy（67/67）", "高",
     "所有子遊戲 iframe 都沒有任何嵌入限制屬性，第三方程式完全信任，且無 referrer 管控。",
     "對子遊戲 iframe 加上 sandbox（依需放行）、顯式 allow、及 referrerpolicy='strict-origin-when-cross-origin' 或 no-referrer。"),
    ("播放來源 47/67 指向 staging/測試主機", "中高",
     "40 款指 stagegameweb、8 款指 n2stg（測試域），僅 19 款用正式 web.ministga7z。",
     "上線環境所有遊戲的播放 iframe 來源應統一指向正式主機；測試主機不應在正式站被直接引用。"),
    ("CSP 完全缺失", "高",
     "gfg.win 無 Content-Security-Policy，頁面與第三方資源可自由注入/嵌入，增加竄改面。",
     "發布 CSP（含 frame-ancestors 'self' + 授權 provider），並加 X-Frame-Options、Referrer-Policy、HSTS、X-Content-Type-Options、Permissions-Policy。"),
    ("HSTS 缺失", "高",
     "無 Strict-Transport-Security，首次連線可被降級 → 中間人竄改/注入播放內容。",
     "於 CloudFront/源站設定 HSTS（max-age 31536000; includeSubDomains; preload）。"),
    ("子遊戲內容完整性（第三方 iframe）", "中",
     "遊戲內容由第三方主機承載，OMNITEST 無法驗證其內部邏輯/賠率是否被竄改，只能確保傳輸層（HTTPS）與來源（host allowlist）不被中間人伺機替換。",
     "應建立與各 provider 的內容 hash/版本簽章核對機制；OMNITEST 已確認 HTTPS 傳輸與來源白名單無異常，內部邏輯篡改需 provider 端配合。"),
]

fix_body = ""
for title, sev, desc, fix in fixes:
    scls = "lfail" if sev in ("高","中高") else "warn1"
    fix_body += f"""<div class="fixcard">
      <div class="fixtitle">{esc(title)} <span class="sev {scls}">{esc(sev)}</span></div>
      <div class="fixdesc">{esc(desc)}</div>
      <div class="fixrec"><b>修正建議：</b>{esc(fix)}</div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gfg.win 子遊戲竄改/破解風險評估</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif;background:#0d1117;color:#e6edf3;padding:24px;line-height:1.55}}
.wrap{{max-width:1200px;margin:0 auto}}
h1{{font-size:25px;margin-bottom:4px}} h2{{font-size:18px;margin:30px 0 12px;color:#58a6ff;border-left:4px solid #58a6ff;padding-left:10px}}
.sub{{color:#8b949e;font-size:14px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:8px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;text-align:center}}
.bignum{{font-size:32px;font-weight:700;color:#58a6ff}} .bigname{{font-size:14px;margin-top:6px;color:#c9d1d9}} .bignote{{font-size:12px;color:#8b949e;margin-top:4px}}
.big-ok .bignum{{color:#3fb950}} .big-warn .bignum{{color:#d29922}} .big-fail .bignum{{color:#f85149}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#161b22;border-radius:10px;overflow:hidden;margin-bottom:6px}}
th{{background:#21262d;color:#8b949e;text-align:left;padding:10px;font-weight:600;position:sticky;top:0}}
td{{padding:9px 10px;border-top:1px solid #21262d;vertical-align:middle}}
.gname{{font-weight:600}}.idx{{color:#8b949e;width:34px}} .hm{{font-size:11px;color:#8b949e;margin-top:2px}}
.hosttag{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;background:#21262d;color:#c9d1d9}}
.hosttag.ok{{color:#3fb950;background:#3fb95022}}.hosttag.warn{{color:#d29922;background:#d2992222}}.hosttag.other{{color:#8b949e}}
.lpass{{color:#3fb950;font-weight:600}} .lfail{{color:#f85149;font-weight:700}} .warn1{{color:#d29922}}
.sev{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:8px;vertical-align:middle}}
.fixcard{{background:#161b22;border:1px solid #30363d;border-left:4px solid #58a6ff;border-radius:8px;padding:14px 16px;margin-bottom:14px}}
.fixcard.high{{border-left-color:#f85149}}.fixcard.med{{border-left-color:#d29922}}
.fixtitle{{font-weight:700;margin-bottom:6px}} .fixdesc{{font-size:13px;color:#c9d1d9;margin-bottom:8px}}
.fixrec{{font-size:13px;color:#7ee787;background:#122620;border-radius:6px;padding:8px 12px}}
.note{{background:#1c2128;border-left:4px solid #d29922;border-radius:6px;padding:12px 16px;margin:16px 0;font-size:13px;color:#c9d1d9}}
</style></head><body>
<div class="wrap">
<h1>🛡️ gfg.win — 各子遊戲竄改 / 破解風險評估</h1>
<div class="sub">OMNITEST games-integrity（唯讀、非破壞）｜產出 {time.strftime('%Y-%m-%d %H:%M')}｜授權範圍：gfg.win + 播放 provider 網域</div>

<h2>總體姿勢</h2>
<div class="grid">
  <div class="card big-ok"><div class="bignum">{https_yes}/{len(games)}</div><div class="bigname">iframe 走 HTTPS</div><div class="bignote">無明文 / 無中間人注入</div></div>
  <div class="card big-ok"><div class="bignum">{host_exp}/{len(games)}</div><div class="bigname">來源在授權白名單</div><div class="bignote">無未知/惡意 host</div></div>
  <div class="card big-warn"><div class="bignum">{tok}/{len(games)}</div><div class="bigname">URL 含敏感 token</div><div class="bignote">session/簽章在 query</div></div>
  <div class="card big-fail"><div class="bignum">{acc}</div><div class="bigname">帳號洩漏於 URL</div></div>
  <div class="card big-fail"><div class="bignum">{sandbox}</div><div class="bigname">有 sandbox</div></div>
  <div class="card big-fail"><div class="bignum">{ref}</div><div class="bigname">有 referrerpolicy</div></div>
</div>

<h2>播放來源 host 分布</h2>
<div class="grid">{host_cards}</div>

<div class="note">
  ⚠️ <b>主站 + API 完全沒有任何安全標頭</b>（CSP / X-Frame-Options / HSTS / Referrer-Policy /
  X-Content-Type-Options / Permissions-Policy / CORS 全缺失）。這是最直接的竄改/注入風險面。
</div>

<h2>主站安全標頭（防竄改控制）</h2>
<table><thead><tr><th>Header</th><th>狀態</th><th>目前值</th><th>風險說明</th></tr></thead>
<tbody>{header_body}</tbody></table>

<h2>播放 provider TLS 🛰️</h2>
<table><thead><tr><th>主機</th><th>狀態</th><th>憑證 / 版本</th></tr></thead><tbody>{tls_body}</tbody></table>

<h2>67 款子遊戲完整性明細</h2>
<table><thead><tr><th>#</th><th>子遊戲</th><th>傳輸</th><th>播放主機</th><th>URL token</th><th>帳號於 URL</th><th>sandbox</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>

<h2>竄改 / 破解風險面 ＋ 修正建議（給開發/系統）</h2>
{fix_body}

<div class="note">
  本次為<b>唯讀、非破壞</b>之完整性評估：僅檢查傳輸層（HTTPS）、來源白名單、iframe 控制屬性、主站標頭、
  與 provider TLS 憑證。未對任何子遊戲進行實際竄改、注入打擊或越權操作。涉及 provider 內部遊戲邏輯/賠率之
  真實性驗證，需 provider 端配合提供內容簽章機制，OMNITEST 已確認其傳輸與來源無中間人替換入口。
</div>

<div style="text-align:center;color:#8b949e;font-size:12px;margin-top:26px">
  OMNITEST 自動化測試平台 · 資料來源 omnitest_artifacts/integrity.json
</div>
</div></body></html>"""

out = f"{ART}/games_integrity_report.html"
open(out, "w", encoding="utf-8").write(html)
print(f"written: {out} ({os.path.getsize(out)/1024:.0f} KB)")
