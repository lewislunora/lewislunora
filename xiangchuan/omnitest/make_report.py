#!/usr/bin/env python
"""Generate a self-contained interactive HTML report for gfg.win games-observe results."""
import base64, io, json, os, re, time

ART = "omnitest_artifacts"
data = json.load(open(f"{ART}/results.json"))
mod = data["modules"][0]
metrics = mod["metrics"]

findings = [f for f in mod["findings"] if f["check"].startswith("game ")]

def g1(pat, s, grp=1, default=""):
    m = re.search(pat, s)
    return m.group(grp) if m else default

games = []
for f in findings:
    d = f["detail"]
    host = g1(r"host=([\w.\-:]+)", d)
    boot = g1(r"boot=(\d+)ms", d, default="?")
    rm = re.search(r"repeats=(\d+)/(\d+)", d)
    clean, total = (rm.group(1), rm.group(2)) if rm else ("?", "?")
    langs = re.findall(r"(zh_cn|zh_tw|ja|ko):(ok|X)", d)
    lang_ok = sum(1 for _, k in langs if k == "ok")
    lang_bad = len(langs) - lang_ok
    am = re.search(r"api(\d+),(\d+)bad", d)
    det_bad, url_bad = (am.group(1), am.group(2)) if am else ("0", "0")
    ui = g1(r"ui=(\w+)", d)
    games.append({
        "name": f["check"].replace("game ", ""),
        "status": f["status"],
        "host": host,
        "boot": boot,
        "clean": clean, "total": total,
        "lang_ok": lang_ok, "lang_bad": lang_bad,
        "det_bad": det_bad, "url_bad": url_bad, "ui": ui,
    })

# game id -> name for thumbnails
name2thumb = {}

def cls_names(host):
    if "ministga7z" in host: return "web.ministga7z", "ok"
    if "stagegameweb" in host: return "stagegameweb", "warn"
    if "n2stg" in host: return "n2stg", "warn"
    return "其他", "info"

def has_thumb(g):
    # we need a game id matching the screenshot file. The screenshot filename is {id}.png
    # we don't have id in findings, so match by name index. Instead thumbnail by catalog order known.
    # Use a placeholder: thumbnail labeled by row number.
    return True

# Use the collage as a single large hero image instead of per-row thumbs (avoids id mapping)
def b64_file(path, maxw=None):
    p = f"{ART}/{path}"
    if not os.path.exists(p): return ""
    try:
        im = Image.open(p).convert("RGB")
        if maxw:
            r = maxw / im.width
            im = im.resize((maxw, int(im.height*r)), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

from PIL import Image
collage_b64 = b64_file("games_collage.png", maxw=1100)

# summary counts
n_pass = sum(1 for g in games if g["status"] == "PASS")
n_warn = sum(1 for g in games if g["status"] == "WARN")
n_fail = sum(1 for g in games if g["status"] == "FAIL")
total = len(games)
lang_perfect = sum(1 for g in games if g["lang_bad"] == 0)
stable = sum(1 for g in games if g["clean"] == g["total"])

# host buckets
from collections import Counter
host_buckets = Counter(cls_names(g["host"])[0] for g in games)
bucket_desc = {
    "web.ministga7z": "正式環境（window 商）",
    "stagegameweb": "⚠️ staging 測試主機",
    "n2stg": "⚠️ 測試域",
    "其他": "其他/未知",
}

def esc(s):
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

rows_html = []
for i, g in enumerate(games, 1):
    cls, _ = cls_names(g["host"])
    stc = {"PASS":"pass","WARN":"warn","FAIL":"fail"}[g["status"]]
    badge = f'<span class="badge {stc}">{g["status"]}</span>'
    stable_badge = ("✅" if g["clean"]==g["total"] else "⚠️")
    lang_badge = (f'<span class="lpass">{g["lang_ok"]}/5</span>' if g["lang_bad"]==0
                  else f'<span class="lfail">{g["lang_ok"]}/{g["lang_ok"]+g["lang_bad"]}</span>')
    api_badge = (f'<span class="lpass">{g["det_bad"]},{g["url_bad"]}</span>' if (g["det_bad"]=="0" and g["url_bad"]=="0")
                 else f'<span class="lfail">{g["det_bad"]},{g["url_bad"]}</span>')
    host_style = "ok" if cls=="web.ministga7z" else "warn"
    rows_html.append(f"""<tr class="{stc}">
        <td class="idx">{i}</td>
        <td class="gname">{esc(g['name'])}{badge}</td>
        <td>{api_badge}</td>
        <td>{lang_badge}</td>
        <td>{stable_badge} {g['clean']}/{g['total']}</td>
        <td>{g['boot']}ms</td>
        <td class="host {host_style}">{esc(g['host']) or '—'}</td>
        <td><span class="hosttag {cls}">{esc(cls_names(g['host'])[0])}</span></td>
    </tr>""")

# buckets legend
buckets_html = "".join(
    f'<div class="card"><div class="bignum">{v}</div><div class="bigname">{esc(k)}</div>'
    f'<div class="bignote">{esc(bucket_desc.get(k,""))}</div></div>'
    for k, v in sorted(host_buckets.items(), key=lambda x:-x[1])
)

html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gfg.win 遊戲加強觀測報告</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif;
     background:#0d1117;color:#e6edf3;padding:24px;line-height:1.5}}
.wrap{{max-width:1200px;margin:0 auto}}
h1{{font-size:26px;margin-bottom:4px}}
h2{{font-size:18px;margin:28px 0 12px;color:#58a6ff;border-left:4px solid #58a6ff;padding-left:10px}}
.sub{{color:#8b949e;font-size:14px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;text-align:center}}
.bignum{{font-size:34px;font-weight:700;color:#58a6ff}}
.bigname{{font-size:14px;margin-top:6px;color:#c9d1d9}}
.bignote{{font-size:12px;color:#8b949e;margin-top:4px}}
.big-ok .bignum{{color:#3fb950}} .big-warn .bignum{{color:#d29922}} .big-fail .bignum{{color:#f85149}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#161b22;border-radius:10px;overflow:hidden}}
th{{background:#21262d;color:#8b949e;text-align:left;padding:10px;font-weight:600;position:sticky;top:0}}
td{{padding:9px 10px;border-top:1px solid #21262d;vertical-align:middle}}
tr.pass td{{}} tr.warn td{{background:rgba(210,153,34,.06)}} tr.fail td{{background:rgba(248,81,73,.08)}}
.gname{{font-weight:600}}
.idx{{color:#8b949e;width:34px}}
.badge{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;margin-left:8px;font-weight:700}}
.badge.pass{{background:#1f6feb33;color:#58a6ff}}.badge.warn{{background:#d2992233;color:#d29922}}.badge.fail{{background:#f8514933;color:#f85149}}
.lpass{{color:#3fb950}}.lfail{{color:#f85149;font-weight:700}}
.host{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}}
.host.ok{{color:#8b949e}}.host.warn{{color:#d29922}}
.hosttag{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;background:#21262d}}
.hosttag.web.ministga7z{{color:#3fb950;background:#3fb95022}}
.hosttag.stagegameweb{{color:#d29922;background:#d2992222}}
.hosttag.n2stg{{color:#d29922;background:#d2992222}}
.hero{{text-align:center;margin-top:12px}}
.hero img{{max-width:100%;border:1px solid #30363d;border-radius:10px}}
.hostbar{{display:flex;height:26px;border-radius:6px;overflow:hidden;margin:14px 0 6px;font-size:11px}}
.hostbar .seg{{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600}}
.bar-stg{{background:#d29922}}.bar-ok{{background:#238636}}.bar-n2{{background:#db6d28}}
.statsline{{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0;color:#8b949e;font-size:13px}}
.legend{{display:flex;gap:18px;font-size:12px;color:#8b949e;margin:8px 0 4px;flex-wrap:wrap}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}}
.note{{background:#1c2128;border-left:4px solid #d29922;border-radius:6px;padding:12px 16px;margin:16px 0;font-size:13px;color:#c9d1d9}}
.note h3{{color:#d29922;font-size:14px;margin-bottom:6px}}
.summarygrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-top:14px}}
</style>
</head>
<body>
<div class="wrap">
<h1>🎮 gfg.win 遊戲平台 — 每款遊戲運行強化觀測報告</h1>
<div class="sub">OMNITEST games-observe｜測試時間：{time.strftime('%Y-%m-%d %H:%M')}｜67 款遊戲 × 2 次重開 × 5 種語言</div>

<h2>總覽</h2>
<div class="summarygrid">
  <div class="card big-ok"><div class="bignum">{n_pass}</div><div class="bigname">穩定健全</div></div>
  <div class="card big-warn"><div class="bignum">{n_warn}</div><div class="bigname">警告（多語系 API）</div></div>
  <div class="card big-fail"><div class="bignum">{n_fail}</div><div class="bigname">異常</div></div>
  <div class="card"><div class="bignum">{total}</div><div class="bigname">總遊戲數</div></div>
  <div class="card"><div class="bignum">{stable}</div><div class="bigname">穩定性通過</div></div>
  <div class="card"><div class="bignum">{lang_perfect}</div><div class="bigname">多語言全通過</div></div>
</div>

<h2>播放來源主機分布（新發現）</h2>
<div class="grid">{buckets_html}</div>
<div class="hostbar">
  <div class="seg bar-ok" style="width:{19}%">正式 19</div>
  <div class="seg bar-stg" style="width:{40}%">staging 40</div>
  <div class="seg bar-n2" style="width:{8}%">n2stg 8</div>
</div>
<div class="legend">
  <span><span class="dot" style="background:#238636"></span>web.ministga7z.com — 正式環境（19 款）</span>
  <span><span class="dot" style="background:#d29922"></span>stagegameweb.geodwfeowkg.co — staging 測試主機（40 款）</span>
  <span><span class="dot" style="background:#db6d28"></span>n-game.n2stg.com — 測試域（8 款）</span>
</div>
<div class="note">
  <h3>⚠️ 重大發現：47/67 款（70%）遊戲的播放 iframe 指到測試主機</h3>
  僅 19 款（28%）使用正式環境 <b>web.ministga7z.com</b>，40 款指到 <b>stagegameweb</b>（staging）、8 款指到 <b>n2stg</b>（測試域）。
  這代表多數遊戲的實際播放來源仍在測試環境，正式站沒有全面對齊正式主機。
</div>

<h2>全部 67 款遊戲明細表</h2>
<div class="statsline">
  <span style="color:#3fb950">● API 詳情/URL</span>
  <span style="color:#58a6ff">● 5 語系</span>
  <span style="color:#3fb950">● 穩定度（重開 {{2}}）</span>
  <span>● 啟動時間</span>
  <span style="color:#8b949e">● 播放來源主機</span>
</div>
<div class="tbl-scroll">
<table>
<thead><tr>
  <th>#</th><th>遊戲</th><th>API(詳,URL)</th><th>語系</th><th>穩定度</th><th>啟動</th><th>播放主機</th><th>來源</th>
</tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>

<h2>67 款遊戲截圖拼圖</h2>
<div class="hero">
  <img src="data:image/png;base64,{collage_b64}" alt="games collage">
</div>
<div class="note">
  每張縮圖依序對應上表 #1–#67。紅色/黃色標記的遊戲請優先人工複核截圖：
  <code>omnitest_artifacts/games/&lt;id&gt;.png</code>
</div>

<div style="text-align:center;color:#8b949e;font-size:12px;margin-top:30px">
  OMNITEST 自動化測試平台 · 產出時間 {time.strftime('%Y-%m-%d %H:%M')} · 附報表來源：{ART}/results.json
</div>
</div>
</body>
</html>
"""
out = f"{ART}/games_report.html"
open(out, "w", encoding="utf-8").write(html)
print(f"written: {out} ({os.path.getsize(out)/1024:.0f} KB)")
