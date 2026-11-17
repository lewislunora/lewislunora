#!/usr/bin/env python3
"""AI 自動更新／調整網站的收集、提案、套用工具（翔川 Neo）。

設計原則：
- AI 只做「逐字符合的 old_text -> new_text」置換，不做整檔重寫。
- 有黑名單（DB／憑證／manifests／workflow／omnitest 等）與份量上限。
- 每次決策寫入 decisions.jsonl，下一次_run_用量表資料驗證效果，形成閉環。

用法：
  python ai_tuner.py collect   [--since 168] [--out PATH]
  python ai_tuner.py inventory [--out PATH]
  python ai_tuner.py propose   [--metrics PATH] [--inventory PATH] [--out PATH] [--dry-run]
  python ai_tuner.py apply     --proposals PATH [--yes] [--push] [--allow-medium] [--allow-high]
                              [--skip-tests] [--message TEXT] [--dry-run]
  python ai_tuner.py run       [--since 168] [--dry-run] [--push]
  python ai_tuner.py verify
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STATE_REL = Path("xiangchuan") / "ai-tuner"


# ────────────────────────────── 基礎工具 ──────────────────────────────

def log(msg: str) -> None:
    print(f"[ai-tuner] {msg}", flush=True)


def load_config() -> dict:
    path = REPO_ROOT / STATE_REL / "config.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def state_dir(config: dict | None = None) -> Path:
    cfg = config or load_config()
    return REPO_ROOT / cfg.get("state_dir", str(STATE_REL))


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def relpath(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def git(args: list[str], check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗：{proc.stderr.strip()}")
    return proc.stdout.strip()


def http_get(url: str, timeout: int = 25) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-tuner/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        log(f"GET 失敗 {url}: {exc}")
        return None


def probe(url: str) -> dict:
    started = _dt.datetime.now()
    result = {"url": url, "ok": False, "status": None, "seconds": None, "error": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-tuner/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read(2048)
            result["status"] = resp.status
            result["ok"] = 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
    except Exception as exc:  # noqa: BLE001 - 回報用
        result["error"] = str(exc)
    result["seconds"] = round((_dt.datetime.now() - started).total_seconds(), 2)
    return result


def today() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d")


# ────────────────────────────── 安全守門 ──────────────────────────────

def is_blocked(rel: str, config: dict) -> bool:
    for pattern in config.get("blocked_patterns", []):
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch("/" + rel, pattern):
            return True
        # 允許 "**/x/**" 這類目錄型規則
        trimmed = pattern.rstrip("*")
        if trimmed.endswith("/") and rel.startswith(trimmed.split("**/")[-1]):
            return True
    return False


def is_editable(rel: str, config: dict) -> tuple[bool, str]:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        return False, "路徑跳出 repo"
    roots = config.get("editable_roots", ["."])
    inside = any(root in (".", "") or rel == root or rel.startswith(root.rstrip("/") + "/") for root in roots)
    if not inside:
        return False, "不在可編輯根目錄"
    if is_blocked(rel, config):
        return False, "命中黑名單"
    if p.suffix.lower() not in config.get("allowed_extensions", []):
        return False, "副檔名不在允許清單"
    return True, ""


def content_fingerprint(file_rel: str, new_text: str) -> str:
    return hashlib.sha1(f"{file_rel}\0{new_text}".encode("utf-8")).hexdigest()


def recent_decisions(config: dict) -> list[dict]:
    path = state_dir(config) / "decisions.jsonl"
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    days = int(config.get("dedupe_days", 21))
    cutoff = _dt.datetime.now() - _dt.timedelta(days=days)
    fresh = []
    for row in rows:
        try:
            ts = _dt.datetime.fromisoformat(row.get("run_date", ""))
        except ValueError:
            continue
        if ts >= cutoff:
            fresh.append(row)
    return fresh


def already_done(fp: str, config: dict) -> bool:
    for row in recent_decisions(config):
        for act in row.get("actions", []):
            if act.get("fingerprint") == fp and act.get("status") == "applied":
                return True
    return False


# ────────────────────────────── collect ──────────────────────────────

def cmd_collect(args) -> int:
    config = load_config()
    base = config["api_base"].rstrip("/")
    since = args.since
    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "since_hours": since,
        "summary": http_get(f"{base}/api/analytics/summary?since={since}"),
        "summary_all_time": http_get(f"{base}/api/analytics/summary?since=20000"),
        "status": http_get(f"{base}/api/status"),
        "probes": [probe(url) for url in config.get("sites", [])],
    }
    out = Path(args.out) if args.out else state_dir(config) / "metrics" / f"{today()}.json"
    write_json(out, payload)
    s = payload.get("summary") or {}
    log(f"量表已寫入 {out.name}：近 {since}h PV={s.get('total')}、歷史 PV={s.get('total_all')}")
    for pr in payload["probes"]:
        log(f"  {pr['url']} -> {pr['status']} ({pr['seconds']}s)")
    return 0


# ────────────────────────────── inventory ──────────────────────────────

ROLE_RULES = [
    ("admin", "後台（AI 不改）"),
    ("community", "社群留存"),
    ("social", "社群／配對"),
    ("jobs", "找工作／找人才"),
    ("tasks", "任務牆"),
    ("money", "AI 商業點子"),
    ("calendar", "行事曆"),
    ("novels", "小說連載"),
    ("pricing", "價格／詢價轉換"),
    ("support", "支援／聯繫"),
    ("login", "會員登入"),
    ("register", "會員註冊"),
    ("govdata", "專業信任背書"),
    ("security-portfolio", "專業信任背書"),
    ("app", "App 下載"),
    ("flutter", "App 下載"),
]


def guess_role(rel: str) -> str:
    low = rel.lower()
    for key, role in ROLE_RULES:
        if key in low:
            return role
    if low.endswith("index.html"):
        return "首頁／轉換入口"
    return "內容頁"


def cmd_inventory(args) -> int:
    config = load_config()
    docs = REPO_ROOT / "docs"
    items = []
    for path in sorted(docs.rglob("*.html")):
        rel = relpath(path)
        if is_blocked(rel, config):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        title_m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
        desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', raw, re.I | re.S)
        if not desc_m:
            desc_m = re.search(r'content=["\'](.*?)["\'][^>]+name=["\']description["\']', raw, re.I | re.S)
        items.append({
            "path": rel,
            "role": guess_role(rel),
            "title": (title_m.group(1).strip() if title_m else "")[:120],
            "description": (desc_m.group(1).strip() if desc_m else "")[:200],
            "bytes": len(raw),
            "h1_count": len(re.findall(r"<h1[\s>]", raw, re.I)),
        })
    data = docs / "data"
    data_files = sorted(relpath(p) for p in data.glob("*.json")) if data.exists() else []
    payload = {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
               "pages": items, "data_files": data_files}
    out = Path(args.out) if args.out else state_dir(config) / "inventory.json"
    write_json(out, payload)
    log(f"庫存已寫入 {out.name}：{len(items)} 頁、{len(data_files)} 個 data JSON")
    return 0


# ────────────────────────────── Groq 呼叫 ──────────────────────────────

def strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return t


def extract_json(text: str) -> dict:
    t = strip_code_fence(text)
    candidates = [t]
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end > start:
        candidates.append(t[start : end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    # 平衡括號掃描（容忍內外夾帶文字）
    depth, in_str, esc, begin = 0, False, False, -1
    for i, ch in enumerate(t):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                begin = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and begin >= 0:
                try:
                    return json.loads(t[begin : i + 1])
                except json.JSONDecodeError:
                    begin = -1
    raise ValueError("AI 回應中找不到合法 JSON")


SYSTEM_PROMPT = """你是「翔川 Neo」官網的成長工程師，透過 GitHub Actions 定期自動調整網站。
目標：讓訪客一進站就能玩／用，並把使用者整合成統一自我品牌；最終導向詢價與註冊。

硬性規則：
1. 只能提出「逐字字串置換」：每个行動必须給 file、old_text、new_text，且 old_text 在該檔案中恰好出現一次（連空白、换行都要一致）。
2. 不可提案整檔重寫、新增檔案或刪除檔案。
3. 不可碰：資料庫、.env/金鑰/憑證/token、k8s manifests、terraform、.github/workflows、omnitest、marketing_system/data、任何 backup JSON。
4. 不可造假數據或流量數字；不可使用沒有依據的數字（既有的真實 API 數字除外）。
5. 單次最多 6 個行動，寧可少而準。優先做「可被搜尋、可被分享、可量測轉換」的小改版。
6. 要嘛不做（actions 空陣列），否則必须是有明確預期的行動。
7. 只可使用 inventory 裡存在的 file 路徑。

輸出格式（JSON）：
{
  "diagnosis": "依據量表的判斷（2-4 句）",
  "actions": [
    {
      "id": "a1",
      "file": "docs/index.html",
      "old_text": "原本檔案中逐字存在的片段",
      "new_text": "取代後的新片段",
      "risk": "low",
      "reason": "為什麼這樣改",
      "expected_effect": "可用哪個指標驗證"
    }
  ]
}
risk 只能是 low / medium / high。"""


def build_user_prompt(metrics: dict, inventory: dict, decisions: list[dict]) -> str:
    bundle = {
        "量測": {
            "近N小時PV": (metrics.get("summary") or {}).get("total"),
            "歷史PV": (metrics.get("summary_all_time") or {}).get("total_all"),
            "熱門頁": (metrics.get("summary_all_time") or {}).get("pages"),
            "國家": (metrics.get("summary_all_time") or {}).get("countries"),
            "站台狀態": [{"url": p.get("url"), "status": p.get("status"), "秒": p.get("seconds")}
                       for p in metrics.get("probes", [])],
            "後台狀態": (metrics.get("status") or {}).get("auto_engine"),
        },
        "網站庫存": [
            {"path": p["path"], "角色": p["role"], "標題": p["title"]}
            for p in inventory.get("pages", [])
        ],
        "前次決策": [
            {"日期": d.get("run_date"), "診斷": d.get("diagnosis"),
             "行動": [{"file": a.get("file"), "reason": a.get("reason")} for a in d.get("actions", [])]}
            for d in decisions[-8:]
        ],
    }
    return (
        "以下是本次收集的真實資料。請依 SYSTEM 規則輸出 JSON 決策。\n\n"
        + json.dumps(bundle, ensure_ascii=False, indent=2)
    )


def call_groq(user_prompt: str, config: dict) -> dict:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("環境變數 GROQ_API_KEY 未設定")
    body = {
        "model": config.get("model", "openai/gpt-oss-120b"),
        "temperature": float(config.get("temperature", 0.4)),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return extract_json(content)


def validate_action(act: dict, config: dict, decisions: list[dict]) -> tuple[bool, str]:
    file_rel = str(act.get("file", "")).strip().replace("\\", "/").lstrip("./")
    if not file_rel:
        return False, "缺少 file"
    ok, why = is_editable(file_rel, config)
    if not ok:
        return False, f"檔案不可編輯：{why}"
    path = REPO_ROOT / file_rel
    if not path.is_file():
        return False, "檔案不存在"
    old_text = act.get("old_text")
    new_text = act.get("new_text")
    if not isinstance(old_text, str) or not isinstance(new_text, str) or not old_text:
        return False, "old_text/new_text 必須是非空字串"
    if old_text == new_text:
        return False, "old_text 與 new_text 相同"
    if len(new_text.encode("utf-8")) > int(config.get("max_new_text_bytes", 20000)):
        return False, "new_text 過長"
    raw = path.read_text(encoding="utf-8", errors="replace")
    if raw.count(old_text) != 1:
        return False, f"old_text 在檔案中出現 {raw.count(old_text)} 次（必須恰好 1 次）"
    risk = str(act.get("risk", "low")).lower()
    if risk not in ("low", "medium", "high"):
        return False, "risk 必須是 low/medium/high"
    fp = content_fingerprint(file_rel, new_text)
    if already_done(fp, config):
        return False, "最近已套做過相同變更"
    return True, ""


# ────────────────────────────── propose ──────────────────────────────

def cmd_propose(args) -> int:
    config = load_config()
    if not config.get("enabled", True):
        log("tuner 停用中（config.enabled=false）")
        return 0
    metrics = read_json(Path(args.metrics)) if args.metrics else read_json(state_dir(config) / "metrics" / f"{today()}.json", {})
    inventory = read_json(Path(args.inventory)) if args.inventory else read_json(state_dir(config) / "inventory.json", {"pages": []})
    decisions = recent_decisions(config)
    plan = call_groq(build_user_prompt(metrics, inventory, decisions), config)
    actions = plan.get("actions") or []
    results = []
    for idx, act in enumerate(actions[: int(config.get("max_actions", 6))], start=1):
        act.setdefault("id", f"a{idx}")
        ok, why = validate_action(act, config, decisions)
        results.append({**act, "valid": ok, "reject_reason": "" if ok else why})
    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "diagnosis": plan.get("diagnosis", ""),
        "actions": results,
    }
    out = Path(args.out) if args.out else state_dir(config) / "proposals" / f"{today()}.json"
    write_json(out, payload)
    good = [a for a in results if a["valid"]]
    log(f"提案已寫入 {out.name}：有效 {len(good)}/{len(results)}")
    for a in results:
        flag = "OK " if a["valid"] else "SKIP"
        log(f"  [{flag}] {a.get('id')} {a.get('file')} :: {a.get('reason','')[:60]}")
        if not a["valid"]:
            log(f"        原因：{a['reject_reason']}")
    return 0


# ────────────────────────────── apply ──────────────────────────────

BACKUP_PATHS = ["docs/data/db_backup.json", "xiangchuan/marketing_system/data/test_backup.json"]


def restore_backups() -> None:
    for rel in BACKUP_PATHS:
        path = REPO_ROOT / rel
        if path.exists():
            git(["checkout", "--", rel], check=False)


def changed_lines(old_text: str, new_text: str) -> int:
    return abs(len(new_text.splitlines()) - len(old_text.splitlines())) + 1


def mirror_action(act: dict, config: dict) -> tuple[str | None, str]:
    """把同一個字串替換套到鏡像目錄；鏡像若已分岔（找不到 old_text）就跳過。

    交接鐵則：兩個 docs 目錄結構不同，不可整份覆蓋，所以只做等價字串替換。
    """
    for pair in config.get("sync_pairs", []):
        src_root = pair["from"].rstrip("/")
        dst_root = pair["to"].rstrip("/")
        rel = act["file"]
        if not (rel == src_root or rel.startswith(src_root + "/")):
            continue
        suffix = rel[len(src_root) + 1 :]
        dst_rel = f"{dst_root}/{suffix}"
        dst_path = REPO_ROOT / dst_rel
        if is_blocked(dst_rel, config):
            return None, "mirror_blocked"
        if not dst_path.is_file():
            return None, "mirror_missing"
        raw = dst_path.read_text(encoding="utf-8", errors="replace")
        if raw.count(act["old_text"]) != 1:
            return None, "mirror_diverged"
        dst_path.write_text(raw.replace(act["old_text"], act["new_text"], 1), encoding="utf-8")
        return dst_rel, "mirrored"
    return None, "no_pair"


def run_tests(config: dict) -> tuple[bool, str]:
    venv_python = REPO_ROOT / "xiangchuan" / "marketing_system" / "venv" / "bin" / "python"
    python = str(venv_python) if venv_python.exists() else sys.executable
    proc = subprocess.run(
        [python, "-m", "pytest", "marketing_system/tests", "-q", "--no-header"],
        cwd=REPO_ROOT / "xiangchuan", capture_output=True, text=True, timeout=900,
    )
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-12:])
    return proc.returncode == 0, tail


def cmd_apply(args) -> int:
    config = load_config()
    proposals = read_json(Path(args.proposals))
    if not proposals:
        log("沒有 proposals 檔案")
        return 1
    decisions = recent_decisions(config)
    allowed_risk = {"low"}
    if args.allow_medium:
        allowed_risk.add("medium")
    if args.allow_high and config.get("allow_high_risk"):
        allowed_risk.add("high")

    to_apply, skipped = [], []
    files_seen, lines_seen = set(), 0
    for act in proposals.get("actions", []):
        # 一律重新驗證，不信任 proposals 檔裡的 valid 旗標（可能被手改）
        ok, why = validate_action(act, config, decisions)
        if not ok:
            act["valid"], act["reject_reason"] = False, why
            skipped.append({"action": act, "status": "invalid"})
            continue
        if act.get("risk") not in allowed_risk:
            skipped.append({"action": act, "status": "risk_not_allowed"})
            continue
        cost = changed_lines(act["old_text"], act["new_text"])
        if len(files_seen | {act["file"]}) > int(config.get("max_files_per_run", 8)):
            skipped.append({"action": act, "status": "too_many_files"})
            continue
        if lines_seen + cost > int(config.get("max_changed_lines_per_run", 120)):
            skipped.append({"action": act, "status": "too_many_lines"})
            continue
        files_seen.add(act["file"])
        lines_seen += cost
        to_apply.append(act)

    log(f"預計套用 {len(to_apply)} 個行動（跳過 {len(skipped)}）")
    for item in skipped:
        log(f"  跳過 {item['action'].get('id')}：{item['status']}")

    if args.dry_run:
        print(json.dumps([{k: a.get(k) for k in ("id", "file", "risk", "reason")} for a in to_apply],
                         ensure_ascii=False, indent=2))
        log("dry-run：未寫入任何檔案")
        return 0
    if not to_apply:
        log("沒有可套用的行動")
        return 0
    if not args.yes:
        log("需要 --yes 才會實際寫入")
        return 2

    applied = []
    for act in to_apply:
        path = REPO_ROOT / act["file"]
        raw = path.read_text(encoding="utf-8", errors="replace")
        path.write_text(raw.replace(act["old_text"], act["new_text"], 1), encoding="utf-8")
        applied.append({**act, "status": "applied",
                        "fingerprint": content_fingerprint(act["file"], act["new_text"])})
        log(f"  已套用 {act['id']} -> {act['file']}")

    changed = sorted({a["file"] for a in applied})
    synced: list[str] = []
    for act in applied:
        dst, status = mirror_action(act, config)
        if dst:
            synced.append(dst)
        elif status not in ("no_pair",):
            log(f"  鏡像未套用 {act['file']}：{status}")
    log(f"已套用 {len(synced)} 個鏡像變更")

    restore_backups()

    if config.get("require_tests_pass", True) and not args.skip_tests:
        ok, tail = run_tests(config)
        if not ok:
            log("測試未通過，停止提交（修改仍留在工作區）:\n" + tail)
            return 3
        log("測試通過")

    decision_row = {
        "run_date": _dt.datetime.now().isoformat(timespec="seconds"),
        "diagnosis": proposals.get("diagnosis", ""),
        "actions": applied + [dict(item["action"], status=item["status"]) for item in skipped],
        "metrics_ref": f"{today()}.json",
    }
    with (state_dir(config) / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(decision_row, ensure_ascii=False) + "\n")

    if args.push:
        paths = changed + synced + [str(state_dir(config) / "decisions.jsonl")]
        git(["add", "--", *paths], check=False)
        msg = args.message or f"ai-tuner: 自動調整 {len(applied)} 項（{', '.join(changed[:3])}）"
        git(["commit", "-m", msg], check=False)
        git(["push", "origin", "main"], check=False)
        log("已提交並推送（會觸發 Render / GitHub Pages 部署）")
    else:
        log("未推送（--push 才會推送到 main 觸發部署）")
    return 0


# ────────────────────────────── report / run / verify ──────────────────────────────

def cmd_report(args) -> int:
    config = load_config()
    metrics = read_json(Path(args.metrics)) if args.metrics else {}
    proposals = read_json(Path(args.proposals)) if args.proposals else {}
    lines = [f"# AI Tuner 報告 {today()}", ""]
    s = (metrics.get("summary") or {})
    lines.append(f"- 近 {metrics.get('since_hours', '?')}h PV：{s.get('total')}；歷史 PV：{s.get('total_all')}")
    for p in metrics.get("probes", []):
        lines.append(f"- {p.get('url')}：HTTP {p.get('status')} / {p.get('seconds')}s")
    lines += ["", f"## 診斷", proposals.get("diagnosis", "(無)"), "", "## 行動"]
    for a in proposals.get("actions", []):
        mark = "✅" if a.get("valid") else "⛔"
        lines.append(f"- {mark} `{a.get('file')}` — {a.get('reason','')}")
        if not a.get("valid"):
            lines.append(f"  - 拒絕原因：{a.get('reject_reason')}")
    text = "\n".join(lines)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


def cmd_run(args) -> int:
    config = load_config()
    rc = cmd_collect(argparse.Namespace(since=args.since, out=None))
    if rc:
        return rc
    rc = cmd_inventory(argparse.Namespace(out=None))
    if rc:
        return rc
    rc = cmd_propose(argparse.Namespace(metrics=None, inventory=None, out=None, dry_run=False))
    if rc:
        return rc
    return cmd_apply(argparse.Namespace(
        proposals=str(state_dir(config) / "proposals" / f"{today()}.json"),
        yes=not args.dry_run,
        push=args.push and not args.dry_run,
        allow_medium=False, allow_high=False, skip_tests=False,
        message=None, dry_run=args.dry_run,
    ))


def cmd_verify(args) -> int:
    config = load_config()
    for url in config.get("sites", []):
        p = probe(url)
        log(f"{p['url']} -> HTTP {p['status']} ({p['seconds']}s) ok={p['ok']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 自動調整網站工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("collect")
    p.add_argument("--since", type=int, default=168)
    p.add_argument("--out")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("inventory")
    p.add_argument("--out")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("propose")
    p.add_argument("--metrics")
    p.add_argument("--inventory")
    p.add_argument("--out")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("apply")
    p.add_argument("--proposals", required=True)
    p.add_argument("--yes", action="store_true")
    p.add_argument("--push", action="store_true")
    p.add_argument("--allow-medium", action="store_true")
    p.add_argument("--allow-high", action="store_true")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--message")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("run")
    p.add_argument("--since", type=int, default=168)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--push", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report")
    p.add_argument("--metrics")
    p.add_argument("--proposals")
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("verify")
    p.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
