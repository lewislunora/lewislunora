"""Comprehensive API endpoint tests"""
import json
import pytest
from unittest.mock import patch, MagicMock
from marketing_system.database import execute, fetch, fetch_one


class TestStatus:
    def test_status_returns_200(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "platforms" in data
        assert "scheduler" in data

    def test_status_has_platforms(self, client):
        resp = client.get("/api/status")
        data = resp.json()
        assert isinstance(data["platforms"], dict)
        assert "telegram" in data["platforms"]


class TestConfig:
    def test_config_returns_google_client_id(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "google_client_id" in data

    def test_config_is_dict(self, client):
        resp = client.get("/api/config")
        assert isinstance(resp.json(), dict)


class TestContact:
    def test_contact_with_valid_data(self, client, sample_contact):
        with patch("marketing_system.api.server.send_contact_email") as mock_email:
            mock_email.return_value = {"status": "sent"}
            resp = client.post("/api/contact", json=sample_contact)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    def test_contact_missing_name(self, client):
        resp = client.post("/api/contact", json={"聯絡方式": "test@test.com"})
        assert resp.status_code == 400

    def test_contact_missing_contact(self, client):
        resp = client.post("/api/contact", json={"姓名": "Test"})
        assert resp.status_code == 400

    def test_list_contacts(self, client, sample_contact):
        with patch("marketing_system.api.server.send_contact_email") as mock_email:
            mock_email.return_value = {"status": "sent"}
            client.post("/api/contact", json=sample_contact)
        resp = client.get("/api/contacts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_contacts_with_pagination(self, client, sample_contact):
        with patch("marketing_system.api.server.send_contact_email") as mock_email:
            mock_email.return_value = {"status": "sent"}
            for _ in range(5):
                client.post("/api/contact", json=sample_contact)
        resp = client.get("/api/contacts?per_page=2")
        data = resp.json()
        assert len(data["items"]) == 2


class TestContent:
    def test_create_content(self, client, sample_content):
        resp = client.post("/api/content", json=sample_content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"

    def test_create_content_saves_title(self, client, sample_content):
        create = client.post("/api/content", json=sample_content).json()
        row = fetch_one("SELECT title FROM contents WHERE id=?", [create["id"]])
        assert row["title"] == "Test Post"

    def test_create_content_without_title(self, client):
        resp = client.post("/api/content", json={"body": "no title", "platforms": ["telegram"]})
        assert resp.status_code == 422

    def test_list_contents(self, client, sample_content):
        client.post("/api/content", json=sample_content)
        resp = client.get("/api/content")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_get_single_content(self, client, sample_content):
        create = client.post("/api/content", json=sample_content).json()
        resp = client.get(f"/api/content/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Post"

    def test_get_nonexistent_content(self, client):
        resp = client.get("/api/content/99999")
        assert resp.status_code == 404

    def test_delete_content(self, client, sample_content):
        create = client.post("/api/content", json=sample_content).json()
        resp = client.delete(f"/api/content/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_nonexistent_content(self, client):
        resp = client.delete("/api/content/99999")
        assert resp.status_code == 200

    @patch("marketing_system.api.server._build_connector")
    def test_publish_content(self, mock_build, client, sample_content):
        mock_conn = MagicMock()
        mock_conn.post.return_value = {"success": True, "post_url": "https://t.me/test"}
        mock_build.return_value = mock_conn
        create = client.post("/api/content", json=sample_content).json()
        resp = client.post(f"/api/content/{create['id']}/publish")
        assert resp.status_code == 200
        assert "results" in resp.json()

    @patch("marketing_system.api.server._build_connector")
    def test_publish_updates_status_to_published(self, mock_build, client, sample_content):
        mock_conn = MagicMock()
        mock_conn.post.return_value = {"success": True, "post_url": "https://t.me/test"}
        mock_build.return_value = mock_conn
        create = client.post("/api/content", json=sample_content).json()
        client.post(f"/api/content/{create['id']}/publish")
        row = fetch_one("SELECT status FROM contents WHERE id=?", [create["id"]])
        assert row["status"] == "published"

    def test_ai_generate_fallback_without_key(self, client):
        resp = client.post("/api/content/ai-generate", json={
            "template": "社aaa",
            "variables": {"topic": "AI"},
        })
        assert resp.status_code == 200
        assert "text" in resp.json()


class TestAccounts:
    def test_create_account(self, client, sample_account):
        resp = client.post("/api/accounts", json=sample_account)
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_list_accounts(self, client, sample_account):
        client.post("/api/accounts", json=sample_account)
        resp = client.get("/api/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1

    def test_delete_account(self, client, sample_account):
        create = client.post("/api/accounts", json=sample_account).json()
        resp = client.delete(f"/api/accounts/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_nonexistent_account(self, client):
        resp = client.delete("/api/accounts/99999")
        assert resp.status_code == 200

    @patch("marketing_system.api.server._build_connector")
    def test_verify_account(self, mock_build, client, sample_account):
        mock_conn = MagicMock()
        mock_conn.verify.return_value = True
        mock_build.return_value = mock_conn
        create = client.post("/api/accounts", json=sample_account).json()
        resp = client.post(f"/api/accounts/{create['id']}/verify")
        assert resp.status_code == 200
        assert resp.json().get("verified") is True

    @patch("marketing_system.api.server._build_connector")
    def test_verify_invalid_account(self, mock_build, client, sample_account):
        mock_conn = MagicMock()
        mock_conn.verify.return_value = False
        mock_build.return_value = mock_conn
        create = client.post("/api/accounts", json=sample_account).json()
        resp = client.post(f"/api/accounts/{create['id']}/verify")
        assert resp.status_code == 200
        assert resp.json().get("verified") is False


class TestSchedules:
    def test_list_schedules(self, client, sample_content):
        sc = {**sample_content, "scheduled_at": "2027-01-01T09:00"}
        client.post("/api/content", json=sc)
        resp = client.get("/api/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_schedules_empty_when_none(self, client):
        resp = client.get("/api/schedules")
        data = resp.json()
        assert "items" in data


class TestAnalytics:
    def test_analytics_returns_data(self, client):
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
            ["APost", "Body", "[]"],
        )
        execute(
            "INSERT INTO analytics (content_id, platform, views, likes) VALUES (?,?,?,?)",
            [cid, "telegram", 100, 10],
        )
        execute(
            "INSERT INTO analytics (content_id, platform, views, likes) VALUES (?,?,?,?)",
            [cid, "line", 200, 20],
        )
        resp = client.get("/api/analytics?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 2

    def test_analytics_empty_with_no_data(self, client):
        resp = client.get("/api/analytics?days=30")
        data = resp.json()
        assert "items" in data


class TestKnowledgeBase:
    def test_create_kb_entry(self, client, sample_kb_entry):
        resp = client.post("/api/kb", json=sample_kb_entry)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"

    def test_list_kb_entries(self, client, sample_kb_entry):
        client.post("/api/kb", json=sample_kb_entry)
        resp = client.get("/api/kb")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1

    def test_list_kb_filter_by_language(self, client, sample_kb_entry):
        client.post("/api/kb", json=sample_kb_entry)
        resp = client.get("/api/kb?language=zh-TW")
        data = resp.json()
        for item in data["items"]:
            assert item["language"] == "zh-TW"

    def test_update_kb_entry(self, client, sample_kb_entry):
        create = client.post("/api/kb", json=sample_kb_entry).json()
        kid = create["id"]
        resp = client.put(f"/api/kb/{kid}", json={
            "keywords": ["方案", "價格", "費用", "更新"],
            "answer": "Updated answer",
            "language": "zh-TW",
        })
        assert resp.status_code == 200
        row = fetch_one("SELECT answer FROM kb_entries WHERE id=?", [kid])
        assert row["answer"] == "Updated answer"

    def test_delete_kb_entry(self, client, sample_kb_entry):
        create = client.post("/api/kb", json=sample_kb_entry).json()
        kid = create["id"]
        resp = client.delete(f"/api/kb/{kid}")
        assert resp.status_code == 200
        row = fetch_one("SELECT * FROM kb_entries WHERE id=?", [kid])
        assert row is None

    def test_kb_query_matches(self, client, sample_kb_entry):
        client.post("/api/kb", json=sample_kb_entry)
        resp = client.post("/api/kb/query", json={"text": "請問方案價格多少？"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] is not None

    def test_kb_query_no_match(self, client):
        resp = client.post("/api/kb/query", json={"text": "今天天氣很好"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] is None

    def test_list_pending(self, client):
        resp = client.get("/api/kb/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    @patch("marketing_system.ai.generator.AIContentGenerator")
    def test_suggest_pending(self, mock_gen, client):
        pid = execute(
            "INSERT INTO kb_pending (question, language, count) VALUES (?,?,?)",
            ["What is the price?", "en", 5],
        )
        mock_instance = MagicMock()
        mock_instance.generate.return_value = "The price is $10"
        mock_gen.return_value = mock_instance
        resp = client.post(f"/api/kb/pending/{pid}/suggest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_suggest"] == "The price is $10"

    def test_reject_pending(self, client):
        pid = execute(
            "INSERT INTO kb_pending (question, language, count) VALUES (?,?,?)",
            ["Ignore me", "en", 1],
        )
        resp = client.post(f"/api/kb/pending/{pid}/reject")
        assert resp.status_code == 200
        row = fetch_one("SELECT * FROM kb_pending WHERE id=?", [pid])
        assert row["status"] == "rejected"

    def test_auto_learn_endpoint(self, client):
        resp = client.post("/api/kb/pending/auto-learn")
        assert resp.status_code == 200


class TestTemplates:
    def test_list_templates(self, client):
        resp = client.get("/api/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 4

    def test_templates_have_expected_structure(self, client):
        resp = client.get("/api/templates")
        item = resp.json()["items"][0]
        assert "name" in item
        assert "prompt_template" in item


class TestBackup:
    def test_backup_endpoint(self, client):
        resp = client.get("/api/backup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestTelegram:
    def test_broadcast_requires_text(self, client):
        resp = client.post("/api/telegram/broadcast")
        assert resp.status_code == 400

    def test_broadcast_with_text(self, client):
        resp = client.post("/api/telegram/broadcast?text=hello")
        assert resp.status_code == 200

    def test_webhook_empty(self, client):
        resp = client.post("/api/telegram/webhook", json={})
        assert resp.status_code == 200


class TestAuth:
    def test_register_new_user(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "newuser@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["email"] == "newuser@test.com"

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "email": "dupe@test.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/register", json={
            "email": "dupe@test.com",
            "password": "password123",
        })
        assert resp.status_code == 400

    def test_login_valid_credentials(self, client):
        client.post("/api/auth/register", json={
            "email": "login@test.com",
            "password": "mypassword",
        })
        resp = client.post("/api/auth/login", json={
            "email": "login@test.com",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={
            "email": "wrongpw@test.com",
            "password": "correctpw",
        })
        resp = client.post("/api/auth/login", json={
            "email": "wrongpw@test.com",
            "password": "wrongpw",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "anything",
        })
        assert resp.status_code == 401

    def test_auth_me_with_valid_token(self, client):
        reg = client.post("/api/auth/register", json={
            "email": "me@test.com",
            "password": "password",
        }).json()
        resp = client.get(f"/api/auth/me?token={reg['token']}")
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@test.com"

    def test_auth_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_auth_me_with_invalid_token(self, client):
        resp = client.get("/api/auth/me?token=invalid_token_here")
        assert resp.status_code == 401


class TestDashboard:
    def test_dashboard_returns_html(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "auth-guard.js" in resp.text


class TestRoot:
    def test_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
