import json
import logging
from ..config import GROQ_API_KEY, GROQ_MODEL, GROQ_MAX_TOKENS
from ..database import fetch, fetch_one

logger = logging.getLogger(__name__)


class AIContentGenerator:
    def __init__(self):
        self.client = None
        if GROQ_API_KEY:
            try:
                from groq import Groq
                self.client = Groq(api_key=GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

    def is_available(self):
        return self.client is not None

    def generate(self, template_name, variables=None):
        if not self.is_available():
            return "⚠️ Groq API 未設定或額度已用盡。"

        variables = variables or {}
        prompt = variables.get("prompt", "")
        if not prompt:
            template = fetch_one(
                "SELECT prompt_template FROM ai_templates WHERE name=?",
                [template_name]
            )
            if not template:
                return f"❌ 找不到模板: {template_name}"
            prompt = template["prompt_template"].format(**variables)

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=GROQ_MAX_TOKENS,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return f"❌ API 錯誤: {e}"

    def generate_for_platforms(self, topic, platforms, language="zh-TW", style="專業"):
        if not self.is_available():
            return self._fallback_content(topic, platforms, language)

        results = {}
        for platform in platforms:
            prompt = (
                f"以{language}寫一篇關於「{topic}」的{platform}貼文。\n"
                f"語氣：{style}\n"
                f"要求：適合{platform}平台風格，開頭要吸引人，結尾加CTA。"
            )
            try:
                resp = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=GROQ_MAX_TOKENS,
                )
                results[platform] = resp.choices[0].message.content.strip()
            except Exception as e:
                results[platform] = self._single_fallback(topic, platform, language)
        return results

    def _fallback_content(self, topic, platforms, language):
        results = {}
        for platform in platforms:
            results[platform] = self._single_fallback(topic, platform, language)
        return results

    def _single_fallback(self, topic, platform, language):
        return (
            f"【{topic}】- {platform.upper()} 貼文\n\n"
            f"📌 {topic} 是現在最值得關注的趨勢。\n\n"
            f"無論你是剛起步還是想升級，現在就是最佳時機。\n\n"
            f"👉 了解更多：https://lewislunora.github.io/lewislunora/product/\n\n"
            f"#{topic.replace(' ', '')} #AI行銷 #自動化"
        )
