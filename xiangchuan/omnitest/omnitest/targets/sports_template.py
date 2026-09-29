"""Target profile template: 體育投注平台 (Sports betting platform).

Replace base_url, endpoints, and field names with your actual sports betting site.

Typical sports betting structure:
  - Event list API: returns sports categories / live events
  - Event detail API: returns odds, teams, match status
  - Play page: native SPA with live odds display
  - Observation: odds change monitoring, live score updates
"""
from omnitest.core.config import Endpoint, Target


def _ok(d):
    return d.get("code") in (0, 200) or "data" in d


# ──────────────────────────────────────────────
#  TEMPLATE: replace URLs and field names below
# ──────────────────────────────────────────────
TARGET = Target(
    name="sports_template",
    base_url="https://YOUR_SPORTS_SITE.com",
    api_base="https://YOUR_SPORTS_SITE.com",
    seed_paths=[
        "/",
        "/#/sports",
        "/#/event/1",       # example event page
        "/#/live",
        "/#/coupon",        # bet slip
        "/#/about",
    ],
    global_headers={"Accept": "application/json", "language": "en"},
    endpoints=[
        # --- 賽事列表 API：取得體育種類 / 即時賽事 ---
        Endpoint(name="event-list", method="POST",
                 path="/api/getEventList",
                 json_body={"language": "en", "sportId": 0},
                 success_check=_ok),
        # --- 賽事詳情 API：取得賠率、隊伍、比賽狀態 ---
        Endpoint(name="event-detail", method="POST",
                 path="/api/getEventDetail",
                 json_body={"language": "en", "eventId": 0},
                 success_check=_ok),
        # --- 賠率 API（即時更新） ---
        Endpoint(name="odds-update", method="POST",
                 path="/api/getOdds",
                 json_body={"language": "en", "eventId": 0},
                 success_check=_ok),
    ],
    # ── games 模組設定（通用掃描器） ──
    games_list_endpoint="event-list",
    games_detail_endpoint="event-detail",
    games_url_endpoint="",             # 體育投注不需要外部播放 URL
    games_catalog_path="data.events",  # JSON dot-path: response.data.events → [{eventId, eventName}]
    games_id_field="eventId",
    games_name_field="eventName",
    games_play_type="native",          # 賽事頁面是原生 SPA
    games_play_selector=".event-container, .match-view, .live-player, main",
    games_info_selector=".event-info, .match-detail, main",
    games_observation="odds",          # 觀測賠率變化
    games_detail_extra_fields=["homeTeam", "awayTeam", "matchTime"],
    console_error_allowlist=[r"favicon", r"analytics"],
    human_sim_allow_submit=True,       # 允許模擬下注流程
    notes="Template for sports betting platforms. Replace base_url and endpoint paths.",
)
