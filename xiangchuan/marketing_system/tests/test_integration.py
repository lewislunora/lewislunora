"""Full integration tests – mock only external I/O, exercise real code paths"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from marketing_system.api.server import app
from marketing_system.database import execute, fetch, fetch_one, init_db


@pytest.fixture(autouse=True)
def clean_db():
    from pathlib import Path
    import marketing_system.config as cfg
    for p in [cfg.DATABASE_PATH, cfg.DATABASE_BACKUP_PATH]:
        if p.exists():
            p.unlink()
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


class TestContactFullPipeline:
    """Exercise the real contact_form → email/notification routing with low-level mocks"""

    def test_smtp_configured_sends_email(self, client):
        """When SMTP_USER/SMTP_PASS are set, contact_form should call SMTP, not Telegram"""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value = MagicMock()
            resp = client.post("/api/contact", json={
                "姓名": "Alice", "聯絡方式": "@alice",
                "公司": "Co", "Email": "a@b.com", "行業別": "tech", "備註": "Hello",
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            mock_smtp.return_value.__enter__.return_value.starttls.assert_called_once()

    def test_smtp_not_configured_sends_telegram(self, client):
        """When SMTP_USER is empty, contact_form should fallback to Telegram notification"""
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            with patch("requests.post") as mock_post:
                mock_post.return_value.json.return_value = {"ok": True}
                resp = client.post("/api/contact", json={
                    "姓名": "Bob", "聯絡方式": "@bob",
                })
                assert resp.status_code == 200
                mock_post.assert_called_once()

    def test_contact_stores_in_db(self, client):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value = MagicMock()
            client.post("/api/contact", json={
                "姓名": "Carol", "聯絡方式": "carol@test.com",
            })
        rows = fetch("SELECT * FROM contacts WHERE name=?", ["Carol"])
        assert len(rows) == 1
        assert rows[0]["contact"] == "carol@test.com"

    def test_contact_routing_smtp_preferred_over_telegram(self, client):
        """When SMTP is configured, should NOT call Telegram"""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.return_value = MagicMock()
            with patch("requests.post") as mock_req:
                resp = client.post("/api/contact", json={
                    "姓名": "Routing", "聯絡方式": "test",
                })
                assert resp.status_code == 200
                mock_req.assert_not_called()

    def test_contact_partial_fields(self, client):
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            with patch("requests.post"):
                resp = client.post("/api/contact", json={
                    "姓名": "Partial", "聯絡方式": "@partial",
                })
                assert resp.status_code == 200
                rows = fetch("SELECT * FROM contacts WHERE name=?", ["Partial"])
                assert rows[0]["company"] == ""
                assert rows[0]["email"] == ""


class TestWebhookFullFlow:
    """Test the full webhook processing pipeline with KB matching"""

    def test_webhook_kb_match_returns_reply(self, client):
        """Pre-insert KB entry, then simulate a webhook message that should match"""
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
            [json.dumps(["方案價格"]), "我們的方案價格...", "zh-TW"],
        )
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            resp = client.post("/api/telegram/webhook", json={
                "message": {
                    "chat": {"id": 12345, "type": "private"},
                    "text": "請問方案價格多少？",
                    "message_id": 100,
                }
            })
            assert resp.status_code == 200
            sent = mock_post.call_args[1]["json"]
            assert "方案價格" in sent["text"]
            assert sent["reply_to_message_id"] == 100
            assert sent["chat_id"] == 12345

    def test_webhook_no_match_saves_pending(self, client):
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            client.post("/api/telegram/webhook", json={
                "message": {
                    "chat": {"id": 999, "type": "private"},
                    "text": "今天天氣如何？",
                    "message_id": 1,
                }
            })
        rows = fetch("SELECT * FROM kb_pending WHERE question=?", ["今天天氣如何？"])
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"

    def test_webhook_group_mention(self, client):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
            [json.dumps(["方案介紹"]), "方案介紹回答", "zh-TW"],
        )
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            resp = client.post("/api/telegram/webhook", json={
                "message": {
                    "chat": {"id": -100123, "type": "group", "title": "Test Group"},
                    "text": "@ailunora_bot 請問方案介紹",
                    "message_id": 5,
                }
            })
            assert resp.status_code == 200
            sent = mock_post.call_args[1]["json"]
            assert "方案介紹回答" in sent["text"]
            assert sent["chat_id"] == -100123

    def test_webhook_group_no_mention_ignored(self, client):
        with patch("requests.post") as mock_post:
            resp = client.post("/api/telegram/webhook", json={
                "message": {
                    "chat": {"id": -100456, "type": "group"},
                    "text": "無關內容未提及Bot",
                    "message_id": 10,
                }
            })
            assert resp.status_code == 200
            mock_post.assert_not_called()

    def test_webhook_start_command(self, client):
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            client.post("/api/telegram/webhook", json={
                "message": {
                    "chat": {"id": 777, "type": "private"},
                    "text": "/start",
                    "message_id": 1,
                }
            })
            sent = mock_post.call_args[1]["json"]
            assert "歡迎使用" in sent["text"]

    def test_webhook_unknown_command_returns_ok(self, client):
        with patch("requests.post") as mock_post:
            resp = client.post("/api/telegram/webhook", json={
                "message": {
                    "chat": {"id": 888, "type": "private"},
                    "text": "/unknown_cmd_xyz",
                    "message_id": 1,
                }
            })
            assert resp.status_code == 200
            mock_post.assert_not_called()

    def test_webhook_channel_post(self, client):
        """Channel posts should trigger chat_id auto-save"""
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            resp = client.post("/api/telegram/webhook", json={
                "channel_post": {
                    "chat": {"id": -100999, "type": "channel", "title": "Test Channel"},
                    "text": "Hello channel!",
                    "message_id": 1,
                }
            })
            assert resp.status_code == 200
        rows = fetch("SELECT * FROM accounts WHERE platform='telegram_chat'")
        assert any("Test Channel" in r["label"] for r in rows)

    def test_webhook_empty_body(self, client):
        resp = client.post("/api/telegram/webhook", json={})
        assert resp.status_code == 200

    def test_webhook_missing_chat(self, client):
        resp = client.post("/api/telegram/webhook", json={"message": {"text": "no chat"}})
        assert resp.status_code == 200


class TestBroadcastFullFlow:
    """Broadcast with real accounts in DB"""

    def test_broadcast_to_all_accounts(self, client):
        execute(
            "INSERT INTO accounts (platform, label, credentials) VALUES (?, ?, ?)",
            ["telegram_chat", "Group1", json.dumps({"chat_id": "-100111"})],
        )
        execute(
            "INSERT INTO accounts (platform, label, credentials) VALUES (?, ?, ?)",
            ["telegram_chat", "Group2", json.dumps({"chat_id": "-100222"})],
        )
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            resp = client.post("/api/telegram/broadcast?text=hello+world")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert mock_post.call_count == 2

    def test_broadcast_without_accounts(self, client):
        with patch("requests.post") as mock_post:
            resp = client.post("/api/telegram/broadcast?text=hi")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            mock_post.assert_not_called()


class TestKBFullFlow:
    """Full KB CRUD + query + pending + auto-learn lifecycle"""

    def test_create_and_list(self, client):
        client.post("/api/kb", json={
            "keywords": ["測試", "test"],
            "answer": "這是測試回答",
            "language": "zh-TW",
        })
        resp = client.get("/api/kb")
        assert len(resp.json()["items"]) >= 1

    def test_query_exact_match(self, client):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
            [json.dumps(["方案價格"]), "方案回答內容", "zh-TW"],
        )
        resp = client.post("/api/kb/query", json={"text": "方案價格多少？"})
        assert resp.json()["reply"] == "方案回答內容"

    def test_query_no_match(self, client):
        resp = client.post("/api/kb/query", json={"text": "zzzrandom999"})
        assert resp.json()["reply"] is None

    def test_query_empty_text(self, client):
        resp = client.post("/api/kb/query", json={"text": ""})
        assert resp.status_code == 400

    def test_update_and_verify(self, client):
        cid = execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
            [json.dumps(["舊"]), "舊答案", "zh-TW"],
        )
        client.put(f"/api/kb/{cid}", json={
            "keywords": ["新"],
            "answer": "新答案",
            "language": "en",
        })
        row = fetch_one("SELECT answer, language FROM kb_entries WHERE id=?", [cid])
        assert row["answer"] == "新答案"
        assert row["language"] == "en"

    def test_delete_kb(self, client):
        cid = execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?, ?, ?)",
            [json.dumps(["del"]), "刪除", "zh-TW"],
        )
        resp = client.delete(f"/api/kb/{cid}")
        assert resp.status_code == 200
        assert fetch_one("SELECT id FROM kb_entries WHERE id=?", [cid]) is None

    def test_pending_suggest(self, client):
        pid = execute(
            "INSERT INTO kb_pending (question, language, count) VALUES (?, ?, ?)",
            ["What is price?", "en", 3],
        )
        resp = client.post(f"/api/kb/pending/{pid}/suggest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "What is price?"
        assert data["ai_suggest"] == ""  # No GROQ_API_KEY

    def test_pending_reject(self, client):
        pid = execute(
            "INSERT INTO kb_pending (question, language, count) VALUES (?, ?, ?)",
            ["Bad question", "zh-TW", 1],
        )
        client.post(f"/api/kb/pending/{pid}/reject")
        row = fetch_one("SELECT status FROM kb_pending WHERE id=?", [pid])
        assert row["status"] == "rejected"

    def test_pending_nonexistent_suggest(self, client):
        resp = client.post("/api/kb/pending/99999/suggest")
        assert resp.status_code == 404

    def test_auto_learn_endpoint(self, client):
        resp = client.post("/api/kb/pending/auto-learn")
        assert resp.status_code == 200


class TestContentEdgeCases:
    """Content CRUD with edge cases"""

    def test_empty_platforms(self, client):
        resp = client.post("/api/content", json={
            "title": "No Platform",
            "body": "Body",
            "platforms": [],
        })
        assert resp.status_code == 200

    def test_scheduled_content(self, client):
        resp = client.post("/api/content", json={
            "title": "Scheduled",
            "body": "Body",
            "platforms": ["telegram"],
            "scheduled_at": "2030-01-01T09:00",
        })
        assert resp.status_code == 200

    def test_list_with_status_filter(self, client):
        execute(
            "INSERT INTO contents (title, body, platforms, status) VALUES (?, ?, ?, ?)",
            ["Draft", "Body", "[]", "draft"],
        )
        execute(
            "INSERT INTO contents (title, body, platforms, status) VALUES (?, ?, ?, ?)",
            ["Published", "Body", "[]", "published"],
        )
        resp = client.get("/api/content?status=published")
        data = resp.json()
        assert all(c["status"] == "published" for c in data["items"])

    def test_delete_with_schedules(self, client):
        cid = execute(
            "INSERT INTO contents (title, body, platforms) VALUES (?, ?, ?)",
            ["ToDelete", "Body", "[]"],
        )
        execute(
            "INSERT INTO schedules (content_id, platform, scheduled_at, status) VALUES (?, ?, '2030-01-01', 'pending')",
            [cid, "telegram"],
        )
        resp = client.delete(f"/api/content/{cid}")
        assert resp.status_code == 200
        schedules = fetch("SELECT * FROM schedules WHERE content_id=?", [cid])
        assert len(schedules) == 0

    def test_ai_generate_with_groq_key(self, client):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False):
            with patch("marketing_system.ai.generator.AIContentGenerator.is_available", return_value=True):
                with patch("marketing_system.ai.generator.AIContentGenerator.generate", return_value="AI response"):
                    resp = client.post("/api/content/ai-generate", json={
                        "template": "社aaa",
                        "variables": {"topic": "AI"},
                    })
                    assert resp.status_code == 200
                    assert resp.json()["text"] == "AI response"


class TestAuthEdgeCases:
    """Auth endpoints with edge cases"""

    def test_register_special_chars_email(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "user+tag@test.com",
            "password": "pass123",
        })
        assert resp.status_code == 200
        assert resp.json()["email"] == "user+tag@test.com"

    def test_login_updates_token(self, client):
        reg = client.post("/api/auth/register", json={
            "email": "token_update@test.com",
            "password": "pass",
        }).json()
        token1 = reg["token"]
        # Simulate token being cleared (e.g. server restart scenario)
        execute("UPDATE users SET token=NULL WHERE email=?", ["token_update@test.com"])
        login = client.post("/api/auth/login", json={
            "email": "token_update@test.com",
            "password": "pass",
        }).json()
        assert login["token"] != token1  # New token generated
        assert login["token"] is not None

    def test_register_uppercase_email(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "UPPERCASE@TEST.COM",
            "password": "pass",
        })
        assert resp.status_code == 200
        assert resp.json()["email"] == "uppercase@test.com"


class TestAnalyticsEdgeCases:
    def test_analytics_multiple_days(self, client):
        cid = execute("INSERT INTO contents (title, body, platforms) VALUES (?,?,?)",
                       ["A", "B", "[]"])
        execute("INSERT INTO analytics (content_id, platform, views, likes, recorded_at) VALUES (?,?,?,?, datetime('now', '-60 days'))",
                [cid, "telegram", 10, 1])
        resp7 = client.get("/api/analytics?days=7")
        resp60 = client.get("/api/analytics?days=90")
        assert len(resp7.json()["items"]) == 0  # outside 7-day window
        assert len(resp60.json()["items"]) >= 1  # inside 90-day window


class TestStaticFileEdgeCases:
    def test_dashboard_injects_auth_guard(self, client):
        resp = client.get("/dashboard")
        assert "auth-guard.js" in resp.text
        assert "widget.css" in resp.text
        assert "widget.js" in resp.text

    def test_root_returns_index_html(self, client):
        from pathlib import Path
        import marketing_system.config as cfg
        index = cfg.DOCS_DIR / "index.html"
        if index.exists():
            resp = client.get("/")
            assert resp.status_code == 200

    def test_api_status_smtp_flag(self, client):
        with patch.dict(os.environ, {"SMTP_USER": "u", "SMTP_PASS": "p"}, clear=False):
            resp = client.get("/api/status")
            assert resp.json()["smtp_configured"] is True
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            resp = client.get("/api/status")
            assert resp.json()["smtp_configured"] is False
