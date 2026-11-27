"""Telegram 互動政策：對內 / 對外身份判定與路由規則。"""
from marketing_system.services import telegram_policy as tp


INTERNAL = "-1003739611959"
CHANNEL = "-1003937328575"
OWNER = "626453598"
EXTERNAL = "-999888777"


def _msg(chat_id, text, chat_type="supergroup", title="外部群"):
    return {
        "message_id": 1,
        "chat": {"id": chat_id, "type": chat_type, "title": title},
        "text": text,
    }


def test_internal_and_linked_recognized():
    assert tp.is_internal(INTERNAL) is True
    assert tp.is_internal(OWNER) is True
    assert tp.is_linked_channel(CHANNEL) is True
    assert tp.is_external(EXTERNAL) is True


def test_internal_group_free_text_does_not_need_mention():
    assert tp.should_respond(_msg(INTERNAL, "測試 AI 回覆")) is True
    assert tp.requires_mention(INTERNAL, "supergroup") is False


def test_external_group_needs_mention_and_opt_in(monkeypatch):
    monkeypatch.setattr(tp, "EXTERNAL_CHAT_IDS", set())
    assert tp.should_respond(_msg(EXTERNAL, "你好")) is False
    assert tp.should_respond(_msg(EXTERNAL, "@ailunora_bot 你好")) is False

    monkeypatch.setattr(tp, "EXTERNAL_CHAT_IDS", {EXTERNAL})
    assert tp.should_respond(_msg(EXTERNAL, "你好")) is False
    assert tp.should_respond(_msg(EXTERNAL, "@ailunora_bot 你好")) is True


def test_private_chat_keeps_kb_service():
    assert tp.should_respond(_msg(12345, "方案與價格", chat_type="private")) is True
    assert tp.requires_mention(12345, "private") is False


def test_command_whitelist_by_identity():
    assert tp.allowed_commands(INTERNAL) == tp.ALL_COMMANDS
    assert tp.allowed_commands(EXTERNAL) == tp.PUBLIC_COMMANDS
    for cmd in ("自動化", "auto", "部署", "deploy", "狀態", "status"):
        assert tp.command_internal_only(cmd) is True
    for cmd in ("start", "help", "靈感", "idea"):
        assert tp.command_internal_only(cmd) is False


def test_clean_text_strips_bot_tag_and_command_suffix():
    assert tp.clean_text("/help@ailunora_bot", "supergroup") == "/help"
    assert tp.clean_text("@ailunora_bot 你好", "supergroup") == "你好"
    assert tp.clean_text("/自動化 AI 行銷", "private") == "/自動化 AI 行銷"


def test_empty_or_non_text_message_ignored():
    assert tp.should_respond(_msg(INTERNAL, "")) is False
    assert tp.should_respond({"chat": {"id": INTERNAL, "type": "supergroup"}}) is False
