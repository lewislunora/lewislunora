"""Social login (Google/Facebook/LINE/Telegram) endpoint tests"""
import time
import hashlib
import hmac
import urllib.parse
import pytest
from unittest.mock import patch


def _tg_sign(data, token):
    items = sorted((k, v) for k, v in data.items() if k != "hash")
    check = "\n".join(f"{k}={v}" for k, v in items)
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def _get_state(resp):
    loc = resp.headers["location"]
    return urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]


class TestProviders:
    def test_providers_empty_when_not_configured(self, client):
        resp = client.get("/api/auth/providers")
        assert resp.status_code == 200
        assert resp.json()["providers"] == []
        assert resp.json()["email_password"] is True

    def test_google_provider_listed_when_configured(self, client):
        with patch("marketing_system.services.social_auth.GOOGLE_CLIENT_ID", "gid"), \
             patch("marketing_system.services.social_auth.GOOGLE_CLIENT_SECRET", "gsec"):
            resp = client.get("/api/auth/providers")
            ids = [p["id"] for p in resp.json()["providers"]]
            assert "google" in ids


class TestOAuthFlow:
    def test_authorize_unconfigured_404(self, client):
        resp = client.get("/api/auth/oauth/google/authorize")
        assert resp.status_code == 404

    def test_authorize_unknown_provider_404(self, client):
        resp = client.get("/api/auth/oauth/line/authorize")
        assert resp.status_code == 404

    def test_google_authorize_redirects_and_sets_state(self, client):
        with patch("marketing_system.services.social_auth.GOOGLE_CLIENT_ID", "gid"), \
             patch("marketing_system.services.social_auth.GOOGLE_CLIENT_SECRET", "gsec"):
            resp = client.get("/api/auth/oauth/google/authorize", follow_redirects=False)
            assert resp.status_code in (302, 307)
            assert "accounts.google.com/o/oauth2/v2/auth" in resp.headers["location"]
            assert resp.cookies.get("oauth_state")
            assert _get_state(resp) == resp.cookies["oauth_state"]

    def test_google_callback_full_flow(self, client):
        with patch("marketing_system.services.social_auth.GOOGLE_CLIENT_ID", "gid"), \
             patch("marketing_system.services.social_auth.GOOGLE_CLIENT_SECRET", "gsec"):
            resp = client.get("/api/auth/oauth/google/authorize", follow_redirects=False)
            state = _get_state(resp)

        with patch("marketing_system.api.server.exchange_and_profile", return_value={
            "provider_id": "12345", "name": "張三", "email": "zhang@test.com", "avatar": ""}):
            resp = client.get(f"/api/auth/oauth/google/callback?code=abc123&state={state}",
                              follow_redirects=False)
            assert resp.status_code in (302, 307)
            assert "ok=1" in resp.headers["location"]
            assert resp.cookies.get("token")

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "zhang@test.com"
        assert me.json()["name"] == "張三"

    def test_google_callback_bad_state_rejected(self, client):
        with patch("marketing_system.services.social_auth.GOOGLE_CLIENT_ID", "gid"), \
             patch("marketing_system.services.social_auth.GOOGLE_CLIENT_SECRET", "gsec"):
            client.get("/api/auth/oauth/google/authorize", follow_redirects=False)
        with patch("marketing_system.api.server.exchange_and_profile", return_value={
            "provider_id": "1", "name": "X", "email": "x@test.com", "avatar": ""}):
            resp = client.get("/api/auth/oauth/google/callback?code=abc&state=wrong",
                              follow_redirects=False)
            assert resp.status_code == 400

    def test_same_identity_logs_into_same_account(self, client):
        for _ in range(2):
            with patch("marketing_system.services.social_auth.GOOGLE_CLIENT_ID", "gid"), \
                 patch("marketing_system.services.social_auth.GOOGLE_CLIENT_SECRET", "gsec"):
                resp = client.get("/api/auth/oauth/google/authorize", follow_redirects=False)
                state = _get_state(resp)
            with patch("marketing_system.api.server.exchange_and_profile", return_value={
                "provider_id": "fixed-uid", "name": "同一個人", "email": "", "avatar": ""}):
                resp = client.get(f"/api/auth/oauth/google/callback?code=abc&state={state}",
                                  follow_redirects=False)
                assert resp.status_code in (302, 307)
        me = client.get("/api/auth/me")
        assert me.json()["name"] == "同一個人"


class TestTelegram:
    def test_telegram_start_unconfigured_404(self, client):
        resp = client.get("/api/auth/telegram/start")
        assert resp.status_code == 404

    def test_telegram_callback_valid(self, client):
        token = "test:bot-token"
        with patch("marketing_system.services.social_auth.TELEGRAM_BOT_TOKEN", token), \
             patch("marketing_system.services.social_auth.TELEGRAM_BOT_USERNAME", "my_bot"):
            data = {"id": "998877", "first_name": "小明", "username": "xiaoming",
                    "auth_date": str(int(time.time()))}
            data["hash"] = _tg_sign(data, token)
            resp = client.post("/api/auth/telegram/callback", data=data, follow_redirects=False)
            assert resp.status_code in (302, 307)
            assert resp.cookies.get("token")

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["name"] == "小明"

    def test_telegram_callback_tampered_rejected(self, client):
        token = "test:bot-token"
        with patch("marketing_system.services.social_auth.TELEGRAM_BOT_TOKEN", token), \
             patch("marketing_system.services.social_auth.TELEGRAM_BOT_USERNAME", "my_bot"):
            data = {"id": "998877", "first_name": "小明",
                    "auth_date": str(int(time.time()))}
            data["hash"] = _tg_sign(data, token)
            data["first_name"] = "被竄改"  # sign no longer matches
            resp = client.post("/api/auth/telegram/callback", data=data, follow_redirects=False)
            assert resp.status_code == 400

    def test_telegram_callback_missing_hash(self, client):
        with patch("marketing_system.services.social_auth.TELEGRAM_BOT_TOKEN", "t"), \
             patch("marketing_system.services.social_auth.TELEGRAM_BOT_USERNAME", "b"):
            resp = client.post("/api/auth/telegram/callback",
                               data={"id": "1", "auth_date": "1"}, follow_redirects=False)
            assert resp.status_code == 400


class TestInstagram:
    def test_instagram_authorize_redirects(self, client):
        with patch("marketing_system.services.social_auth.INSTAGRAM_APP_ID", "igid"), \
             patch("marketing_system.services.social_auth.INSTAGRAM_APP_SECRET", "igsec"):
            resp = client.get("/api/auth/oauth/instagram/authorize", follow_redirects=False)
            assert resp.status_code in (302, 307)
            assert "api.instagram.com/oauth/authorize" in resp.headers["location"]

    def test_instagram_callback_full_flow(self, client):
        with patch("marketing_system.services.social_auth.INSTAGRAM_APP_ID", "igid"), \
             patch("marketing_system.services.social_auth.INSTAGRAM_APP_SECRET", "igsec"):
            resp = client.get("/api/auth/oauth/instagram/authorize", follow_redirects=False)
            state = _get_state(resp)

        with patch("marketing_system.api.server.exchange_and_profile", return_value={
            "provider_id": "987654", "name": "my_brand.ig", "email": "", "avatar": ""}):
            resp = client.get(f"/api/auth/oauth/instagram/callback?code=igcode&state={state}",
                              follow_redirects=False)
            assert resp.status_code in (302, 307)
            assert resp.cookies.get("token")

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["name"] == "my_brand.ig"


class TestSession:
    def test_set_cookie_sets_session(self, client):
        reg = client.post("/api/auth/register", json={
            "email": "cookie@test.com", "password": "password"}).json()
        resp = client.get(f"/api/auth/set-cookie?token={reg['token']}", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert resp.cookies.get("token") == reg["token"]
        assert client.get("/api/auth/me").status_code == 200

    def test_set_cookie_invalid_token(self, client):
        resp = client.get("/api/auth/set-cookie?token=nope", follow_redirects=False)
        assert resp.status_code == 401

    def test_logout_clears_cookie(self, client):
        reg = client.post("/api/auth/register", json={
            "email": "logout@test.com", "password": "password"}).json()
        client.get(f"/api/auth/set-cookie?token={reg['token']}", follow_redirects=False)
        assert client.get("/api/auth/me").status_code == 200
        client.get("/api/auth/logout", follow_redirects=False)
        assert client.get("/api/auth/me").status_code == 401

    def test_me_with_cookie(self, client):
        reg = client.post("/api/auth/register", json={
            "email": "me@test.com", "password": "password"}).json()
        client.get(f"/api/auth/set-cookie?token={reg['token']}", follow_redirects=False)
        me = client.get("/api/auth/me")
        assert me.json()["email"] == "me@test.com"
