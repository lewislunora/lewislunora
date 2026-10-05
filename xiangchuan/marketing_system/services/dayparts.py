"""每日內容的「時段」排程（台灣時間）。

問題背景
- 內容引擎原本每 15 分鐘檢查一次，但 Render 容器時區是 UTC，
  「今天」的切換點落在台灣早上 8 點，導致每日內容全部集中在早上產出，
  使用者感受不到「上午／中午／下午／晚上」的節奏。
- 這裡改用 Asia/Taipei 計算時段，讓內容分散到各時段，並保留補產機制
  （若某時段因服務休眠錯過，下一輪會補產，當日產量不減）。

資料表 daily_slots(kind, slot, day) 記錄「哪一類內容、哪個時段、哪一天已經產過」。
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ..database import execute, fetch, fetch_one

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Taipei")

# (key, 標籤, 圖示, 開始小時, 結束小時)  結束小時 24 表示當日 23:59
SLOTS = [
    ("dawn", "清晨", "🌅", 5, 8),
    ("morning", "上午", "🌤️", 8, 12),
    ("noon", "中午", "🍚", 12, 14),
    ("afternoon", "下午", "🌞", 14, 18),
    ("evening", "傍晚", "🌆", 18, 21),
    ("night", "夜晚", "🌙", 21, 24),
]

# 每一類內容排在哪幾個時段產出
SLOT_PLAN = {
    "short": ["dawn", "noon", "evening"],   # 短文：清晨／中午／傍晚
    "seo": ["morning"],                     # 長文：上午
    "novel": ["morning", "evening"],        # 小說：上午一更、傍晚一更
}


def now_tw() -> datetime:
    return datetime.now(TZ)


def today_tw() -> str:
    return now_tw().strftime("%Y-%m-%d")


def current_slot(now: datetime | None = None) -> dict:
    now = now or now_tw()
    h = now.hour
    for key, label, icon, start, end in SLOTS:
        if start <= h < end:
            return {"key": key, "label": label, "icon": icon}
    return {"key": "night", "label": "夜晚", "icon": "🌙"}


def _slot_bounds(key: str) -> tuple[int, int]:
    for k, _label, _icon, start, end in SLOTS:
        if k == key:
            return start, end
    return 0, 24


def done_slots(kind: str, day: str | None = None) -> set:
    day = day or today_tw()
    return {
        r["slot"]
        for r in fetch("SELECT slot FROM daily_slots WHERE kind=? AND day=?", [kind, day])
    }


def mark_slot(kind: str, slot: str, day: str | None = None) -> None:
    day = day or today_tw()
    execute(
        "INSERT OR IGNORE INTO daily_slots (kind,slot,day,at) VALUES (?,?,?,datetime('now'))",
        [kind, slot, day],
    )


def should_run(kind: str, now: datetime | None = None) -> dict:
    """判斷現在該不該為這類內容產出。

    回傳 {run: bool, slot: str, reason: str}
    - 目前時段在計畫內且今天還沒產過 → 產
    - 計畫中的時段已結束卻沒產過（服務當時休眠）→ 立刻補產，當日產量不減
    """
    plan = SLOT_PLAN.get(kind)
    now = now or now_tw()
    cur = current_slot(now)
    if not plan:
        return {"run": True, "slot": cur["key"], "reason": "無時段設定"}
    done = done_slots(kind)
    h = now.hour
    # 1) 當前時段正好在計畫內且尚未產出
    if cur["key"] in plan and cur["key"] not in done:
        return {"run": True, "slot": cur["key"],
                "reason": f"{cur['icon']} {cur['label']}時段"}
    # 2) 補產：已結束卻沒產出的時段（服務休眠時錯過）
    for s in plan:
        start, end = _slot_bounds(s)
        if s in done:
            continue
        if end <= h or (start <= h < end and s == cur["key"]):
            return {"run": True, "slot": s, "reason": f"補產錯過的 {s} 時段"}
    return {"run": False, "slot": cur["key"],
            "reason": f"目前 {cur['icon']}{cur['label']}，不在 {kind} 排程時段或今日已產過"}


def overview() -> dict:
    """給後台／狀態 API 看：今天各時段產了什麼、下一個時段是什麼。"""
    day = today_tw()
    now = now_tw()
    rows = fetch(
        "SELECT kind,slot,at FROM daily_slots WHERE day=? ORDER BY at", [day]
    )
    return {
        "tz": "Asia/Taipei",
        "now_tw": now.strftime("%Y-%m-%d %H:%M"),
        "current": current_slot(now),
        "plan": SLOT_PLAN,
        "done": [{"kind": r["kind"], "slot": r["slot"], "at": r["at"]} for r in rows],
        "pending": {
            kind: [s for s in plan if s not in {x["slot"] for x in rows if x["kind"] == kind}]
            for kind, plan in SLOT_PLAN.items()
        },
    }