import os, time, requests
from pathlib import Path

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "guides"

ARTICLES = [
    {
        "slug": "solopreneur-ai-system",
        "title": "超級個體 AI 系統建立指南：一人公司必備的自動化工具",
        "desc": "如何用 AI 打造你的超級個體事業系統，從內容到客戶完全自動化",
        "sections": ["什麼是超級個體？為什麼現在是最好的時代", "一人公司必備的 AI 工具組合", "內容自動化系統建立", "客戶獲取與管理自動化", "從工具到系統的整合思維", "常見問題 FAQ"],
    },
    {
        "slug": "ai-consulting-framework",
        "title": "AI 顧問服務框架：如何用 AI 放大你的專業價值",
        "desc": "顧問如何用 AI 提升服務品質、擴大服務規模、增加收入",
        "sections": ["傳統顧問的困境與 AI 的機會", "AI 輔助顧問工作流程", "知識管理與案例庫建立", "用 AI 擴大服務規模", "顧問的 AI 服務包裝與定價", "常見問題 FAQ"],
    },
]

system_prompt = """你是一個專業的個人品牌教練、超級個體顧問。你擅長寫實用指南。
風格：專業、實戰、步驟清晰。用繁體中文。
每篇都要包含：痛點引入、核心概念、具體步驟、實戰案例、 actionable tips。"""

def call_groq(title, desc, sections):
    sections_text = "\n".join([f"- {s}" for s in sections])
    user_prompt = f"""請寫一篇關於「{title}」的完整指南文章（繁體中文）。

文章描述：{desc}

結構需包含：
{sections_text}

要求：
- 開頭點出痛點
- 具體 actionable 步驟
- AI 工具的具體應用
- 全文 2000-3000 字
- 用繁體中文
- 直接輸出 Markdown"""

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], "max_tokens": 4096, "temperature": 0.7}
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=180)
    return resp.json()["choices"][0]["message"]["content"]

def main():
    for i, art in enumerate(ARTICLES, 1):
        print(f"[{i}/{len(ARTICLES)}] {art['title'][:40]}...")
        try:
            content = call_groq(art['title'], art['desc'], art['sections'])
            filepath = OUTPUT_DIR / f"{art['slug']}.md"
            filepath.write_text(content + "\n", encoding="utf-8")
            print(f"  -> {art['slug']}.md ({len(content)} 字)")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(25)
    print("[DONE]")

if __name__ == "__main__":
    main()
