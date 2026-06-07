"""Notification service tests"""
import os
import pytest
from unittest.mock import patch, MagicMock
from marketing_system.services.notification_service import send_telegram_notification


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

