"""Gmail API service tests"""
import os
import pytest
from unittest.mock import patch, MagicMock
from marketing_system.services import gmail_api


GMAIL_ENV = {
    "GMAIL_CLIENT_ID": "client-id",
    "GMAIL_CLIENT_SECRET": "client-secret",
    "GMAIL_REFRESH_TOKEN": "refresh-token",
}


class TestIsConfigured:
    def test_false_when_envs_missing(self):
        with patch.dict(os.environ, {"GMAIL_CLIENT_ID": "", "GMAIL_REFRESH_TOKEN": ""}, clear=False):
            assert gmail_api.is_configured() is False

    def test_true_when_all_envs_present(self):
        with patch.dict(os.environ, GMAIL_ENV, clear=False):
            assert gmail_api.is_configured() is True

    def test_false_when_missing_secret(self):
        with patch.dict(os.environ, {**GMAIL_ENV, "GMAIL_CLIENT_SECRET": ""}, clear=False):
            assert gmail_api.is_configured() is False


class TestSendEmail:
    def test_skips_when_not_configured(self):
        with patch.dict(os.environ, {"GMAIL_CLIENT_ID": "", "GMAIL_REFRESH_TOKEN": ""}, clear=False):
            result = gmail_api.send_email("subject", "body")
            assert result["status"] == "skipped"

    @patch("requests.post")
    def test_sends_successfully(self, mock_post):
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "abc123"}
        send_resp = MagicMock()
        send_resp.status_code = 200
        send_resp.json.return_value = {"id": "msg1"}
        mock_post.side_effect = [token_resp, send_resp]

        with patch.dict(os.environ, GMAIL_ENV, clear=False):
            result = gmail_api.send_email("Subject", "Body text", to="me@test.com")
            assert result["status"] == "sent"

        calls = mock_post.call_args_list
        assert calls[0].args[0] == gmail_api.TOKEN_URL
        assert calls[1].args[0] == gmail_api.SEND_URL
        assert calls[1].kwargs["headers"]["Authorization"] == "Bearer abc123"
        import base64
        decoded = base64.urlsafe_b64decode(calls[1].kwargs["json"]["raw"]).decode("utf-8")
        assert "Subject: Subject" in decoded
        assert "To: me@test.com" in decoded
        import email
        msg = email.message_from_string(decoded)
        assert msg.get_content_type() == "text/plain"
        assert msg.get_payload(decode=True).decode("utf-8") == "Body text"

    @patch("requests.post")
    def test_reports_api_error(self, mock_post):
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "abc123"}
        send_resp = MagicMock()
        send_resp.status_code = 500
        send_resp.text = "internal error"
        mock_post.side_effect = [token_resp, send_resp]

        with patch.dict(os.environ, GMAIL_ENV, clear=False):
            result = gmail_api.send_email("Subject", "Body")
            assert result["status"] == "error"
            assert "500" in result["error"]

    @patch("requests.post")
    def test_reports_token_error(self, mock_post):
        token_resp = MagicMock()
        token_resp.status_code = 400
        token_resp.text = "invalid_grant"
        mock_post.return_value = token_resp

        with patch.dict(os.environ, GMAIL_ENV, clear=False):
            result = gmail_api.send_email("Subject", "Body")
            assert result["status"] == "error"

    @patch("requests.post")
    def test_handles_network_error(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        with patch.dict(os.environ, GMAIL_ENV, clear=False):
            result = gmail_api.send_email("Subject", "Body")
            assert result["status"] == "error"
            assert "Network error" in result["error"]
