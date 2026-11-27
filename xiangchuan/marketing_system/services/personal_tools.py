"""個人工具：計算、筆記、提醒。

owner 格式固定為 ``user:<id>``（網站登入）或 ``chat:<chat_id>``（Telegram），
所有讀寫都帶 owner，避免跨用戶／跨群存取。
"""
import ast
import logging
import math
import operator
import re
from datetime import datetime, timedelta

from ..database import execute, fetch, fetch_one

logger = logging.getLogger(__name__)

MAX_EXPR = 200
MAX_NOTE = 4000


# ── 計算：白名單 AST，不用 eval ────────────────────────────────────
_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    name: getattr(math, name)
    for name in ("sqrt", "sin", "cos", "tan", "log", "log10", "exp",
                 "floor", "ceil", "fabs")
}
_FUNCS["round"] = round
_CONST = {"pi": math.pi, "e": math.e}


def _calc_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("只支援數字")
        return node.value
    if isinstance(node, ast.BinOp):
        left, right = _calc_node(node.left), _calc_node(node.right)
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise ValueError("不支援的運算子")
        if isinstance(node.op, ast.Pow):
            if abs(right) > 100 or abs(left) > 1e6:
                raise ValueError("指數太大")
        try:
            return op(left, right)
        except (ZeroDivisionError, OverflowError, ValueError) as e:
            raise ValueError(str(e))
    if isinstance(node, ast.UnaryOp):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError("不支援的運算子")
        return op(_calc_node(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _CONST:
            return _CONST[node.id]
        raise ValueError(f"不支援的名稱：{node.id}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ValueError("不支援的函數")
        args = [_calc_node(a) for a in node.args]
        if node.keywords or not 1 <= len(args) <= 2 or (len(args) == 2 and node.func.id != "round"):
            raise ValueError("函數參數不正確")
        try:
            return _FUNCS[node.func.id](*args)
        except (OverflowError, ValueError) as e:
            raise ValueError(str(e))
    raise ValueError("不支援的語法（可用 + - * / % ** 與 sqrt/log/sin/cos 等）")


def calculate(expression: str) -> str:
    """安全的四則運算；回傳格式化後的字串。"""
    expr = (expression or "").strip()
    if not expr:
        raise ValueError("請輸入運算式")
    if len(expr) > MAX_EXPR:
        raise ValueError(f"運算式過長（最多 {MAX_EXPR} 字）")
    expr = expr.replace("^", "**")  # 常見的指數寫法
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ValueError("運算式格式不正確")
    value = _calc_node(tree.body)
    if isinstance(value, complex) or abs(value) > 1e15:
        raise ValueError("結果太大或不支援")
    return f"{value:.10g}"


def owner_for_user(user_id) -> str:
    return f"user:{user_id}"


def owner_for_chat(chat_id) -> str:
    return f"chat:{chat_id}"


# ── 筆記 ──────────────────────────────────────────────────────────
def get_note(owner: str, note_id):
    return fetch_one(
        "SELECT id, content, tags, created_at, updated_at FROM notes WHERE id=? AND owner=?",
        [note_id, owner],
    )


def add_note(owner: str, content: str, tags: str = "") -> dict:
    content = (content or "").strip()
    if not content:
        raise ValueError("請輸入筆記內容")
    if len(content) > MAX_NOTE:
        raise ValueError(f"筆記最多 {MAX_NOTE} 字")
    nid = execute(
        "INSERT INTO notes (owner, content, tags) VALUES (?,?,?)",
        [owner, content, (tags or "")[:200]],
    )
    return get_note(owner, nid)


def list_notes(owner: str, q: str = "", limit: int = 20) -> list:
    limit = min(max(int(limit or 20), 1), 50)
    if q:
        like = f"%{q}%"
        return fetch(
            "SELECT id, content, tags, created_at, updated_at FROM notes "
            "WHERE owner=? AND (content LIKE ? OR tags LIKE ?) "
            "ORDER BY updated_at DESC, id DESC LIMIT ?",
            [owner, like, like, limit],
        )
    return fetch(
        "SELECT id, content, tags, created_at, updated_at FROM notes "
        "WHERE owner=? ORDER BY updated_at DESC, id DESC LIMIT ?",
        [owner, limit],
    )


def delete_note(owner: str, note_id) -> bool:
    # execute() 只回 lastrowid，DELETE 無法用它判斷是否真的刪到資料。
    if not get_note(owner, note_id):
        return False
    execute("DELETE FROM notes WHERE id=? AND owner=?", [note_id, owner])
    return True


# ── 提醒 ──────────────────────────────────────────────────────────
_UNITS = {
    "秒": 1, "分鐘": 60, "分": 60, "小時": 3600, "時": 3600,
    "天": 86400, "日": 86400, "週": 604800,
}


def parse_due(value, now: datetime = None) -> datetime:
    """接受 ``YYYY-MM-DD HH:MM``、``10分鐘後`` 等格式。"""
    now = now or datetime.now()
    if isinstance(value, datetime):
        return value
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    m = re.match(r"^(\d+)\s*(秒|分鐘|分|小時|時|天|日|週)\s*後?$", s)
    if m:
        return now + timedelta(seconds=int(m.group(1)) * _UNITS[m.group(2)])
    raise ValueError("時間格式不正確（例：2026-11-28 10:00 或 30分鐘後）")


def get_reminder(owner: str, rid):
    return fetch_one(
        "SELECT id, text, due_at, status, chat_id, created_at FROM reminders WHERE id=? AND owner=?",
        [rid, owner],
    )


def add_reminder(owner: str, text: str, due_at, chat_id: str = "") -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("請輸入提醒內容")
    due = parse_due(due_at)
    if due <= datetime.now():
        raise ValueError("提醒時間必須在未來")
    rid = execute(
        "INSERT INTO reminders (owner, chat_id, text, due_at) VALUES (?,?,?,?)",
        [owner, str(chat_id or ""), text[:500], due.strftime("%Y-%m-%d %H:%M:%S")],
    )
    return get_reminder(owner, rid)


def list_reminders(owner: str, limit: int = 20) -> list:
    limit = min(max(int(limit or 20), 1), 50)
    return fetch(
        "SELECT id, text, due_at, status, created_at FROM reminders "
        "WHERE owner=? ORDER BY status='pending' DESC, due_at ASC LIMIT ?",
        [owner, limit],
    )


def cancel_reminder(owner: str, rid) -> bool:
    row = fetch_one("SELECT status FROM reminders WHERE id=? AND owner=?", [rid, owner])
    if not row or row["status"] != "pending":
        return False
    execute("UPDATE reminders SET status='cancelled' WHERE id=? AND owner=?", [rid, owner])
    return True


def due_reminders(limit: int = 50) -> list:
    return fetch(
        "SELECT id, chat_id, text, due_at, attempts FROM reminders "
        "WHERE status='pending' AND due_at<=datetime('now') ORDER BY due_at ASC LIMIT ?",
        [limit],
    )


def take_due(owner: str) -> list:
    """網站用：取出該用戶已到期的提醒並標為已通知（前端輪詢）。"""
    rows = fetch(
        "SELECT id, text, due_at FROM reminders "
        "WHERE owner=? AND status='pending' AND due_at<=datetime('now') "
        "ORDER BY due_at ASC LIMIT 20",
        [owner],
    )
    if rows:
        marks = ",".join("?" for _ in rows)
        execute(
            f"UPDATE reminders SET status='sent', sent_at=datetime('now') WHERE id IN ({marks})",
            [r["id"] for r in rows],
        )
    return rows


def _finish(ids, status="sent", postpone_minutes=0):
    if not ids:
        return
    marks = ",".join("?" for _ in ids)
    if postpone_minutes:
        execute(
            f"UPDATE reminders SET status='pending', attempts=attempts+1, "
            f"due_at=datetime(due_at, '+' || ? || ' minutes') WHERE id IN ({marks})",
            [postpone_minutes, *ids],
        )
    else:
        execute(
            f"UPDATE reminders SET status=?, sent_at=datetime('now') WHERE id IN ({marks})",
            [status, *ids],
        )


def dispatch_due(send_fn=None) -> dict:
    """背景呼叫：到期的提醒發 Telegram，失敗最多重試 3 次。"""
    rows = due_reminders()
    sent, failed, retried = [], [], []
    for row in rows:
        ok = True
        if row["chat_id"]:
            try:
                if send_fn:
                    ok = send_fn(row["chat_id"], f"⏰ 提醒：{row['text']}")
                else:
                    import requests
                    import os
                    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                    resp = requests.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": row["chat_id"], "text": f"⏰ 提醒：{row['text']}"},
                        timeout=15,
                    )
                    ok = bool(resp.ok)
            except Exception as e:
                logger.warning(f"reminder send failed: {e}")
                ok = False
        if ok:
            sent.append(row["id"])
        elif (row["attempts"] or 0) + 1 >= 3:
            failed.append(row["id"])
        else:
            retried.append(row["id"])
    _finish(sent, "sent")
    _finish(failed, "failed")
    _finish(retried, "pending", postpone_minutes=1)
    return {"sent": len(sent), "failed": len(failed), "retried": len(retried)}
