"""Target profile: Wikipedia (https://en.wikipedia.org) — public encyclopedia, light modules only."""
from omnitest.core.config import Endpoint, Target

TARGET = Target(
    name="wikipedia",
    base_url="https://en.wikipedia.org",
    api_base="https://en.wikipedia.org",
    seed_paths=[
        "/",
        "/wiki/Main_Page",
        "/wiki/Python_(programming_language)",
        "/wiki/Software_testing",
        "/wiki/Web_application",
    ],
    endpoints=[
        Endpoint(name="api-query", method="GET",
                 path="/w/api.php?action=query&format=json&titles=Main_Page&prop=info",
                 success_check=lambda d: "query" in d),
        Endpoint(name="api-search", method="GET",
                 path="/w/api.php?action=opensearch&format=json&search=Python&limit=5",
                 success_check=lambda d: isinstance(d, list) and len(d) >= 2),
    ],
    console_error_allowlist=[
        r"favicon",
        r"wikimedia",
    ],
    notes="Public static-content site; ideal for smoke/e2e/value/API validation.",
)
