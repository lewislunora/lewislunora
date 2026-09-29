from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Endpoint:
    """A single API call definition used by api/value/load modules."""

    name: str
    method: str = "POST"
    url: str = ""                      # absolute URL; if empty -> api_base + path
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    expect_status: tuple[int, ...] = (200,)
    success_check: Callable[[dict], bool] | None = None   # envelope check, e.g. code==0
    weight: float = 1.0                # relative frequency inside load scenarios


@dataclass
class LoginProfile:
    """Parameterised login used by login-storm / authenticated scenarios."""

    url: str = ""
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    username_field: str = "account"
    password_field: str = "password"
    extra_body: dict[str, Any] = field(default_factory=dict)
    success_path: str = "code"         # dot-path to success flag
    success_value: Any = 0
    token_path: str = "data.url"       # dot-path to session token/url (optional)
    username_pattern: str = "40120_player{n}"   # {n} substituted
    password: str = ""
    heartbeat_path: str = ""           # optional keep-alive call during session hold
    heartbeat_method: str = "POST"
    heartbeat_body: dict[str, Any] = field(default_factory=dict)
    heartbeat_interval: float = 30.0


@dataclass
class Target:
    """Everything OMNITEST needs to know about one site."""

    name: str
    base_url: str
    seed_paths: list[str] = field(default_factory=list)      # pages incl. SPA hash routes
    api_base: str = ""                                       # default: base_url
    global_headers: dict[str, str] = field(default_factory=dict)
    endpoints: list[Endpoint] = field(default_factory=list)
    login: LoginProfile | None = None
    authorized_domains: list[str] = field(default_factory=list)
    console_error_allowlist: list[str] = field(default_factory=list)  # regex list
    max_crawl_pages: int = 200
    human_sim_allow_submit: bool = False
    notes: str = ""
    # --- per-game sweep (module "games") ---
    games_list_endpoint: str = ""    # Endpoint.name returning {"data":[{gameId,gameName},...]}
    games_detail_endpoint: str = ""  # Endpoint.name taking {"gameId": id}
    games_url_endpoint: str = ""     # Endpoint.name issuing playable URL {"gameId","account"}
    games_account: str = ""          # demo/test player account for url issuance
    # --- generalized game/product sweep ---
    games_catalog_path: str = "data"        # JSON dot-path to item list in list-API response
    games_id_field: str = "gameId"          # field name for unique ID in catalog items
    games_name_field: str = "gameName"      # field name for display name in catalog items
    games_play_type: str = "iframe"         # "iframe" | "video" | "canvas" | "native"
    games_play_selector: str = ""           # CSS selector for play area (auto-detected if empty)
    games_info_selector: str = ""           # CSS selector for detail page content
    games_observation: str = "traffic"      # "traffic" | "ws" | "odds" | "stream" | "none"
    games_detail_extra_fields: list[str] = field(default_factory=list)  # extra fields to validate in detail API

    def api_url(self, ep: Endpoint) -> str:
        if ep.url:
            return ep.url
        base = (self.api_base or self.base_url).rstrip("/")
        return f"{base}{ep.path}"


def parse_dot_path(path: str) -> list[Any]:
    out: list[Any] = []
    for part in path.split("."):
        if part.isdigit():
            out.append(int(part))
        else:
            out.append(part)
    return out


def dig(obj: Any, path: str, default: Any = None) -> Any:
    cur = obj
    for key in parse_dot_path(path):
        try:
            cur = cur[key]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return default
    return cur


HOST_RE = re.compile(r"^https?://([^/:?#]+)")


def host_of(url: str) -> str:
    m = HOST_RE.match(url.strip())
    return (m.group(1).lower() if m else "").removeprefix("www.")
