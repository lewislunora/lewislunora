"""Email service tests"""
import os
import pytest
from unittest.mock import patch, MagicMock
from marketing_system.services.email_service import (
    get_smtp_config, is_configured, send_contact_email,
)


class TestGetSmtpConfig:
    def test_default_config(self):
        cfg = get_smtp_config()
        assert cfg["host"] == "smtp.gmail.com"
        assert cfg["port"] == 587

    def test_uses_env_vars(self):
        with patch.dict(os.environ, {"SMTP_HOST": "custom.host", "SMTP_PORT": "465"}, clear=False):
            cfg = get_smtp_config()
            assert cfg["host"] == "custom.host"
            assert cfg["port"] == 465


class TestIsConfigured:
    def test_returns_true_when_configured(self):
        with patch.dict(os.environ, {"SMTP_USER": "user@test.com", "SMTP_PASS": "secret"}, clear=False):
            assert is_configured() is True

    def test_returns_false_when_missing_user(self):
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": "secret"}, clear=False):
            assert is_configured() is False

    def test_returns_false_when_missing_pass(self):
        with patch.dict(os.environ, {"SMTP_USER": "user@test.com", "SMTP_PASS": ""}, clear=False):
            assert is_configured() is False

    def test_returns_false_when_both_missing(self):
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            assert is_configured() is False


class TestSendContactEmail:
    def test_fallback_when_not_configured(self):
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            result = send_contact_email({"姓名": "Test"})
            assert result["status"] == "logged"
            assert "not sent" in result["note"]

    @patch("smtplib.SMTP")
    def test_sends_email_when_configured(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        with patch.dict(os.environ, {"SMTP_USER": "me@test.com", "SMTP_PASS": "pass"}, clear=False):
            result = send_contact_email({
                "姓名": "Alice",
                "公司": "Test Corp",
                "聯絡方式": "@alice",
                "Email": "alice@test.com",
                "行業別": "tech",
                "備註": "Hello",
            })
            assert result["status"] == "sent"
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("me@test.com", "pass")
            mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_email_contains_contact_data(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        with patch.dict(os.environ, {"SMTP_USER": "me@test.com", "SMTP_PASS": "pass"}, clear=False):
            send_contact_email({
                "姓名": "Bob",
                "公司": "My Co",
                "聯絡方式": "@bob",
                "Email": "bob@test.com",
                "行業別": "finance",
                "備註": "I want to try",
            })
            msg = mock_server.send_message.call_args[0][0]
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()
            assert "Bob" in body
            assert "My Co" in body
            assert "@bob" in body
            assert "finance" in body
            assert "I want to try" in body
            assert "新預約諮詢" in msg["Subject"]

    @patch("smtplib.SMTP")
    def test_handles_smtp_error_gracefully(self, mock_smtp):
        mock_smtp.return_value.__enter__.return_value.send_message.side_effect = Exception("Connection refused")
        with patch.dict(os.environ, {"SMTP_USER": "me@test.com", "SMTP_PASS": "pass"}, clear=False):
            result = send_contact_email({"姓名": "Error Case"})
            assert result["status"] == "error"
            assert "Connection refused" in result["error"]

    def test_empty_data_does_not_crash(self):
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            result = send_contact_email({})
            assert result["status"] == "logged"

    def test_partial_data(self):
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}, clear=False):
            result = send_contact_email({"姓名": "Only Name"})
            assert result["status"] == "logged"
