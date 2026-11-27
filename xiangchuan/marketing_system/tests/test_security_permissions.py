"""權限邊界安全測試：webhook 密鑰、管理端授權、憑證外洩。"""
import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from marketing_system.api.server import app
from marketing_system.database import execute, fetch_one
import marketing_system.services.openclaw_agent as oa

SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "test-webhook-secret")
GOOD_HEADERS = {"X-Telegram-Bot-Api-Secret-Token": SECRET}


@pytest.fixture
def client():
    return TestClient(app)


def _webhook(client, chat, text, headers=GOOD_HEADERS):
    return client.post(
        "/api/telegram/webhook",
        headers=headers,
        json={"message": {"chat": chat, "text": text, "message_id": 1}},
    )


class TestWebhookSecret:
    def test_missing_secret_rejected(self, client):
        with patch("requests.post") as post:
            resp = _webhook(
                client,
                {"id": -999888777, "type": "group"},
                "/部署",
                headers={},
            )
            assert resp.status_code == 403
            post.assert_not_called()

    def test_wrong_secret_rejected(self, client):
        with patch("requests.post") as post:
            resp = _webhook(
                client,
                {"id": 626453598, "type": "private"},
                "/部署",
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            )
            assert resp.status_code == 403
            post.assert_not_called()

    def test_valid_secret_external_group_still_cannot_control(self, client):
        with patch("requests.post") as post, patch.object(oa, "DEPLOY_HOOK_URL", "https://hook.test/deploy"):
            post.return_value.json.return_value = {"ok": True}
            _webhook(client, {"id": -999888777, "type": "group"}, "/部署")
            assert not any("hook.test/deploy" in str(c) for c in post.call_args_list)

    def test_valid_secret_private_work_group_needs_mention(self, client):
        with patch("requests.post") as post, patch.object(oa, "DEPLOY_HOOK_URL", "https://hook.test/deploy"):
            post.return_value.json.return_value = {"ok": True}
            _webhook(
                client,
                {"id": -1003739611959, "type": "supergroup"},
                "/部署",
            )
            assert not any("hook.test/deploy" in str(c) for c in post.call_args_list)


class TestConfigEndpointsRequireAdmin:
    @pytest.mark.parametrize("method,path,body", [
        ("post", "/api/accounts", {"platform": "telegram", "label": "x", "credentials": {}}),
        ("put", "/api/accounts/1", {"platform": "telegram", "label": "x", "credentials": {}}),
        ("delete", "/api/accounts/1", None),
        ("post", "/api/content", {"title": "x", "body": "y", "platforms": []}),
        ("delete", "/api/content/1", None),
        ("post", "/api/pages", {"title": "x", "slug": "x", "content": "y"}),
        ("delete", "/api/pages/1", None),
        ("post", "/api/kb", {"keywords": ["x"], "answer": "y"}),
        ("delete", "/api/kb/1", None),
        ("post", "/api/telegram/broadcast?text=spam", None),
        ("delete", "/api/comments/1", None),
    ])
    def test_anonymous_cannot_modify(self, client, method, path, body):
        with patch("requests.post") as post:
            kw = {"json": body} if body is not None else {}
            resp = getattr(client, method)(path, **kw)
            assert resp.status_code in (401, 403), (path, resp.status_code)
            if path.startswith("/api/telegram/broadcast"):
                post.assert_not_called()

    def test_admin_can_create_account(self, client):
        execute(
            "INSERT INTO users (username, email, password_hash, salt, token, is_admin, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1, 1)",
            ["sec_admin", "sec@test.com", "x", "s", "sec-token"],
        )
        resp = client.post(
            "/api/accounts",
            headers={"Cookie": "token=sec-token"},
            json={"platform": "telegram", "label": "ok", "credentials": {"chat_id": 1}},
        )
        assert resp.status_code == 200
        assert fetch_one("SELECT label FROM accounts WHERE label='ok'")


class TestOperationalEndpointsRequireAdmin:
    """會產生內容或對外發文的操作端點不能匿名呼叫。"""

    @pytest.mark.parametrize("method,path,body", [
        ("get", "/api/auto-promote", None),
        ("post", "/api/auto-promote/post/1", None),
        ("post", "/api/roam/visit", {"url": "https://example.test"}),
        ("post", "/api/roam/generate", {"title": "x", "content": "y", "url": "https://example.test"}),
        ("post", "/api/roam/post", {"url": "https://example.test", "reply": "x"}),
        ("post", "/api/roam/run", None),
    ])
    def test_anonymous_cannot_operate(self, client, method, path, body):
        with patch("requests.post") as post, patch("requests.get") as get:
            kw = {"json": body} if body is not None else {}
            resp = getattr(client, method)(path, **kw)
            assert resp.status_code in (401, 403), (path, resp.status_code)
            post.assert_not_called()
            get.assert_not_called()

    def test_govdata_force_cannot_bypass_cooldown(self, client):
        """公開 ingest 端點忽略 force，避免匿名反覆下載。"""
        with patch("marketing_system.services.govdata.ingest", return_value={"ok": True}) as ingest:
            resp = client.post("/api/govdata/ingest", json={"nid": "abc", "force": True})
            assert resp.status_code == 200
            ingest.assert_called_once_with("abc")


class TestRollbackPaths:
    """誤改後的可回滾性：設定版本歷史、權限 audit、本機 break-glass。"""

    def test_site_settings_history_and_rollback(self, admin_client):
        admin_client.put("/api/site-settings", json={"key": "hero_title", "value": "原始"})
        admin_client.put("/api/site-settings", json={"key": "hero_title", "value": "誤改"})

        history = admin_client.get("/api/site-settings/hero_title/history")
        assert history.status_code == 200
        assert [x["value"] for x in history.json()["items"]] == ["原始"]

        resp = admin_client.post("/api/site-settings/hero_title/rollback")
        assert resp.status_code == 200
        current = admin_client.get("/api/site-settings/hero_title").json()
        assert current.get("value") == "原始" or current.get("_raw") == "原始"

    def test_anonymous_cannot_view_or_rollback_settings(self, client):
        assert client.get("/api/site-settings/any/history").status_code in (401, 403)
        assert client.post("/api/site-settings/any/rollback").status_code in (401, 403)

    def test_admin_change_is_audited(self, admin_client):
        execute(
            "INSERT INTO users (username, email, password_hash, salt, token, is_admin, is_active) "
            "VALUES (?, ?, ?, ?, ?, 0, 1)",
            ["target_user", "target@test.com", "x", "s", "target-token"],
        )
        resp = admin_client.post("/api/admin/set-admin?email=target@test.com&is_admin=true")
        assert resp.status_code == 200
        row = fetch_one("SELECT action, target FROM admin_audit ORDER BY id DESC LIMIT 1")
        assert row["target"] == "target@test.com"
        assert row["action"] == "grant"

    def test_break_glass_can_restore_admin_without_api(self, admin_client):
        from marketing_system.scripts import ops_rollback

        execute(
            "INSERT INTO users (username, email, password_hash, salt, token, is_admin, is_active) "
            "VALUES (?, ?, ?, ?, ?, 0, 1)",
            ["locked", "locked@test.com", "x", "s", "locked-token"],
        )
        # 模擬所有管理員都被降權：直接操作 DB，不經需要 admin 的 API
        execute("UPDATE users SET is_admin=0")
        ops_rollback.admin(argparse.Namespace(
            email="locked@test.com", grant=True, revoke=False, actor="break-glass-test"
        ))
        row = fetch_one("SELECT is_admin FROM users WHERE email='locked@test.com'")
        assert row["is_admin"] == 1
        assert client_can_login_as_admin()

    def test_break_glass_can_restore_site_setting(self, admin_client):
        from marketing_system.scripts import ops_rollback

        admin_client.put("/api/site-settings", json={"key": "notice", "value": "舊公告"})
        admin_client.put("/api/site-settings", json={"key": "notice", "value": "錯公告"})
        ops_rollback.site_settings(argparse.Namespace(
            key="notice", history_id=None, list=False, actor="break-glass-test"
        ))
        assert fetch_one("SELECT value FROM site_settings WHERE key='notice'")["value"] == "舊公告"


def client_can_login_as_admin():
    """用被 break-glass 還原的 token 打一次管理端檢查。"""
    return TestClient(app).get(
        "/api/admin/check", headers={"Cookie": "token=locked-token"}
    ).json()["admin"] is True


class TestNoHardcodedCredentials:
    @pytest.mark.parametrize("relative", [
        "xiangchuan/deploy.sh",
        "xiangchuan/run_dev_bot.sh",
        "xiangchuan/start_bot.sh",
        "xiangchuan/bot_test.log",
    ])
    def test_no_bot_token_in_tracked_files(self, relative):
        root = Path(__file__).resolve().parents[3]
        text = (root / relative).read_text()
        assert "8653211794" not in text
        assert "AAGWq9" not in text
        assert "AAG08x" not in text
