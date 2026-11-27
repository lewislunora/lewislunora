"""OpenClaw Telegram Agent：授權與指令處理。"""
from marketing_system.services import openclaw_agent as oa


def test_is_authorized_accepts_multiple_chat_ids(monkeypatch):
    monkeypatch.setattr(oa, "ALLOWED_CHAT_IDS", ["111223344", "626453598"])
    assert oa._is_authorized("111223344") is True
    assert oa._is_authorized("626453598") is True
    assert oa._is_authorized("999") is False


def test_is_authorized_fallback_to_notify_chat(monkeypatch):
    monkeypatch.setattr(oa, "ALLOWED_CHAT_IDS", ["626453598"])
    assert oa._is_authorized("626453598") is True
    assert oa._is_authorized("777") is False
