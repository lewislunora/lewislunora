"""自然語言意圖判讀 + 群組聊天習慣自我學習（只存統計，不存原文）。"""
from unittest.mock import patch

import pytest

from marketing_system.services import bot_learning as learning
from marketing_system.services import openclaw_agent as oa

INTERNAL = "-1003739611959"
EXTERNAL = "-999888777"


# ── 意圖判讀：AI 只能選代號，不能自由承諾功能 ─────────────────────────

@pytest.mark.parametrize("text,intent", [
    ("列出所有可執行功能", "help"),
    ("我要怎麼關閉OpenClaw AI 助手", "stop"),
    ("停止這個 bot", "stop"),
    ("情感分析 分析Wesley Lee情感狀態", "unsupported"),
    ("做個訊息開關觸發邏輯", "unsupported"),
    ("計算 (1+2)*3", "calc"),
    ("算一下 sqrt(16)", "calc"),
    ("翻譯這句話成英文", "translate"),
    ("記一下 買牛奶", "note"),
    ("提醒我 30分鐘後 喝水", "remind"),
])
def test_deterministic_intents(text, intent):
    assert oa.classify_intent(text)[0] == intent


def test_ai_may_only_choose_from_allowlist(monkeypatch):
    monkeypatch.setattr(oa.ai_gen, "is_available", lambda: True)
    monkeypatch.setattr(oa.ai_gen, "generate", lambda system, payload: "情感分析、語音撥打")
    assert oa.classify_intent("随便聊聊")[0] == "faq"

    monkeypatch.setattr(oa.ai_gen, "generate", lambda system, payload: "calc\n(1+2)*3")
    assert oa.classify_intent("幫我算 things")[0] == "calc"


def test_ai_prompt_is_a_classifier_not_an_answer_machine(monkeypatch):
    seen = {}
    monkeypatch.setattr(oa.ai_gen, "is_available", lambda: True)

    def fake_generate(system, payload):
        seen["prompt"] = payload["prompt"]
        return "unsupported"

    monkeypatch.setattr(oa.ai_gen, "generate", fake_generate)
    oa.classify_intent("隨便聊聊今天")
    assert "只輸出一行代號" in seen["prompt"]
    assert "絕對不要輸出代號表以外" in seen["prompt"]


# ── 自然語言路由 ──────────────────────────────────────────────────────

def test_close_assistant_gets_fixed_whitelist_not_idea(monkeypatch):
    called = []
    monkeypatch.setattr(oa, "_cmd_idea", lambda text: called.append(text) or "不該出現")
    reply = oa.route_natural_language("我要怎麼關閉OpenClaw AI 助手", INTERNAL)
    assert "安靜" in reply and "站長" in reply  # 口語但仍給出確切做法
    assert called == []


def test_sentiment_request_is_refused_without_ai(monkeypatch):
    monkeypatch.setattr(oa.ai_gen, "is_available", lambda: (_ for _ in ()).throw(AssertionError("不該呼叫 AI")))
    reply = oa.route_natural_language("情感分析 分析Wesley Lee情感狀態", EXTERNAL)
    assert "還不會" in reply
    assert "/help" in reply


def test_natural_language_calculation_works_without_slash():
    reply = oa.route_natural_language("計算 (1+2)*3", EXTERNAL)
    assert "= " in reply and "9" in reply


def test_ai_entry_routes_natural_language():
    reply = oa._handle_command(EXTERNAL, "ai", "計算 sqrt(16)")
    assert "= " in reply and "4" in reply


def test_internal_only_intent_blocked_externally():
    reply = oa.route_natural_language("記一下 買牛奶", EXTERNAL)
    assert "僅供對內群組" in reply


def test_start_hides_internal_features_in_external_group():
    public = oa._cmd_start(EXTERNAL)
    for feature in ("筆記", "提醒", "語音", "生圖", "部署", "狀態"):
        assert feature not in public
    internal = oa._cmd_start(INTERNAL)
    assert "筆記" in internal


def test_unknown_question_is_remembered_for_auto_learn(monkeypatch):
    remembered = []
    monkeypatch.setattr(oa, "_remember_unanswered", lambda text: remembered.append(text))
    monkeypatch.setattr(oa.ai_gen, "is_available", lambda: True)
    monkeypatch.setattr(oa.ai_gen, "generate", lambda system, payload: "faq\n簡短回答")
    reply = oa.route_natural_language("這個問題很特別？", EXTERNAL)
    assert reply == "簡短回答"
    assert remembered == ["這個問題很特別？"]


# ── 聊天習慣學習 + 回覆長度 ──────────────────────────────────────────

def test_observe_stores_statistics_only():
    assert learning.observe(EXTERNAL, "請問方案價格多少？", is_question=True, force=True) is True
    profile = learning.profile(EXTERNAL)
    assert profile["samples"] == 1
    assert profile["questions"] == 1
    assert "方案價格" in profile["topics"]
    # 原文不能進駐 DB
    assert all("請問方案價格多少" not in str(v) for v in profile.values())


def test_reply_budget_learns_from_group_habit():
    for _ in range(6):
        learning.observe(EXTERNAL, "短\n兩行", force=True)
    max_lines, max_chars = learning.reply_budget(EXTERNAL)
    assert 1 <= max_lines <= 3
    assert 30 <= max_chars <= 60
    assert max_lines >= 2  # 學到群組常用兩句


def test_short_reply_never_exceeds_three_sentences_or_sixty_chars():
    text = "第一步先註冊。第二步再設定。第三步才上線。第四步會超標。"
    shortened = oa._shorten(text, chat_id=EXTERNAL)
    assert len(shortened) <= 60
    assert len(shortened.split("\n")) <= 3


def test_learning_failure_degrades_to_safe_default(monkeypatch):
    monkeypatch.setattr(learning, "fetch_one", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    assert learning.reply_budget(EXTERNAL) == (2, 45)
    assert learning.observe(EXTERNAL, "你好", force=True) is None


# ── Webhook 與 polling 共用同一套引擎 ─────────────────────────────────

def test_webhook_ai_entry_uses_intent_engine(client):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"}
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"ok": True}
        resp = client.post("/api/telegram/webhook", headers=headers, json={
            "message": {
                "chat": {"id": 777, "type": "private"},
                "text": "/ai 計算 (1+2)*3",
                "message_id": 1,
            }
        })
    assert resp.status_code == 200
    assert "9" in mock_post.call_args[1]["json"]["text"]
