"""自然但不囉嗦：網站精靈與 Telegram bot 共用的回覆引擎。"""
from marketing_system.config import DOCS_DIR
from marketing_system.services import natural_reply as nr


class FakeGen:
    def __init__(self, text, available=True):
        self.text = text
        self.available = available
        self.prompt = ""

    def is_available(self):
        return self.available

    def generate(self, template, variables):
        self.prompt = variables.get("prompt", "")
        return self.text


# ── 字數與語氣 ────────────────────────────────────────────────────────

def test_reply_budget_is_short_and_bounded(monkeypatch):
    monkeypatch.setattr(nr.bot_learning, "reply_budget", lambda chat_id: (3, 60))
    lines, chars = nr.reply_budget("計算 (1+2)*3")
    assert 1 <= lines <= 3
    assert 30 <= chars <= 45  # 對方寫得短，不能回得像作文，也不能截成半句

    lines, chars = nr.reply_budget("想問的是" + "很多事情" * 40)
    assert (lines, chars) == (3, 60)  # 寫很長也只到硬上限 60 字


def test_polish_removes_boilerplate_and_caps_length():
    out = nr.polish("**好的**，以下是回覆：• 這句話其實很長很長很長。", 2, 15)
    assert "**" not in out
    assert "以下是" not in out
    assert not out.startswith("•")
    assert len(out) <= 15


def test_polish_handles_escaped_newlines_and_bullets():
    out = nr.polish("主要功能包括：\\n• AI 智能客服\\n• 自動發文", 2, 30)
    assert "\\n" not in out
    assert "•" not in out
    assert len(out) <= 30


def test_clip_never_ends_with_a_dangling_separator():
    out = nr.polish("嗨，我是翔川 Neo 助理，能算、筆記、翻譯、搜尋等等", 1, 20)
    assert len(out) <= 20
    assert not out.endswith(("、", "，", ","))
    assert out.endswith("…")


def test_reply_uses_kb_answer_directly():
    out = nr.reply("客服電話", kb_answer="客服電話是 0800-123-456，歡迎來電。")
    assert "0800" in out
    assert len(out) <= 45


def test_capability_question_uses_fixed_short_whitelist():
    gen = FakeGen("主要功能包括：\n• 客服\n• 發文\n• 生圖")
    out = nr.reply("你能做什麼？", generator=gen,
                   kb_answer="主要功能包括：\n• 客服\n• 發文\n• 生圖")
    assert "想先試哪個" in out
    assert "•" not in out
    assert len(out) <= 30


def test_reply_prompt_forces_natural_short_answer():
    gen = FakeGen("身為 AI，以下是說明：我可以幫你算數。要不要也試試翻譯？")
    out = nr.reply("你能幹嘛", generator=gen)
    assert "身為 AI" not in out
    assert "以下是" not in out
    assert len(out) <= 45
    assert "全段" in gen.prompt and "字以內" in gen.prompt
    assert "不要條列" in gen.prompt
    assert "不要編造" in gen.prompt
    assert "需要登入" in gen.prompt


def test_reply_never_leaks_api_errors():
    assert "❌" not in nr.reply("你好", generator=FakeGen("❌ API 錯誤: quota"))
    assert "再說一次" in nr.reply("你好", generator=FakeGen("⚠️ 未設定"))
    assert "稍後再問我" in nr.reply("你好", generator=FakeGen("ok", available=False))


def test_reply_uses_recent_history():
    gen = FakeGen("還行啦，你呢？")
    nr.reply("最近好嗎", generator=gen, history=[
        {"role": "user", "text": "我今天很累"},
        {"role": "ai", "text": "辛苦了"},
    ])
    assert "近期對話" in gen.prompt
    assert "我今天很累" in gen.prompt


# ── 公開端點：網站精靈與 bot 走同一顆引擎 ─────────────────────────────

def test_assistant_chat_endpoint(client, monkeypatch):
    monkeypatch.setattr(nr, "_DEFAULT_GEN", FakeGen("我可以幫你算數，要試試嗎？"))
    r = client.post("/api/assistant/chat", json={"text": "你能幫我什麼"})
    assert r.status_code == 200
    assert "算數" in r.json()["reply"]
    assert len(r.json()["reply"]) <= 45


def test_assistant_chat_rate_limit(client, monkeypatch):
    monkeypatch.setattr(nr, "_DEFAULT_GEN", FakeGen("好的，我懂。"))
    for _ in range(12):
        assert client.post("/api/assistant/chat", json={"text": "你好"}).status_code == 200
    limited = client.post("/api/assistant/chat", json={"text": "你好"}).json()
    assert limited.get("limited") is True


def test_assistant_chat_filters_spam(client, monkeypatch):
    monkeypatch.setattr(nr, "_DEFAULT_GEN", FakeGen("不該出現"))
    r = client.post("/api/assistant/chat", json={"text": "test@example.com 博彩"})
    assert r.json().get("filtered") is True
    assert "不該出現" not in r.json()["reply"]


def test_spirit_uses_shared_endpoint():
    src = (DOCS_DIR / "spirit.js").read_text(encoding="utf-8")
    assert "/api/assistant/chat" in src
    assert "history: S.history" in src
