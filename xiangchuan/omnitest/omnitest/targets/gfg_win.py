"""Target profile: GFG GAMES (https://gfg.win) — Vue3 SPA game portal.

Discovered structure:
  routes   #/  #/games  #/gameInfo/:id  #/game/:id  #/about
  APIs     POST /ow/getGameList | getGameFilters | getGameDetail |
           getGameUrl | getHome | getNews | getPopularGame | getTopWins
           header `language: <locale>` + body {language:"en_us", ...}
  demo     site ships a built-in demo player `40120_player777`; getGameUrl
           returns a provider iframe URL (JWT) used by #/game/:id
"""
from omnitest.core.config import Endpoint, LoginProfile, Target


def _ok_code0(d):
    return d.get("code") == 0


TARGET = Target(
    name="gfg_win",
    base_url="https://gfg.win",
    api_base="https://gfg.win",
    seed_paths=[
        "/",                      # home shell
        "/#/games",
        "/#/gameInfo/300001",
        "/#/game/300001",
        "/#/about",
    ],
    global_headers={"language": "US"},
    endpoints=[
        Endpoint(name="home",       method="POST", path="/ow/getHome",         json_body={"language": "en_us"}, success_check=_ok_code0),
        Endpoint(name="game-list",  method="POST", path="/ow/getGameList",     json_body={"language": "en_us"}, success_check=_ok_code0, weight=3),
        Endpoint(name="game-filters", method="POST", path="/ow/getGameFilters", json_body={"language": "en_us"}, success_check=_ok_code0),
        Endpoint(name="game-detail", method="POST", path="/ow/getGameDetail",  json_body={"language": "en_us", "gameId": 300001}, success_check=_ok_code0),
        Endpoint(name="game-url",    method="POST", path="/ow/getGameUrl",
                 json_body={"language": "en_us", "gameId": 300001,
                            "account": "40120_player777"}, success_check=_ok_code0),
        Endpoint(name="popular",    method="POST", path="/ow/getPopularGame",  json_body={"language": "en_us"}, success_check=_ok_code0),
        Endpoint(name="top-wins",   method="POST", path="/ow/getTopWins",      json_body={"language": "en_us"}, success_check=_ok_code0, weight=2),
        Endpoint(name="news",       method="POST", path="/ow/getNews",         json_body={"language": "en_us"}, success_check=_ok_code0),
    ],
    login=LoginProfile(
        # the SPA's own demo-account flow: getGameUrl issues a session-scoped
        # provider URL — used here as the "login" handshake for load storms.
        url="https://gfg.win/ow/getGameUrl",
        method="POST",
        username_field="account",
        password_field="__unused__",
        extra_body={"gameId": 300001},
        success_path="code",
        success_value=0,
        token_path="data.url",
        username_pattern="40120_player{n}",
        heartbeat_path="/ow/getTopWins",
        heartbeat_method="POST",
        heartbeat_body={"language": "en_us"},
        heartbeat_interval=15,
    ),
    authorized_domains=["gfg.win"],
    games_list_endpoint="game-list",
    games_detail_endpoint="game-detail",
    games_url_endpoint="game-url",
    games_account="40120_player777",   # SPA's built-in demo player
    console_error_allowlist=[
        r"favicon",
        r"net::ERR_(BLOCKED_BY_CLIENT|FAILED).*?(analytics|gtag|facebook|doubleclick)",
        r"cloudfront.*(403|404)",
    ],
    human_sim_allow_submit=False,
    max_crawl_pages=120,
    notes="Demo/QA portal of GFG GAMES. Heavy tests authorized per signed scope.",
)
