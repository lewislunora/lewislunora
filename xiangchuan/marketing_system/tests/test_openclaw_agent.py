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


INTERNAL = "-1003739611959"
EXTERNAL = "-999888777"


def _update(chat_id, text, chat_type="supergroup"):
    return {"message": {"message_id": 1, "chat": {"id": chat_id, "type": chat_type}, "text": text}}


def test_process_update_ignores_external_group_without_mention(monkeypatch):
    sent = []
    monkeypatch.setattr(oa, "_send_message", lambda chat_id, text: sent.append((chat_id, text)))
    monkeypatch.setattr(oa, "ALLOWED_CHAT_IDS", [INTERNAL, EXTERNAL])
    monkeypatch.setattr(oa.policy, "EXTERNAL_CHAT_IDS", set())

    oa._process_update(_update(EXTERNAL, "你好"))
    assert sent == []


def test_process_update_internal_group_auto_replies(monkeypatch):
    sent = []
    monkeypatch.setattr(oa, "_send_message", lambda chat_id, text: sent.append((chat_id, text)))
    monkeypatch.setattr(oa.ai_gen, "is_available", lambda: True)
    monkeypatch.setattr(oa.ai_gen, "generate", lambda system, payload: "創意點子")
    monkeypatch.setattr(oa, "ALLOWED_CHAT_IDS", [INTERNAL])

    oa._process_update(_update(INTERNAL, "測試 AI 回覆"))
    assert len(sent) == 1
    assert "內容靈感" in sent[0][1]
    assert "創意點子" in sent[0][1]


def test_process_update_blocks_internal_only_command_in_external(monkeypatch):
    sent = []
    monkeypatch.setattr(oa, "_send_message", lambda chat_id, text: sent.append((chat_id, text)))
    monkeypatch.setattr(oa, "ALLOWED_CHAT_IDS", [INTERNAL, EXTERNAL])
    monkeypatch.setattr(oa.policy, "EXTERNAL_CHAT_IDS", set())

    oa._process_update(_update(EXTERNAL, "@ailunora_bot /部署"))
    assert len(sent) == 1
    assert "僅供對內群組" in sent[0][1]


def test_process_update_external_group_can_interact_with_ai(monkeypatch):
    sent = []
    monkeypatch.setattr(oa, "_send_message", lambda chat_id, text: sent.append((chat_id, text)))
    monkeypatch.setattr(oa.ai_gen, "is_available", lambda: True)
    monkeypatch.setattr(oa.ai_gen, "generate", lambda system, payload: "公開創意")
    monkeypatch.setattr(oa.policy, "EXTERNAL_CHAT_IDS", set())

    oa._process_update(_update(EXTERNAL, "@ailunora_bot 給我一點靈感"))
    assert len(sent) == 1
    assert "內容靈感" in sent[0][1]
    assert "公開創意" in sent[0][1]


def test_linked_channel_cannot_control_server(monkeypatch):
    sent = []
    channel = "-1003937328575"
    monkeypatch.setattr(oa, "_send_message", lambda chat_id, text: sent.append((chat_id, text)))
    monkeypatch.setattr(oa.policy, "EXTERNAL_CHAT_IDS", set())

    oa._process_update(_update(channel, "@ailunora_bot /狀態"))
    assert len(sent) == 1
    assert "僅供對內群組" in sent[0][1]


def test_help_hides_internal_commands_in_external():
    text = oa._cmd_help(EXTERNAL)
    assert "/靈感" in text
    assert "/自動化" not in text
    assert "/部署" not in text
    assert "/狀態" not in text
    assert "僅供對內群組" in text

    internal = oa._cmd_help(INTERNAL)
    assert "/自動化" in internal
    assert "/部署" in internal
