import json
import logging
from ..config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)


class AIStoryGenerator:
    """AI 短劇 / AI 動漫腳本自動化 — 用 GROQ 文字模型產生可發布的腳本與分鏡。

    說明：GROQ 目前是純文字模型，無法直接生成影片/圖片。
    本模組專注在「腳本→分鏡→配音稿→字幕」這條可以真正免費自動化的生產線，
    產出的腳本可直接搭配後續的影片生成工具（可靈/榮耀/Runway）使用。
    """

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

    def _call(self, prompt, temperature=0.8):
        if not self.is_available():
            return "⚠️ GROQ_API_KEY 未設定，無法產生內容。請先在 Render 設定 GROQ_API_KEY。"
        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GROQ call failed: {e}")
            return f"⚠️ 呼叫失敗: {e}"

    def generate_short_drama(self, theme, char_count=2, length="60秒", tone="狗血反转"):
        """產生一部 AI 短劇的完整腳本（含分鏡與配音稿）。"""
        prompt = f"""你是一位專業的短影音編劇。請為一支{length}的短劇寫出完整製作腳本。

主題：{theme}
角色數量：{char_count}"
調性：{tone}

請嚴格依以下格式輸出（用繁體中文）：

【片名】
【一句話賣點】
【人物設定】
- 角色1：...
- 角色2：...

【分鏡腳本】（每行一個鏡頭，格式：鏡號|秒數|畫面描述|台詞）
1|0-3|...

【旁白/配音稿】
【結尾鉤子】（引導觀眾追蹤訂閱的一句話）

請確保節奏緊湊、有反轉、適合豎屏短影音。"""
        return self._call(prompt)

    def generate_anime_synopsis(self, theme, style="AI 奇幻"):
        """產生一部 AI 動漫的企劃（世界觀、角色、第一集大綱）。"""
        prompt = f"""你是一位動漫企劃。請為一部全新「{style}」AI 動漫寫出企劃。

主題：{theme}

請輸出（繁體中文）：
【作品名稱】
【世界觀設定】
【主角介紹】（含性格、能力、成長曲線）
【重要配角】2-3位
【第一集完整大綱】（起承轉合）
【核心受眾與賣點】"""
        return self._call(prompt, temperature=0.9)

    def generate_storyboard_prompts(self, script_text):
        """把短劇腳本轉成「每鏡的圖片生成提示詞」（供後續接 Runway/可靈/ComfyUI）。"""
        prompt = f"""以下是一部短劇腳本。請把每個鏡頭轉成「AI 圖片/影片生成提示詞」（英文，供 Midjourney/Runway 使用），
並標出每個鏡頭適合用的風格（realistic 或 anime）。

腳本：
---
{script_text}
---

輸出格式（每鏡一行）：
鏡號|風格風格|英文提示詞|負面提示詞(optional)"""
        return self._call(prompt, temperature=0.7)

    def package_publish(self, theme, tone="狗血反转"):
        """一鍵產出「可發布」的完整短劇包：腳本＋分鏡＋標題＋hashtag。"""
        script = self.generate_short_drama(theme, tone=tone)
        title = self._call(
            f"請為下面這部短劇取 5 個吸引眼球、適合抖音/IG Reels/YouTube Shorts 的繁體中文標題，並附 10 個相關 hashtag。\n\n{script}",
            temperature=0.9,
        )
        return {"script": script, "titles_and_tags": title}
