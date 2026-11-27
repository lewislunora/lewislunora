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


def test_handle_command_auto_generates_automation_task():
    oa.ai_gen.is_available = lambda: True
    oa.ai_gen.generate = lambda system, payload: "自動化任務：每週自動產生內容靈感。"
    r = oa._handle_command(626453598, "自動化", "AI 行銷")
    assert "AI 自動化" in r
    assert "AI 行銷" in r
    assert "自動化任務" in r


def test_handle_command_auto_requires_ai():
    oa.ai_gen.is_available = lambda: False
    assert "未啟用" in oa._handle_command(626453598, "自動化", "")
