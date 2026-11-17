"""名單收集：Email 訂閱與每週自動內容彙整。"""
from marketing_system.database import execute, fetch, fetch_one


def _subscribe(client, email: str = "fan@example.com") -> dict:
    r = client.post("/api/subscribe", json={"email": email, "source": "test"})
    return r.json()


def test_subscribe_creates_and_dedupes(client):
    assert _subscribe(client, "newfan@example.com")["subscribed"] is True
    assert _subscribe(client, "newfan@example.com")["subscribed"] is True
    # Email 不分大小寫，同一筆不會重複
    assert _subscribe(client, "NEWFAN@example.com")["subscribed"] is True
    total = fetch_one("SELECT COUNT(*) AS c FROM subscribers")["c"]
    assert total == 1


def test_subscribe_rejects_invalid_email(client):
    r = client.post("/api/subscribe", json={"email": "not-an-email", "source": "test"})
    assert r.status_code == 400


def test_subscriber_count_endpoint(client):
    _subscribe(client, "counter@example.com")
    r = client.get("/api/subscribers/count")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_admin_subscribers_requires_admin(client):
    assert client.get("/api/admin/subscribers").status_code == 401
