"""個人工具：計算 / 筆記 / 提醒 / 語音辨識，以及 bot 功能清單防魔飾。"""
from datetime import datetime, timedelta

import pytest

from marketing_system.database import execute, fetch_one
from marketing_system.services import ai_tools, openclaw_agent as oa
from marketing_system.services import personal_tools as pt
from marketing_system.services import telegram_policy as tp


INTERNAL = "-1003739611959"
EXTERNAL = "-999888777"


@pytest.fixture
def user_client(client):
    execute(
        "INSERT INTO users (username, email, password_hash, salt, token, is_admin, is_active, plan) "
        "VALUES (?, ?, ?, ?, ?, 0, 1, 'free')",
        ["tools_user", "tools@test.com", "x", "s", "tools-token"],
    )
    client.cookies.set("token", "tools-token")
    return client


@pytest.fixture(autouse=True)
def no_cooldown(monkeypatch):
    monkeypatch.setattr(oa, "_throttled", lambda *a, **k: False)
    monkeypatch.setattr(oa, "_send_message", lambda *a, **k: None)
    monkeypatch.setattr(oa, "_send_photo", lambda *a, **k: None)


# ── 計算 ───────────────────────────────────────────────────────────
def test_calculate_supports_math_and_rejects_code():
    assert pt.calculate("(1+2)*3") == "9"
    assert pt.calculate("sqrt(16)+pi") != ""
    assert pt.calculate("2^10") == "1024"
    with pytest.raises(ValueError):
        pt.calculate("__import__('os')")
    with pytest.raises(ValueError):
        pt.calculate("1/0")


def test_calculate_api_is_public(client):
    r = client.post("/api/tools/calculate", json={"expression": "10/4"})
    assert r.status_code == 200
    assert r.json()["result"] == "2.5"


# ── 筆記 ───────────────────────────────────────────────────────────
def test_notes_are_isolated_by_owner():
    a = pt.add_note("user:1", "甲的筆記", "工作")
    b = pt.add_note("user:2", "乙的筆記")
    assert [n["content"] for n in pt.list_notes("user:1")] == ["甲的筆記"]
    assert pt.get_note("user:1", b["id"]) is None
    assert pt.delete_note("user:1", b["id"]) is False
    assert pt.delete_note("user:1", a["id"]) is True
    assert pt.list_notes("user:1") == []


def test_notes_api_crud(user_client):
    r = user_client.post("/api/tools/notes", json={"content": "買牛奶", "tags": "生活"})
    assert r.status_code == 200
    nid = r.json()["item"]["id"]
    assert user_client.get("/api/tools/notes").json()["items"][0]["content"] == "買牛奶"
    assert len(user_client.get("/api/tools/notes?q=牛奶").json()["items"]) == 1
    assert user_client.delete(f"/api/tools/notes/{nid}").status_code == 200
    assert user_client.delete(f"/api/tools/notes/{nid}").status_code == 404


def test_notes_api_requires_login(client):
    assert client.get("/api/tools/notes").status_code == 401
    assert client.post("/api/tools/notes", json={"content": "x"}).status_code == 401


# ── 提醒 ───────────────────────────────────────────────────────────
def test_parse_due_relative_and_absolute():
    now = datetime(2026, 11, 27, 12, 0, 0)
    assert pt.parse_due("30分鐘後", now) == now + timedelta(minutes=30)
    assert pt.parse_due("2小時後", now) == now + timedelta(hours=2)
    assert pt.parse_due("2026-11-28 10:00", now) == datetime(2026, 11, 28, 10, 0)


def test_due_reminders_dispatch_and_cancel():
    soon = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    r = pt.add_reminder("chat:1", "喝水", soon, chat_id="111")
    execute("UPDATE reminders SET due_at=datetime('now','-1 second') WHERE id=?", [r["id"]])
    sent = []
    result = pt.dispatch_due(lambda cid, text: sent.append((cid, text)) or True)
    assert result == {"sent": 1, "failed": 0, "retried": 0}
    assert sent == [("111", "⏰ 提醒：喝水")]
    assert pt.get_reminder("chat:1", r["id"])["status"] == "sent"
    assert pt.cancel_reminder("chat:1", r["id"]) is False


def test_dispatch_retries_then_fails():
    soon = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    r = pt.add_reminder("chat:2", "開會", soon, chat_id="222")
    execute("UPDATE reminders SET due_at=datetime('now','-1 second') WHERE id=?", [r["id"]])
    assert pt.dispatch_due(lambda *a: False) == {"sent": 0, "failed": 0, "retried": 1}
    execute("UPDATE reminders SET due_at=datetime('now','-1 second') WHERE id=?", [r["id"]])
    assert pt.dispatch_due(lambda *a: False) == {"sent": 0, "failed": 0, "retried": 1}
    execute("UPDATE reminders SET due_at=datetime('now','-1 second') WHERE id=?", [r["id"]])
    assert pt.dispatch_due(lambda *a: False) == {"sent": 0, "failed": 1, "retried": 0}
    assert pt.get_reminder("chat:2", r["id"])["status"] == "failed"


def test_take_due_marks_website_reminder():
    soon = (datetime.now() + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    r = pt.add_reminder("user:9", "繳費", soon)
    execute("UPDATE reminders SET due_at=datetime('now','-1 second') WHERE id=?", [r["id"]])
    rows = pt.take_due("user:9")
    assert [r["text"] for r in rows] == ["繳費"]
    assert pt.take_due("user:9") == []


def test_reminders_api_crud(user_client):
    r = user_client.post("/api/tools/reminders", json={"text": "開會", "due_at": "30分鐘後"})
    assert r.status_code == 200
    rid = r.json()["item"]["id"]
    items = user_client.get("/api/tools/reminders").json()["items"]
    assert items[0]["text"] == "開會"
    assert user_client.delete(f"/api/tools/reminders/{rid}").status_code == 200
    assert user_client.delete(f"/api/tools/reminders/{rid}").status_code == 404


def test_reminder_rejects_past_time(user_client):
    r = user_client.post("/api/tools/reminders", json={"text": "遲到", "due_at": "2020-01-01 10:00"})
    assert r.status_code == 400


# ── 語音辨識 ───────────────────────────────────────────────────────
def test_transcribe_uses_groq_whisper(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured = {}

    class FakeResp:
        ok = True

        def json(self):
            return {"text": "  你好，世界 "}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    assert ai_tools.transcribe(b"AUDIO", "voice.ogg") == "你好，世界"
    assert "groq.com" in captured["url"]
    assert captured["data"]["model"] == "whisper-large-v3"
    assert captured["files"]["file"][0] == "voice.ogg"


def test_transcribe_falls_back_to_openai(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    seen = {}

    class FakeResp:
        ok = True

        def json(self):
            return {"text": "hello"}

    monkeypatch.setattr(
        "requests.post",
        lambda url, **kw: (seen.update(url=url, data=kw.get("data")) or FakeResp()),
    )
    assert ai_tools.transcribe(b"AUDIO") == "hello"
    assert "openai.com" in seen["url"]
    assert seen["data"]["model"] == "whisper-1"


def test_transcribe_without_key_returns_503_style_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ai_tools.stt_available() is False
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        ai_tools.transcribe(b"AUDIO")


def test_transcribe_api_requires_login_and_bumps_usage(user_client, monkeypatch):
    monkeypatch.setattr(ai_tools, "transcribe", lambda raw, name, lang: "測試轉文字")
    r = user_client.post(
        "/api/tools/transcribe",
        files={"file": ("voice.ogg", b"AUDIO", "audio/ogg")},
    )
    assert r.status_code == 200
    assert r.json() == {"text": "測試轉文字"}
    status = user_client.get("/api/license/status").json()
    assert status["usage"]["tool"]["ai_transcribe"]["used"] == 1


def test_transcribe_api_requires_login(client):
    r = client.post("/api/tools/transcribe", files={"file": ("voice.ogg", b"AUDIO")})
    assert r.status_code == 401


# ── Bot 指令 ───────────────────────────────────────────────────────
def test_bot_calc_command():
    assert "9" in oa._handle_command(EXTERNAL, "計算", "(1+2)*3")
    assert "不支援" in oa._handle_command(EXTERNAL, "calc", "__import__('os')")


def test_bot_notes_and_reminders_use_chat_owner():
    out = oa._handle_command(INTERNAL, "筆記", "待辦：回覆信件")
    assert "已記錄" in out
    assert "回覆信件" in oa._handle_command(INTERNAL, "筆記", "列表")
    assert "回覆信件" not in oa._handle_command(EXTERNAL, "筆記", "列表")
    out = oa._handle_command(INTERNAL, "提醒", "30分鐘後 喝水")
    assert "已設定" in out
    assert "喝水" in oa._handle_command(INTERNAL, "提醒", "列表")


def test_new_internal_commands_blocked_externally():
    for cmd in ("筆記", "note", "提醒", "remind", "語音", "voice", "生圖", "image"):
        assert tp.command_internal_only(cmd) is True
    assert tp.command_internal_only("計算") is False
    assert "/計算" in oa._cmd_help(EXTERNAL)
    assert "/筆記" not in oa._cmd_help(EXTERNAL)
    assert "/筆記" in oa._cmd_help(INTERNAL)


def test_voice_message_only_for_internal_chat(monkeypatch):
    monkeypatch.setattr(oa, "_download_telegram_file", lambda fid: b"AUDIO")
    monkeypatch.setattr(ai_tools, "transcribe", lambda raw, name: "轉出的文字")
    msg = {"message_id": 3, "chat": {"id": INTERNAL, "type": "supergroup"},
           "voice": {"file_id": "abc"}}
    assert "轉出的文字" in oa.process_voice(msg)
    msg["chat"]["id"] = EXTERNAL
    assert oa.process_voice(msg) is None


def test_process_update_sends_transcription_for_voice(monkeypatch):
    sent = []
    monkeypatch.setattr(
        oa, "_send_result", lambda cid, result, reply_to=None: sent.append((cid, result))
    )
    monkeypatch.setattr(oa, "process_voice", lambda msg: "🎤 轉文字")
    update = {"message": {
        "message_id": 8,
        "chat": {"id": INTERNAL, "type": "supergroup"},
        "voice": {"file_id": "abc"},
    }}
    oa._process_update(update)
    assert sent == [(INTERNAL, "🎤 轉文字")]


def test_capability_question_uses_help_not_ai(monkeypatch):
    seen = []
    monkeypatch.setattr(oa, "_send_message", lambda cid, text: seen.append(text))
    update = {"message": {
        "message_id": 9,
        "chat": {"id": INTERNAL, "type": "supergroup"},
        "text": "@ailunora_bot 列出所有可執行功能",
    }}
    oa._process_update(update)
    assert seen
    assert "/help" in seen[0] or "指令列表" in seen[0]
    assert "/計算" in seen[0] and "/筆記" in seen[0]
