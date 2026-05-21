"""Database CRUD tests"""
import json
import pytest
from marketing_system.database import execute, fetch, fetch_one


class TestDatabaseCRUD:
    def test_init_creates_tables(self):
        rows = fetch("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r["name"] for r in rows]
        for t in ["accounts", "contents", "schedules", "analytics",
                   "ai_templates", "kb_entries", "kb_pending", "contacts", "users"]:
            assert t in tables, f"Missing table: {t}"

    def test_seed_data_loaded(self):
        templates = fetch("SELECT * FROM ai_templates")
        assert len(templates) >= 4

    def test_insert_and_fetch_content(self):
        cid = execute(
            "INSERT INTO contents (title, body, platforms, language, category) VALUES (?,?,?,?,?)",
            ["Hello", "World", '["telegram"]', "zh-TW", "test"],
        )
        assert cid > 0
        row = fetch_one("SELECT * FROM contents WHERE id=?", [cid])
        assert row["title"] == "Hello"
        assert row["body"] == "World"
        assert row["status"] == "draft"

    def test_update_content(self):
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
            ["Old", "Body", "[]"],
        )
        execute("UPDATE contents SET title=? WHERE id=?", ["Updated", cid])
        row = fetch_one("SELECT title FROM contents WHERE id=?", [cid])
        assert row["title"] == "Updated"

    def test_delete_content(self):
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
            ["DeleteMe", "Body", "[]"],
        )
        execute("DELETE FROM contents WHERE id=?", [cid])
        row = fetch_one("SELECT * FROM contents WHERE id=?", [cid])
        assert row is None

    def test_insert_and_query_kb(self):
        kid = execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["test", "demo"]), "This is a test answer", "en"],
        )
        assert kid > 0
        row = fetch_one("SELECT * FROM kb_entries WHERE id=?", [kid])
        assert json.loads(row["keywords"]) == ["test", "demo"]

    def test_insert_contact(self):
        cid = execute(
            "INSERT INTO contacts (name, contact, email, message) VALUES (?,?,?,?)",
            ["Alice", "alice@test.com", "alice@test.com", "Hello"],
        )
        row = fetch_one("SELECT * FROM contacts WHERE id=?", [cid])
        assert row["name"] == "Alice"

    def test_pagination(self):
        for i in range(10):
            execute(
                "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
                [f"Post {i}", f"Body {i}", "[]"],
            )
        page1 = fetch("SELECT * FROM contents ORDER BY id LIMIT 3 OFFSET 0")
        page2 = fetch("SELECT * FROM contents ORDER BY id LIMIT 3 OFFSET 3")
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0]["id"] != page2[0]["id"]

    def test_schedules_cascade(self):
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
            ["Scheduled", "Body", '["telegram"]'],
        )
        sid = execute(
            "INSERT INTO schedules (content_id, platform, scheduled_at, status) VALUES (?,?,?,?)",
            [cid, "telegram", "2026-12-31 09:00", "pending"],
        )
        row = fetch_one("SELECT * FROM schedules WHERE id=?", [sid])
        assert row["content_id"] == cid
        assert row["status"] == "pending"

    def test_multiple_platforms_content(self):
        platforms = json.dumps(["telegram", "line", "facebook"])
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
            ["Multi", "Body text", platforms],
        )
        row = fetch_one("SELECT platforms FROM contents WHERE id=?", [cid])
        assert json.loads(row["platforms"]) == ["telegram", "line", "facebook"]

    def test_user_registration(self):
        import hashlib, secrets
        email = "user@test.com"
        salt = secrets.token_hex(8)
        pw = hashlib.sha256(("pass123" + salt).encode()).hexdigest()
        token = secrets.token_hex(24)
        uid = execute(
            "INSERT INTO users (username, email, password_hash, salt, token) VALUES (?,?,?,?,?)",
            [email, email, pw, salt, token],
        )
        assert uid > 0
        row = fetch_one("SELECT * FROM users WHERE id=?", [uid])
        assert row["email"] == email
        assert row["token"] == token

    def test_empty_query_returns_empty_list(self):
        rows = fetch("SELECT * FROM contents WHERE title=?", ["nonexistent"])
        assert rows == []

    def test_fetch_one_returns_none_on_empty(self):
        row = fetch_one("SELECT * FROM contents WHERE id=?", [99999])
        assert row is None

    def test_analytics_insert(self):
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
            ["Analytics Post", "Body", "[]"],
        )
        aid = execute(
            "INSERT INTO analytics (content_id, platform, views, likes) VALUES (?,?,?,?)",
            [cid, "telegram", 100, 10],
        )
        assert aid > 0
        rows = fetch("SELECT * FROM analytics WHERE platform=?", ["telegram"])
        assert len(rows) >= 1
        assert rows[0]["views"] == 100

    def test_kb_pending_tracking(self):
        pid = execute(
            "INSERT INTO kb_pending (question, language, count) VALUES (?,?,?)",
            ["What is the price?", "en", 1],
        )
        assert pid > 0
        execute("UPDATE kb_pending SET count=? WHERE id=?", [5, pid])
        row = fetch_one("SELECT * FROM kb_pending WHERE id=?", [pid])
        assert row["count"] == 5
