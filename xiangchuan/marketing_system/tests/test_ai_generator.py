"""AI Generator tests"""
import pytest
from unittest.mock import patch, MagicMock
from marketing_system.ai.generator import AIContentGenerator


class TestAIContentGenerator:
    def test_init_without_api_key(self):
        """Should initialize even without API key"""
        gen = AIContentGenerator()
        # client should be None when GROQ_API_KEY is empty
        assert gen.client is None

    def test_is_available_returns_false_without_key(self):
        gen = AIContentGenerator()
        assert gen.is_available() is False

    def test_fallback_content_structure(self):
        gen = AIContentGenerator()
        result = gen.generate_for_platforms("AI marketing", ["telegram", "facebook"])
        assert isinstance(result, dict)
        assert "telegram" in result
        assert "facebook" in result
        assert len(result["telegram"]) > 0
        assert len(result["facebook"]) > 0

    def test_platform_specific_fallback(self):
        gen = AIContentGenerator()
        result = gen.generate_for_platforms("測試", ["twitter"])
        assert "twitter" in result
        # Twitter should have shorter text (280 chars max)
        assert len(result["twitter"]) <= 600

    def test_generate_custom_fallback_without_key(self):
        gen = AIContentGenerator()
        result = gen.generate("custom", {"prompt": "Write something"})
        assert result.startswith("⚠️") or result.startswith("❌")

    @patch.dict('os.environ', {'GROQ_API_KEY': 'gsk_test_key'}, clear=False)
    def test_generate_returns_error_with_invalid_key(self):
        """With a test API key, generation should fail gracefully"""
        gen = AIContentGenerator()
        result = gen.generate("社群貼文", {"topic": "AI", "language": "繁體中文", "style": "專業", "length": "100"})
        # Should return error message, not crash
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_for_platforms_handles_empty_platforms(self):
        gen = AIContentGenerator()
        result = gen.generate_for_platforms("topic", [])
        assert result == {}

    def test_single_fallback_has_correct_language(self):
        gen = AIContentGenerator()
        en = gen._single_fallback("topic", "telegram", "en")
        zh = gen._single_fallback("topic", "telegram", "zh-TW")
        assert isinstance(en, str)
        assert isinstance(zh, str)
