KB_KW = [
    ["方案", "價格", "費用", "多少錢", "pricing", "plan", "price", "cost"],
    ["功能", "能做什麼", "features", "capabilities"],
    ["平台", "支援", "platform", "support", "整合"],
    ["開始", "試用", "註冊", "start", "trial", "begin", "signup"],
    ["客服", "customer service", "support"],
    ["內容", "content", "文章", "生成"],
    ["知識庫", "knowledge base", "kb"],
    ["品牌", "brand", "app", "應用"],
    ["聯絡", "contact", "email", "電話", "line"],
    ["展示", "demo", "演示"],
    ["價格", "方案", "費用"],
    ["ai", "llm", "groq", "人工智慧"],
]

KB_MSG = {
    "zh-TW": [
        "我們提供三種方案：\n\n① 入門版：免費，50次/天\n② 專業版：NT$890/月，無限次數\n③ 企業版：NT$5,990/月，私有部署\n\n詳細比較請看 👉 https://lewislunora.onrender.com/product/#pricing",
        "主要功能包括：\n• AI 智能客服（24/7）\n• 自動內容生成（文章+社群）\n• 知識庫自增長\n• 多平台分發\n• 數據驅動優化\n• AI 短劇創作",
        "目前已支援：Telegram、Line、Facebook、Instagram。更多平台持續新增中。",
        "開始很簡單：\n1. 點擊「免費試用」按鈕\n2. 加入我們的 Telegram 頻道\n3. 設定你的知識庫\n4. AI 立即上線\n\n立即開始 👉 https://lewislunora.onrender.com/product/",
        "AI 客服可以 24/7 自動回覆客戶問題。支援多語言、知識庫自增長、串接多平台。專業版每月只要 NT$890。",
        "自動內容生成系統可以產出：品牌文章、社群貼文、行銷文案、電子報、短劇劇本。支援中英雙語。",
        "知識庫是 AI 客服的核心。好的回答會自動保存，不好的會被淘汰。支援 👍/👎 回饋機制，越用越聰明。",
        "品牌 App 使用 Flutter 開發，同時支援 iOS、Android 和 Web。內容從 JSON 讀取，無需後端即可更新。",
        "歡迎聯絡我們：\n📧 lewislunora@gmail.com\n✈️ Telegram 頻道：https://t.me/+QgAyWlVyIxFjNmRl\n🤖 客服機器人：@ailunora_bot",
        "觀看即時展示 👉 直接在上方聊天室輸入問題，體驗 AI 客服回覆。或前往商品頁查看完整介紹。",
        "專業版 NT$890/月 · 企業版 NT$5,990/月。14 天免費試用，無需信用卡。",
        "系統使用 Groq Llama 3 LLM 驅動，支援智慧對話、內容生成、情感分析等功能。",
    ],
    "en": [
        "We offer 3 plans:\n① Starter: Free, 50 chats/day\n② Pro: $29/mo, unlimited\n③ Enterprise: $199/mo, private deployment\n\nSee details 👉 https://lewislunora.onrender.com/product/#pricing",
        "Key features:\n• AI Customer Service (24/7)\n• Auto Content Generation\n• Self-Growing Knowledge Base\n• Multi-Platform Distribution\n• Data-Driven Optimization",
        "Supported platforms: Telegram, Line, Facebook, Instagram. More coming soon.",
        "Getting started:\n1. Click \"Free Trial\"\n2. Join our Telegram\n3. Set up your knowledge base\n4. AI goes live instantly",
        "AI customer service works 24/7. Multi-language, self-growing KB, multi-platform. Pro plan starts at $29/mo.",
        "Auto content system generates: blog posts, social posts, marketing copy, newsletters, drama scripts. Chinese + English.",
        "The knowledge base is the core. Good answers auto-save, bad ones get淘汰. 👍/👎 feedback system.",
        "Brand app built with Flutter. iOS + Android + Web. Content from JSON, no backend needed.",
        "Contact us:\n📧 lewislunora@gmail.com\n✈️ Telegram: https://t.me/+QgAyWlVyIxFjNmRl\n🤖 Bot: @ailunora_bot",
        "Live demo 👉 Try typing questions above to experience AI customer service.",
        "Pro $29/mo · Enterprise $199/mo. 14-day free trial, no credit card.",
        "Powered by Groq Llama 3 LLM. Smart conversations, content generation, sentiment analysis.",
    ],
}


def get_kb_reply(text: str, lang: str = "zh-TW") -> str | None:
    lower = text.lower()
    msgs = KB_MSG.get(lang, KB_MSG["zh-TW"])
    for i, keywords in enumerate(KB_KW):
        for kw in keywords:
            if kw in lower:
                return msgs[i] if i < len(msgs) else None
    if lang == "en" and any(w in lower for w in ["how", "what", "can you"]):
        return msgs[6] if len(msgs) > 6 else None
    return None
