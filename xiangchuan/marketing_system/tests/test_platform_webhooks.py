"""Platform webhook receive/verify tests"""
import os
import pytest
from unittest.mock import patch
from marketing_system.services import platform_webhooks
from marketing_system.services.notification_service import _build_message


class TestVerifyMeta:
    def test_returns_challenge_on_valid_token(self):
        with patch.dict(os.environ, {"FB_WEBHOOK_VERIFY_TOKEN": "secret"}, clear=False):
            challenge = platform_webhooks.verify_meta({
                "hub.mode": "subscribe",
                "hub.verify_token": "secret",
                "hub.challenge": "challenge_123",
            })
            assert challenge == "challenge_123"

    def test_returns_none_on_wrong_token(self):
        with patch.dict(os.environ, {"FB_WEBHOOK_VERIFY_TOKEN": "secret"}, clear=False):
            result = platform_webhooks.verify_meta({
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "c",
            })
            assert result is None

    def test_returns_none_on_wrong_mode(self):
        with patch.dict(os.environ, {"FB_WEBHOOK_VERIFY_TOKEN": "secret"}, clear=False):
            result = platform_webhooks.verify_meta({
                "hub.mode": "unsubscribe",
                "hub.verify_token": "secret",
                "hub.challenge": "c",
            })
            assert result is None


class TestVerifyX:
    def test_returns_signed_response(self):
        with patch.dict(os.environ, {"TWITTER_API_SECRET": "s3cret"}, clear=False):
            resp = platform_webhooks.verify_x({"crc_token": "crc123"})
            assert resp and resp["response_token"].startswith("sha256=")

    def test_deterministic_signature(self):
        with patch.dict(os.environ, {"TWITTER_API_SECRET": "s3cret"}, clear=False):
            r1 = platform_webhooks.verify_x({"crc_token": "abc"})
            r2 = platform_webhooks.verify_x({"crc_token": "abc"})
            assert r1 == r2

    def test_returns_none_without_crc(self):
        assert platform_webhooks.verify_x({}) is None


class TestProcessMetaPayload:
    def test_messenger_message(self):
        payload = {"entry": [{"id": "1", "messaging": [
            {"sender": {"id": "123"}, "recipient": {"id": "456"}, "timestamp": 1000,
             "message": {"mid": "m1", "text": "hello"}}
        ]}]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_meta_payload(payload, "facebook")
            assert count == 1
            args = store.call_args[0]
            assert args[1] == "m1"
            assert args[2] == "123"
            assert args[3] == "hello"

    def test_page_comment_change(self):
        payload = {"entry": [{"id": "1", "changes": [
            {"field": "feed", "value": {
                "from": {"id": "u1", "name": "Alice"},
                "message": "Great post!",
                "id": "c1",
            }}
        ]}]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_meta_payload(payload, "facebook")
            assert count == 1
            args = store.call_args[0]
            assert args[3] == "Great post!"
            assert args[2] == "Alice"

    def test_instagram_comment_uses_username(self):
        payload = {"entry": [{"id": "1", "changes": [
            {"field": "comments", "value": {
                "from": {"id": "ig1", "username": "jay_wang"},
                "text": "想了解方案",
                "id": "igc1",
            }}
        ]}]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_meta_payload(payload, "instagram")
            assert count == 1
            args = store.call_args[0]
            assert args[2] == "jay_wang"
            assert args[3] == "想了解方案"

    def test_threads_reply(self):
        payload = {"entry": [{"id": "1", "changes": [
            {"field": "threads_replies", "value": {
                "from": {"id": "t1", "username": "thread_user"},
                "text": "回應內容",
                "id": "tr1",
            }}
        ]}]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_meta_payload(payload, "threads")
            assert count == 1
            args = store.call_args[0]
            assert args[2] == "thread_user"

    def test_skips_empty_messages(self):
        payload = {"entry": [{"id": "1", "messaging": [
            {"sender": {"id": "123"}, "message": {"mid": "m0", "text": ""}}
        ]}]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_meta_payload(payload, "facebook")
            assert count == 0
            store.assert_not_called()


class TestProcessXPayload:
    def test_dm_event(self):
        payload = {"direct_message_events": [
            {"type": "message_create", "id": "dm1",
             "message_create": {"sender_id": "999",
                                "message_data": {"text": "Hi there"}}}
        ]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_x_payload(payload)
            assert count == 1
            args = store.call_args[0]
            assert args[1] == "dm1"
            assert args[2] == "999"
            assert args[3] == "Hi there"

    def test_tweet_event(self):
        payload = {"tweet_create_events": [
            {"id_str": "t1", "text": "Hello world",
             "user": {"id": "1", "name": "Wes", "screen_name": "wesley"}}
        ]}
        with patch("marketing_system.services.platform_webhooks._store_incoming") as store:
            count = platform_webhooks.process_x_payload(payload)
            assert count == 1
            args = store.call_args[0]
            assert args[2] == "Wes"
            assert args[3] == "Hello world"


class TestIncomingMessageFormat:
    def test_build_message_includes_fields(self):
        text = _build_message("incoming", {
            "platform": "facebook",
            "sender": "Alice",
            "content": "請問方案價格？",
        })
        assert "社群進站訊息" in text
        assert "facebook" in text
        assert "Alice" in text
        assert "請問方案價格" in text
