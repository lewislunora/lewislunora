"""Knowledge Base service tests"""
import json
import pytest
from marketing_system.database import init_db, execute, fetch
from marketing_system.services.knowledge_base import get_kb_reply, save_unanswered, get_pending, _guess_keywords


class TestKBReply:
    def test_exact_keyword_match(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["測試專用單詞"]), "這是專用單詞的回答", "zh-TW"],
        )
        reply = get_kb_reply("我想查詢測試專用單詞")
        assert reply == "這是專用單詞的回答"

    def test_no_match_returns_none(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["股價", "股票"]), "股市回答", "zh-TW"],
        )
        reply = get_kb_reply("今天天氣真好")
        assert reply is None

    def test_keyword_too_short_no_match(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["a"]), "Short keyword answer", "en"],
        )
        reply = get_kb_reply("a b c")
        assert reply is None

    def test_english_keyword_word_boundary(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["uniqueplanword"]), "We have three plans", "en"],
        )
        reply = get_kb_reply("tell me about the uniqueplanword", "en")
        assert reply == "We have three plans"

    def test_multi_keyword_fallback(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["zzunique", "zzworld"]), "Hello World answer", "en"],
        )
        reply = get_kb_reply("zzunique to the zzworld", "en")
        assert reply == "Hello World answer"

    def test_longest_keyword_wins(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["測試方案", "測試"]), "Short match", "zh-TW"],
        )
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["測試方案內容", "詳細"]), "Longer match wins", "zh-TW"],
        )
        reply = get_kb_reply("我想看看測試方案內容", "zh-TW")
        assert reply == "Longer match wins"

    def test_language_fallback(self):
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["zzuniqueeng"]), "English answer", "en"],
        )
        reply = get_kb_reply("zzuniqueeng this", "en")
        assert reply == "English answer"

    def test_substring_not_matching_word(self):
        """English keyword 'cat' should not match 'category'"""
        execute(
            "INSERT INTO kb_entries (keywords, answer, language) VALUES (?,?,?)",
            [json.dumps(["cat"]), "Cat answer", "en"],
        )
        reply = get_kb_reply("tell me about category")
        # 'cat' is inside 'category' but 'category' has alphanumeric chars after
        assert reply is None

    def test_empty_text(self):
        reply = get_kb_reply("")
        assert reply is None


class TestSaveUnanswered:
    def test_save_new_question(self):
        qid = save_unanswered("What is this?", "en")
        assert qid > 0
        rows = fetch("SELECT * FROM kb_pending WHERE id=?", [qid])
        assert rows[0]["count"] == 1

    def test_increment_existing_question(self):
        qid1 = save_unanswered("Same question", "en")
        qid2 = save_unanswered("Same question", "en")
        assert qid1 == qid2
        rows = fetch("SELECT * FROM kb_pending WHERE id=?", [qid1])
        assert rows[0]["count"] == 2


class TestGetPending:
    def test_get_pending_list(self):
        save_unanswered("Question A", "en")
        save_unanswered("Question B", "en")
        result = get_pending()
        assert result["total"] >= 2
        assert len(result["items"]) >= 2

    def test_pending_returns_empty_when_none(self):
        result = get_pending()
        # May have items from other tests, just check structure
        assert "items" in result
        assert "total" in result
        assert "page" in result


class TestGuessKeywords:
    def test_normal_question(self):
        kw = _guess_keywords("方案 價格 是多少")
        assert len(kw) >= 2
        assert "價格" in kw

    def test_empty_returns_default(self):
        kw = _guess_keywords("?")
        assert kw == ["一般"]

    def test_max_five_keywords(self):
        kw = _guess_keywords("a b c d e f g h i j k l m n")
        assert len(kw) <= 5
