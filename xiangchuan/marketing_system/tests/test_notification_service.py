"""Notification service tests"""
import os
import pytest
from unittest.mock import patch, MagicMock
from marketing_system.services.notification_service import send_telegram_notification
from marketing_system.services.notification_service import (
    _send_with_retry,
    notify_owner,
)


class TestSendTelegramNotification:
    def test_returns_false_without_chat_id(self):
        with patch("marketing_system.services.notification_service.TELEGRAM_NOTIFY_CHAT_ID", ""):
            with patch("marketing_system.services.notification_service.HARDCODED_BOT_TOKEN", ""):
                result = send_telegram_notification({"姓名": "Test"})
                assert result is False

    def test_returns_false_without_bot_token(self):
        with patch("marketing_system.services.notification_service.HARDCODED_BOT_TOKEN", ""):
            with patch("marketing_system.services.notification_service.TELEGRAM_NOTIFY_CHAT_ID", "123"):
                result = send_telegram_notification({"姓名": "Test"})
                assert result is False

    @patch("requests.post")
    def test_sends_message_successfully(self, mock_post):
        mock_post.return_value.json.return_value = {"ok": True}
        with patch("marketing_system.services.notification_service.TELEGRAM_NOTIFY_CHAT_ID", "123"):
            with patch("marketing_system.services.notification_service.HARDCODED_BOT_TOKEN", "bot:test"):
                result = send_telegram_notification({
                    "姓名": "Alice",
                    "公司": "Test Corp",
                    "行業別": "tech",
                    "備註": "Hello",
                })
                assert result is True
                call_kwargs = mock_post.call_args[1]
                assert call_kwargs["json"]["chat_id"] == "123"
                assert "Alice" in call_kwargs["json"]["text"]
                assert "Test Corp" in call_kwargs["json"]["text"]

    @patch("requests.post")
    def test_handles_api_error(self, mock_post):
        mock_post.return_value.json.return_value = {"ok": False, "description": "Bad token"}
        with patch("marketing_system.services.notification_service.TELEGRAM_NOTIFY_CHAT_ID", "123"):
            with patch("marketing_system.services.notification_service.HARDCODED_BOT_TOKEN", "bot:test"):
                result = send_telegram_notification({"姓名": "Test"})
                assert result is False

    @patch("requests.post")
    def test_handles_network_error(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        with patch("marketing_system.services.notification_service.TELEGRAM_NOTIFY_CHAT_ID", "123"):
            with patch("marketing_system.services.notification_service.HARDCODED_BOT_TOKEN", "bot:test"):
                result = send_telegram_notification({"姓名": "Test"})
                assert result is False

    def test_empty_data_does_not_crash(self):
        with patch("marketing_system.services.notification_service.TELEGRAM_NOTIFY_CHAT_ID", ""):
            with patch("marketing_system.services.notification_service.HARDCODED_BOT_TOKEN", ""):
                result = send_telegram_notification({})
                assert result is False


class TestSendWithRetry:
    def test_succeeds_on_first_attempt(self):
        fn = MagicMock(return_value=True)
        result = _send_with_retry(fn, "test", attempts=3, backoff=0)
        assert result is True
        assert fn.call_count == 1

    def test_retries_until_success(self):
        fn = MagicMock(side_effect=[False, False, True])
        result = _send_with_retry(fn, "test", attempts=3, backoff=0)
        assert result is True
        assert fn.call_count == 3

    def test_gives_up_after_max_attempts(self):
        fn = MagicMock(return_value=False)
        result = _send_with_retry(fn, "test", attempts=2, backoff=0)
        assert result is False
        assert fn.call_count == 2

    def test_recovers_after_exception(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise Exception("boom")
            return True

        result = _send_with_retry(fn, "test", attempts=3, backoff=0)
        assert result is True

    def test_email_predicate_requires_sent_status(self):
        fn = MagicMock(return_value={"status": "error"})
        result = _send_with_retry(
            fn, "test", attempts=2, backoff=0,
            is_success=lambda r: isinstance(r, dict) and r.get("status") == "sent",
        )
        assert result == {"status": "error"}
        assert fn.call_count == 2


class TestNotifyOwner:
    @patch("marketing_system.services.notification_service.time.sleep")
    @patch("marketing_system.services.notification_service._send_email", return_value={"status": "sent"})
    @patch("marketing_system.services.notification_service._send_line_notify", return_value=False)
    @patch("marketing_system.services.notification_service._send_telegram", return_value=True)
    def test_returns_per_channel_results(self, m_tg, m_line, m_email, m_sleep):
        results = notify_owner("contact", {"姓名": "T", "聯絡方式": "@t"})
        assert results["telegram"] is True
        assert results["line"] is False
        assert results["email"]["status"] == "sent"

    @patch("marketing_system.services.notification_service.time.sleep")
    @patch("marketing_system.services.notification_service._send_email", return_value={"status": "error", "error": "x"})
    @patch("marketing_system.services.notification_service._send_line_notify", return_value=True)
    @patch("marketing_system.services.notification_service._send_telegram", return_value=False)
    def test_reports_failed_channels(self, m_tg, m_line, m_email, m_sleep):
        results = notify_owner("comment", {"author_name": "A", "content": "Hi", "page_path": "/"})
        assert results["telegram"] is False
        assert results["line"] is True
        assert results["email"]["status"] == "error"

