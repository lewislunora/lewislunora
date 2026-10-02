"""data.gov.tw 政府資料開放平臺：全目錄自動爬取＋資料集下載分析。

- sync_catalog(): 用 v2 metadata/list API 分批同步「全部」資料集詮釋資料
- ingest(nid): 依目錄內下載網址抓取 CSV/JSON/zip 並正規化存入 DB
- analyze(nid): 對已存入資料欄位做基本統計（型別、眾數、數值總和/平均、最高群組）
"""

import csv
import io
import json
import logging
import zipfile

import requests

from ..config import GROQ_API_KEY, GROQ_MODEL
from ..database import execute, fetch, fetch_one

logger = logging.getLogger(__name__)

CATALOG_API = "https://data.gov.tw/api/v2/rest/dataset/metadata/list"
DETAIL_API = "https://data.gov.tw/api/v2/rest/dataset/{}"

PAGE_LIMIT = 100
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
MAX_ROWS = 60000
MAX_COLS = 200
COOLDOWN_SECONDS = 600

_INGEST_META = {}


def _truncate(text, n=4000):
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        text = ", ".join(str(x) for x in text)
    elif not isinstance(text, str):
        text = str(text)
    return text[:n]


def sync_catalog(max_pages: int = 150) -> dict:
    """分批同步資料集詮釋資料。回傳本次處理統計。"""
    page = 1
    fetched = 0
    upserted = 0
    errors = 0
    while page <= max_pages:
        try:
            resp = requests.get(
                CATALOG_API,
                params={"page_num": page, "page_limit": PAGE_LIMIT},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json().get("result") or {}
            items = payload.get("search_result") or []
            if not items:
                break
            for it in items:
                _upsert_catalog(it)
                upserted += 1
            fetched += len(items)
            logger.info(f"govdata catalog page {page}: {len(items)}")
            page += 1
        except Exception as e:
            errors += 1
            logger.warning(f"govdata catalog page {page} failed: {e}")
            if errors >= 3:
                break
    return {"pages": page - 1, "fetched": fetched, "upserted": upserted, "errors": errors}


def _upsert_catalog(it: dict):
    if not it.get("nid"):
        return
    execute(
        "INSERT INTO gov_catalog (nid, title, agency, category, topic, freq, charge, license, "
        "formats, dl_url, qty, description, view_times, synced_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now')) "
        "ON CONFLICT(nid) DO UPDATE SET "
        "title=excluded.title, agency=excluded.agency, category=excluded.category, "
        "topic=excluded.topic, freq=excluded.freq, charge=excluded.charge, "
        "license=excluded.license, formats=excluded.formats, dl_url=excluded.dl_url, "
        "qty=excluded.qty, description=excluded.description, "
        "view_times=excluded.view_times, synced_at=datetime('now')",
        [
            str(it.get("nid")),
            _truncate(it.get("title")),
            _truncate(it.get("agency_name")),
            _truncate(it.get("category_name")),
            _truncate(it.get("topic_name")),
            _truncate(it.get("check_freq_name")),
            _truncate(it.get("charge")),
            _truncate(it.get("license_name")),
            _truncate(it.get("all_file_format_name")),
            _truncate(it.get("all_url"), 2000),
            _truncate(it.get("all_amount")),
            _truncate(it.get("content")),
            int(it.get("dataset_view_times") or 0),
        ],
    )


def _resolution_fields(nid: str) -> dict:
    row = fetch_one("SELECT * FROM gov_catalog WHERE nid=?", (nid,))
    if row:
        return dict(row)
    try:
        resp = requests.get(DETAIL_API.format(nid), timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        r = payload.get("result") or payload.get("data") or {}
        if isinstance(r, dict) and r.get("nid"):
            _upsert_catalog(r)
            return dict(r)
    except Exception as e:
        logger.warning(f"govdata detail {nid} failed: {e}")
    return {}


def _stream_download(url: str, verify: bool, cap: int) -> bytes:
    with requests.get(url, timeout=60, stream=True, verify=verify) as r:
        r.raise_for_status()
        chunks = []
        size = 0
        for chunk in r.iter_content(1024 * 256):
            chunks.append(chunk)
            size += len(chunk)
            if size > cap:
                raise RuntimeError(f"檔案超過 {cap // 1024 // 1024}MB 上限")
        return b"".join(chunks)


def _pick_url(raw: str) -> str:
    import re
    if isinstance(raw, (list, tuple)):
        raw = " ".join(str(x) for x in raw)
    raw = (raw or "").strip()
    urls = re.findall(r"https?://[^\s\",]+", raw)
    for u in urls:
        low = u.lower()
        if low.endswith((".csv", ".json", ".zip", ".7z", ".gz")):
            return u
    return urls[0] if urls else raw


def _download_bytes(url: str) -> bytes:
    try:
        return _stream_download(url, verify=True, cap=MAX_DOWNLOAD_BYTES)
    except requests.exceptions.SSLError:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logger.warning(f"govdata TLS 驗證失敗（舊憑證），降級重試: {url[:80]}")
        return _stream_download(url, verify=False, cap=MAX_DOWNLOAD_BYTES)


def _bytes_to_rows(data: bytes) -> list:
    text = None
    for enc in ("utf-8-sig", "big5", "utf-8"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise RuntimeError("無法辨識編碼")
    if text.lstrip().startswith(("{", "[")):
        arr = json.loads(text)
        if isinstance(arr, dict):
            arr = arr.values() or []
        if not isinstance(arr, list):
            arr = []
        cols = []
        rows = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            row = {str(k): str(v if v is not None else "") for k, v in item.items()}
            rows.append(row)
        return rows
    reader = csv.reader(io.StringIO(text))
    lines = list(reader)
    header_idx = 0
    if lines and len(lines[0]) == 1:
        header_idx = None
        for i in range(min(len(lines), 6)):
            if len(lines[i]) >= 2:
                header_idx = i
                break
    if header_idx is None:
        return []
    headers = [h.strip() for h in lines[header_idx] if h and h.strip()]
    if not headers:
        return []
    rows = []
    for line in lines[header_idx + 1:]:
        if len(line) < max(len(headers), 1):
            continue
        row = {}
        for i, h in enumerate(headers):
            row[h] = line[i] if i < len(line) else ""
        rows.append(row)
    return rows


def _extract(data: bytes, url: str) -> list:
    low = url.lower()
    if low.endswith(".zip") or data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.lower().endswith((".csv", ".json")):
                    return _bytes_to_rows(zf.read(name))
        raise RuntimeError("zip 內沒有 CSV/JSON")
    return _bytes_to_rows(data)


def ingest(nid: str, force: bool = False) -> dict:
    """下載、正規化、存入資料集內容（上限 MAX_ROWS）。含 10 分鐘同 nid 冷卻。"""
    nid = str(nid)
    now_meta = _INGEST_META.get(nid)
    if not force and now_meta:
        age = (__import__("time").time() - now_meta) / 60
        if age < COOLDOWN_SECONDS / 60:
            return {"ok": False, "note": f"同資料集 {COOLDOWN_SECONDS // 60} 分鐘內已抓過"}
    meta = _resolution_fields(nid)
    if not meta:
        return {"ok": False, "note": "找不到該資料集"}
    url = _pick_url(meta.get("dl_url") or meta.get("all_url"))
    if not url:
        return {"ok": False, "note": "此資料集無下載連結"}
    try:
        data = _download_bytes(url)
        rows = _extract(data, url)[:MAX_ROWS]
        if not rows:
            return {"ok": False, "note": "資料集內容為空或不可解析"}
        cols = []
        seen = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        cols = cols[:MAX_COLS]
        execute("DELETE FROM gov_rows WHERE nid=?", (nid,))
        for idx, row in enumerate(rows):
            slim = {c: (row.get(c) or "") for c in cols}
            execute(
                "INSERT INTO gov_rows (nid, row_idx, payload) VALUES (?,?,?)",
                [nid, idx, json.dumps(slim, ensure_ascii=False, default=str)],
            )
        execute(
            "INSERT INTO gov_datasets (nid, title, agency, columns_json, row_count, status, "
            "sample_json, ingested_at) VALUES (?,?,?,?,?,?,?, datetime('now')) "
            "ON CONFLICT(nid) DO UPDATE SET title=excluded.title, agency=excluded.agency, "
            "columns_json=excluded.columns_json, row_count=excluded.row_count, "
            "status=excluded.status, sample_json=excluded.sample_json, "
            "ingested_at=datetime('now')",
            [
                nid,
                meta.get("title") or "",
                meta.get("agency_name") or meta.get("agency") or "",
                json.dumps(cols, ensure_ascii=False),
                len(rows),
                "ok",
                json.dumps(rows[:5], ensure_ascii=False, default=str),
            ],
        )
        _INGEST_META[nid] = __import__("time").time()
        return {"ok": True, "nid": nid, "rows": len(rows), "cols": len(cols)}
    except Exception as e:
        logger.exception(f"govdata ingest {nid} failed")
        execute(
            "INSERT INTO gov_datasets (nid, title, agency, row_count, status, note, ingested_at) "
            "VALUES (?,?,?,0,'failed',?, datetime('now')) "
            "ON CONFLICT(nid) DO UPDATE SET status='failed', note=?, ingested_at=datetime('now')",
            [nid, meta.get("title", ""), meta.get("agency", ""), _truncate(str(e)), _truncate(str(e))],
        )
        return {"ok": False, "note": str(e)}


def analyze(nid: str) -> dict:
    """對存入資料做基本分析：欄位型別/數量、數值統計、文字樣本、分類最大群組。"""
    rows_raw = fetch("SELECT row_idx, payload FROM gov_rows WHERE nid=? ORDER BY row_idx", (nid,))
    rows = [(r["row_idx"], json.loads(r["payload"])) for r in rows_raw]
    if not rows:
        ds = fetch_one("SELECT * FROM gov_datasets WHERE nid=?", (nid,))
        return {"analyzed": False, "note": "尚未匯入內容", "dataset": dict(ds) if ds else None}
    cols = list(rows[0][1].keys())
    col_stats = {}
    for c in cols:
        values = [r[1].get(c, "") for r in rows]
        nonempty = [v for v in values if str(v).strip() != ""]
        numeric = []
        for v in nonempty:
            try:
                numeric.append(float(v))
            except (TypeError, ValueError):
                continue
        sample_values = list(dict.fromkeys(nonempty))[:5]
        item = {
            "count": len(nonempty),
            "unique": len(set(nonempty)),
            "sample": sample_values,
        }
        if numeric and len(numeric) >= len(nonempty) * 0.9:
            item["type"] = "number"
            item["min"] = min(numeric)
            item["max"] = max(numeric)
            item["sum"] = round(sum(numeric), 2)
            item["avg"] = round(sum(numeric) / len(numeric), 2)
        else:
            item["type"] = "text"
        col_stats[c] = item
    best_group = None
    best_key = None
    for c in cols:
        from collections import Counter
        if len(cols) < 2:
            break
        cnt = Counter((str(r[1].get(c, "")).strip() for r in rows))
        if cnt and len(cnt) < len(rows) and cnt.most_common(1)[0][1] >= max(2, len(rows) * 0.01):
            if best_group is None or len(cnt) > len(Counter((str(r[1].get(best_key, "")).strip() for r in rows))):
                best_key = c
                top = cnt.most_common(6)
                best_group = [{"value": v, "count": n} for v, n in top]
    return {
        "analyzed": True,
        "nid": nid,
        "rows": len(rows),
        "columns": cols,
        "column_stats": col_stats,
        "top_group_column": best_key,
        "top_group": best_group,
    }


def search(q: str, page: int = 1, per_page: int = 20) -> dict:
    like = f"%{q}%"
    total = fetch_one(
        "SELECT COUNT(*) AS c FROM gov_catalog WHERE title LIKE ? OR agency LIKE ? "
        "OR category LIKE ? OR topic LIKE ? OR description LIKE ?",
        [like, like, like, like, like],
    )["c"]
    offset = (page - 1) * per_page
    rows = fetch(
        "SELECT nid, title, agency, category, freq, formats, qty, dl_url, description, view_times "
        "FROM gov_catalog WHERE title LIKE ? OR agency LIKE ? OR category LIKE ? OR topic LIKE ? "
        "OR description LIKE ? ORDER BY view_times DESC LIMIT ? OFFSET ?",
        [like, like, like, like, like, per_page, offset],
    )
    return {
        "q": q,
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows],
    }


def ask(q: str) -> dict:
    """問答式查詢：先搜目錄，再視 GROQ 有無設定組出摘要。"""
    found = search(q, per_page=5)
    if not found["total"]:
        return {"ok": True, "answer": f"沒有找到與「{q}」相關的開放資料集。", "datasets": []}
    titles = "\n".join(f"- {it['title']}（{it['agency']}，格式 {it['formats']}）" for it in found["items"])
    if not GROQ_API_KEY:
        return {"ok": True, "answer": "找到以下資料集，可用 /govdata 頁面瀏覽與分析。\n" + titles, "datasets": found["items"]}
    try:
        import groq
        client = groq.Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是台灣開放資料助理。依資料集清單回答使用者問題；列出最相關資料集、提供機關與資料格式。",
                },
                {"role": "user", "content": f"問題：{q}\n\n資料集清單：\n{titles}"},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        answer = resp.choices[0].message.content.strip()
        return {"ok": True, "answer": answer, "datasets": found["items"]}
    except Exception as e:
        logger.warning(f"govdata ask groq failed: {e}")
        return {"ok": True, "answer": "找到以下資料集，可用 /govdata 頁面瀏覽與分析。\n" + titles, "datasets": found["items"]}


def status() -> dict:
    from collections import Counter
    total = fetch_one("SELECT COUNT(*) AS c FROM gov_catalog")["c"]
    ingested = fetch_one("SELECT COUNT(*) AS c FROM gov_datasets WHERE status='ok'")["c"]
    failed = fetch_one("SELECT COUNT(*) AS c FROM gov_datasets WHERE status='failed'")["c"]
    rows_stored = fetch_one("SELECT COUNT(*) AS c FROM gov_rows")["c"]
    by_format = Counter()
    for r in fetch("SELECT formats FROM gov_catalog LIMIT 20000"):
        for f in (r["formats"] or "").replace(";", ",").split(","):
            f = f.strip()
            if f:
                by_format[f] = by_format.get(f, 0) + 1
    top_orgs = [
        dict(r) for r in fetch(
            "SELECT agency, COUNT(*) AS c FROM gov_catalog GROUP BY agency ORDER BY c DESC LIMIT 10"
        )
    ]
    return {
        "catalog_total": total,
        "ingested": ingested,
        "failed": failed,
        "rows_stored": rows_stored,
        "top_orgs": top_orgs,
        "top_formats": [{"fmt": k, "count": v} for k, v in by_format.most_common(8)],
    }