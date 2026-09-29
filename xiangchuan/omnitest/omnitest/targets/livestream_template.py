"""Target profile template: 直播平台 (Live streaming platform).

Replace base_url, endpoints, and field names with your actual streaming site.

Typical live streaming structure:
  - Room list API: returns live rooms / streamers
  - Room detail API: returns stream URL, viewer count, status
  - Play page: <video> element with HLS/WebRTC player
  - Observation: stream health (playing/buffering/stalled), bitrate, latency
"""
from omnitest.core.config import Endpoint, Target


def _ok(d):
    return d.get("code") in (0, 200) or "data" in d


# ──────────────────────────────────────────────
#  TEMPLATE: replace URLs and field names below
# ──────────────────────────────────────────────
TARGET = Target(
    name="livestream_template",
    base_url="https://YOUR_STREAM_SITE.com",
    api_base="https://YOUR_STREAM_SITE.com",
    seed_paths=[
        "/",
        "/#/live",
        "/#/room/1",        # example room page
        "/#/categories",
        "/#/about",
    ],
    global_headers={"Accept": "application/json", "language": "en"},
    endpoints=[
        # --- 直播間列表 API：取得正在直播的房間 ---
        Endpoint(name="room-list", method="POST",
                 path="/api/getRoomList",
                 json_body={"language": "en", "page": 1, "size": 50},
                 success_check=_ok),
        # --- 直播間詳情 API：取得串流 URL、觀眾數 ---
        Endpoint(name="room-detail", method="POST",
                 path="/api/getRoomDetail",
                 json_body={"language": "en", "roomId": 0},
                 success_check=_ok),
        # --- 串流健康 API（可選） ---
        Endpoint(name="stream-health", method="GET",
                 path="/api/stream/health",
                 params={"roomId": 0},
                 success_check=_ok),
    ],
    # ── games 模組設定（通用掃描器） ──
    games_list_endpoint="room-list",
    games_detail_endpoint="room-detail",
    games_url_endpoint="",             # 直播間 URL 通常在詳情 API 裡
    games_catalog_path="data.rooms",   # JSON dot-path: response.data.rooms → [{roomId, roomName}]
    games_id_field="roomId",
    games_name_field="roomName",
    games_play_type="video",           # 直播播放器是 <video> 元素
    games_play_selector="video, .player video, .live-video, video.jwplayer",
    games_info_selector=".room-info, .streamer-info, main",
    games_observation="stream",        # 觀測串流健康（playing/buffering/stalled）
    games_detail_extra_fields=["streamUrl", "viewerCount", "status"],
    console_error_allowlist=[r"favicon", r"analytics", r"HLS.*error", r"MSE.*error"],
    notes="Template for live streaming platforms. Replace base_url and endpoint paths.",
)
