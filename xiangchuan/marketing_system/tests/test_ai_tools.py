"""翻譯 / 生圖 / 整合搜尋：服務層、API 與 bot 指令。"""
import base64

import pytest

from marketing_system.database import execute
from marketing_system.services import ai_tools, openclaw_agent as oa
from marketing_system.services import telegram_policy as tp


INTERNAL = "-1003739611959"
EXTERNAL = "-999888777"


@pytest.fixture
def user_client(client):
    execute(
        "INSERT INTO users (username, email, password_hash, salt, token, is_admin, is_active, plan) "
        "VALUES (?, ?, ?, ?, ?, 0, 1, 'free')",
        ["tool_user", "tool@test.com", "x", "s", "tool-token"],
    )
    client.cookies.set("token", "tool-token")
    return client


@pytest.fixture(autouse=True)
def no_cooldown(monkeypatch):
    monkeypatch.setattr(oa, "_throttled", lambda *a, **k: False)
    monkeypatch.setattr(oa, "_send_message", lambda *a, **k: None)
    monkeypatch.setattr(oa, "_send_photo", lambda *a, **k: None)


# ── 服務層 ────────────────────────────────────────────────────────
def test_translate_uses_target_language_and_returns_only_translation(monkeypatch):
    monkeypatch.setattr("marketing_system.ai.generator.AIContentGenerator.is_available", lambda self: True)
    seen = {}

    def fake_generate(self, template, variables):
        seen.update(variables)
        return "Artificial intelligence is changing how we work."

    monkeypatch.setattr("marketing_system.ai.generator.AIContentGenerator.generate", fake_generate)
    out = ai_tools.translate("人工智能正在改變我們的工作方式。", "en")
    assert out == "Artificial intelligence is changing how we work."
    assert "英文" in seen["prompt"]
    assert "只輸出譯文" in seen["prompt"]


def test_translate_raises_when_groq_missing(monkeypatch):
    monkeypatch.setattr("marketing_system.ai.generator.AIContentGenerator.is_available", lambda self: False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        ai_tools.translate("hello", "zh-TW")


def test_image_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ai_tools.image_available() is False
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ai_tools.generate_image("a cat")


def test_image_rejects_bad_size(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with pytest.raises(ValueError, match="size"):
        ai_tools.generate_image("a cat", "999x999")


def test_generate_image_decodes_b64(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

    class FakeResp:
        ok = True

        def json(self):
            return {"data": [{
                "b64_json": base64.b64encode(b"PNGDATA").decode(),
                "revised_prompt": "a fluffy cat",
            }]}

    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    raw, revised = ai_tools.generate_image("a cat", "1792x1024")
    assert raw == b"PNGDATA"
    assert revised == "a fluffy cat"
    assert captured["json"]["size"] == "1792x1024"
    assert captured["json"]["model"] == "gpt-image-1"
    assert captured["json"]["response_format"] == "b64_json"


def test_search_combines_gov_and_kb(monkeypatch):
    monkeypatch.setattr(
        ai_tools, "fetch",
        lambda sql, params: [{"keywords": '["空污"]', "answer": "空氣品質指標 AQI"}],
    )
    monkeypatch.setattr(
        "marketing_system.services.govdata.search",
        lambda q, per_page=20: {"items": [{
            "nid": "123", "title": "空氣品質監測", "agency": "環保署", "formats": "CSV",
        }]},
    )
    items = ai_tools.search("空氣品質", "all", 5)
    assert [i["type"] for i in items] == ["gov", "kb"]
    assert items[0]["url"].endswith("nid=123")
    assert "空氣品質指標" in items[1]["detail"]


def test_search_web_uses_roamer(monkeypatch):
    class FakeRoamer:
        def __init__(self, data_dir=None):
            pass

        def search(self, q, max_results=5):
            return [{"title": "結果", "url": "https://example.com", "engine": "ddg"}]

    monkeypatch.setattr("marketing_system.services.web_roamer.WebRoamer", FakeRoamer)
    items = ai_tools.search("AI", "web")
    assert items == [{"type": "web", "title": "結果", "url": "https://example.com", "detail": "ddg"}]


# ── API ───────────────────────────────────────────────────────────
def test_translate_api_requires_login(client, monkeypatch):
    monkeypatch.setattr("marketing_system.ai.generator.AIContentGenerator.is_available", lambda self: True)
    r = client.post("/api/ai/translate", json={"text": "你好", "target": "en"})
    assert r.status_code == 401


def test_translate_api_returns_text_and_bumps_usage(user_client, monkeypatch):
    monkeypatch.setattr("marketing_system.ai.generator.AIContentGenerator.is_available", lambda self: True)
    monkeypatch.setattr("marketing_system.ai.generator.AIContentGenerator.generate", lambda self, t, v: "Hello")
    r = user_client.post("/api/ai/translate", json={"text": "你好", "target": "en"})
    assert r.status_code == 200
    assert r.json() == {"text": "Hello"}

    status = user_client.get("/api/license/status").json()
    assert status["usage"]["tool"]["ai_translate"]["used"] == 1


def test_image_api_returns_data_url(user_client, monkeypatch):
    monkeypatch.setattr(ai_tools, "generate_image", lambda p, s: (b"PNGDATA", "revised"))
    r = user_client.post("/api/ai/image", json={"prompt": "a cat"})
    assert r.status_code == 200
    data = r.json()
    assert data["image"].startswith("data:image/png;base64,")
    assert base64.b64decode(data["image"].split(",", 1)[1]) == b"PNGDATA"
    assert data["revised_prompt"] == "revised"


def test_image_api_without_key_returns_503(user_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = user_client.post("/api/ai/image", json={"prompt": "a cat"})
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json()["detail"]


def test_search_api_is_public(client, monkeypatch):
    monkeypatch.setattr(ai_tools, "search", lambda q, scope, limit: [{"type": "kb", "title": q}])
    r = client.post("/api/ai/search", json={"q": "test", "scope": "kb"})
    assert r.status_code == 200
    assert r.json()["items"][0]["title"] == "test"


# ── Bot 指令 ──────────────────────────────────────────────────────
def test_bot_translate_auto_detects_target(monkeypatch):
    seen = {}
    monkeypatch.setattr(ai_tools, "translate", lambda text, target: (seen.update(text=text, target=target) or "OK"))
    out = oa._handle_command(INTERNAL, "翻譯", "人工智能正在改變世界")
    assert "OK" in out
    assert seen == {"text": "人工智能正在改變世界", "target": "en"}


def test_bot_translate_explicit_target(monkeypatch):
    seen = {}
    monkeypatch.setattr(ai_tools, "translate", lambda text, target: (seen.update(text=text, target=target) or "OK"))
    oa._handle_command(EXTERNAL, "translate", "zh-TW: Good morning")
    assert seen == {"text": "Good morning", "target": "zh-TW"}


def test_bot_search_formats_results(monkeypatch):
    monkeypatch.setattr(ai_tools, "search", lambda q, scope, limit: [
        {"type": "gov", "title": "空氣品質", "url": "/govdata?nid=1", "detail": "環保署"},
    ])
    out = oa._handle_command(EXTERNAL, "搜尋", "空氣品質")
    assert "空氣品質" in out
    assert "/govdata?nid=1" in out
    assert "環保署" in out


def test_bot_image_returns_photo_dict(monkeypatch):
    monkeypatch.setattr(ai_tools, "generate_image", lambda p, s: (b"PNGDATA", "a cat"))
    out = oa._handle_command(INTERNAL, "生圖", "1792x1024 a cat")
    assert isinstance(out, dict)
    assert out["photo"] == b"PNGDATA"
    assert "a cat" in out["caption"]


def test_bot_image_is_internal_only():
    assert tp.command_internal_only("生圖") is True
    assert tp.command_internal_only("image") is True
    assert tp.command_internal_only("搜尋") is False
    internal_help = oa._cmd_help(INTERNAL)
    external_help = oa._cmd_help(EXTERNAL)
    assert "/生圖" in internal_help
    assert "/生圖" not in external_help
    assert "/搜尋" in external_help


def test_process_update_sends_photo_for_image_command(monkeypatch):
    sent = []
    monkeypatch.setattr(oa, "_send_photo", lambda cid, png, caption="", reply_to=None: sent.append((cid, png, caption)))
    monkeypatch.setattr(ai_tools, "generate_image", lambda p, s: (b"PNGDATA", "a cat"))
    update = {"message": {
        "message_id": 7,
        "chat": {"id": INTERNAL, "type": "supergroup"},
        "text": "@ailunora_bot /生圖 a cat",
    }}
    oa._process_update(update)
    assert len(sent) == 1
    assert sent[0][1] == b"PNGDATA"
