"""Target profile: GitHub (https://github.com) — public code hosting, light modules only."""
from omnitest.core.config import Endpoint, Target

TARGET = Target(
    name="github",
    base_url="https://github.com",
    api_base="https://api.github.com",
    seed_paths=[
        "/",
        "/features/actions",
        "/features/copilot",
        "/pricing",
        "/login",
    ],
    global_headers={"Accept": "application/json"},
    endpoints=[
        Endpoint(name="api-repo", method="GET",
                 path="/repos/octocat/Hello-World",
                 success_check=lambda d: d.get("full_name") == "octocat/Hello-World"),
        Endpoint(name="api-user", method="GET",
                 path="/users/octocat",
                 success_check=lambda d: d.get("login") == "octocat"),
        Endpoint(name="api-search", method="GET",
                 path="/search/repositories?q=omnitest+language:python&sort=stars&per_page=3",
                 success_check=lambda d: "items" in d),
    ],
    console_error_allowlist=[
        r"favicon",
        r"githubassets",
    ],
    human_sim_allow_submit=False,
    notes="Public GitHub pages; light modules only (no login-storm, no load).",
)
