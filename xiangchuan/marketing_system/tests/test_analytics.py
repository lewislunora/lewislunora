from datetime import datetime, timedelta

from marketing_system.database import execute, fetch_one
from marketing_system.services.analytics import summary


def test_recent_pageview_is_counted():
    """visited_at 是 SQLite UTC（空白分隔），summary 的 cutoff 必須用同格式比較。

    回歸測試：先前用 datetime.now().isoformat()（帶 T、台北時間），
    導致同一天的 PV 永遠被排除，近 24h 恆為 0。
    """
    execute("INSERT INTO page_views (page) VALUES (?)", ["/regression-test"])
    data = summary(since_hours=24)
    assert data["total"] == 1
    assert data["pages"][0]["page"] == "/regression-test"


def test_old_pageview_is_excluded_from_recent_window():
    old = (datetime.utcnow() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "INSERT INTO page_views (page, visited_at) VALUES (?, ?)",
        ["/old-page", old],
    )
    assert summary(since_hours=24)["total"] == 0
    assert summary(since_hours=20000)["total"] == 1
