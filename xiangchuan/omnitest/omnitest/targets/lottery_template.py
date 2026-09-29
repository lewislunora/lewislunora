"""Target profile template: 彩票平台 (Lottery platform).

Replace base_url, endpoints, and field names with your actual lottery site.

Typical lottery platform structure:
  - Game list API: returns draw IDs / lottery types
  - Draw detail API: returns draw number, draw time, results
  - Play page: native SPA (no iframe), number selection UI
  - Observation: draw countdown timer, result updates via WebSocket
"""
from omnitest.core.config import Endpoint, Target


def _ok(d):
    return d.get("code") in (0, 200) or "data" in d


# ──────────────────────────────────────────────
#  TEMPLATE: replace URLs and field names below
# ──────────────────────────────────────────────
TARGET = Target(
    name="lottery_template",
    base_url="https://YOUR_LOTTERY_SITE.com",
    api_base="https://YOUR_LOTTERY_SITE.com",
    seed_paths=[
        "/",
        "/#/lottery",
        "/#/draw/1",        # example draw page
        "/#/result",
        "/#/about",
    ],
    global_headers={"Accept": "application/json", "language": "en"},
    endpoints=[
        # --- 列表 API：取得彩票種類 / 期號列表 ---
        Endpoint(name="draw-list", method="POST",
                 path="/api/getDrawList",
                 json_body={"language": "en"},
                 success_check=_ok),
        # --- 詳情 API：取得某一期的開獎資訊 ---
        Endpoint(name="draw-detail", method="POST",
                 path="/api/getDrawDetail",
                 json_body={"language": "en", "drawId": 0},
                 success_check=_ok),
        # --- 開獎結果 API（即時推送或輪詢） ---
        Endpoint(name="draw-result", method="POST",
                 path="/api/getDrawResult",
                 json_body={"language": "en", "drawId": 0},
                 success_check=_ok),
    ],
    # ── games 模組設定（通用掃描器） ──
    games_list_endpoint="draw-list",
    games_detail_endpoint="draw-detail",
    games_url_endpoint="",             # 彩票通常不需要外部播放 URL
    games_catalog_path="data.draws",   # JSON dot-path: response.data.draws → [{drawId, drawName}]
    games_id_field="drawId",
    games_name_field="drawName",
    games_play_type="native",          # 彩票選號頁面是原生 SPA
    games_play_selector=".draw-container, .lottery-board, main",
    games_info_selector=".draw-info, .lottery-detail, main",
    games_observation="ws",            # 觀測 WebSocket（開獎推送）
    games_detail_extra_fields=["drawTime", "drawNumber"],
    console_error_allowlist=[r"favicon", r"analytics"],
    notes="Template for lottery platforms. Replace base_url and endpoint paths.",
)
