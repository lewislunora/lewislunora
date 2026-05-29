import os, time, requests, json
from datetime import datetime

GROQ_API_KEY = os.environ['GROQ_API_KEY']
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "guides")

GUIDES = [
    {
        "slug": "ai-personal-brand-positioning",
        "title": "AI 時代個人品牌定位策略：找到你的獨特價值",
        "desc": "學習如何在 AI 時代找到個人品牌定位，建立系統化的內容策略",
        "sections": [
            "為什麼 AI 時代個人品牌更重要",
            "找到你的獨特價值主張",
            "用 AI 分析市場與受眾",
            "建立內容資產的系統化思維",
            "個人品牌定位工作坊",
            "常見問題 FAQ",
        ],
    },
    {
        "slug": "ai-content-system",
        "title": "AI 內容系統建立指南：高效產出高品質內容",
        "desc": "用 AI 建立內容生產線，持續產出吸引目標客戶的內容",
        "sections": [
            "內容系統的核心概念",
            "AI 內容創作工作流",
            "建立可重複使用的內容素材庫",
            "多平台內容策略與分發",
            "內容成效追蹤與優化",
            "常見問題 FAQ",
        ],
    },
    {
        "slug": "ai-customer-system",
        "title": "AI 驅動的客戶獲取系統：自動化精準行銷",
        "desc": "用 AI 建立自動化客戶獲取與管理系統，提升轉換率",
        "sections": [
            "為什麼需要 AI 客戶系統",
            "AI 精準受眾分析與定位",
            "自動化行銷漏斗建立",
            "AI 客服與互動系統",
            "客戶關係管理自動化",
            "常見問題 FAQ",
        ],
    },
    {
        "slug": "knowledge-to-product",
        "title": "將知識技能轉化為數位產品：AI 加速產品化流程",
        "desc": "學會用 AI 將你的專業知識轉化為可銷售的數位產品",
        "sections": [
            "知識產品化的核心理念",
            "用 AI 盤點與整理專業知識",
            "數位產品類型與選擇",
            "AI 輔助產品開發流程",
            "產品定價與上市策略",
            "常見問題 FAQ",
        ],
    },
    {
        "slug": "ai-automation-funnel",
        "title": "AI 自動化銷售漏斗：從流量到變現的完整流程",
        "desc": "建立完整的 AI 自動化銷售漏斗，讓系統為你 24 小時工作",
        "sections": [
            "銷售漏斗的基本原理",
            "頂層流量獲取策略",
            "AI 內容行銷自動化",
            "中層培育與信任建立",
            "底層轉換與客戶留存",
            "常見問題 FAQ",
        ],
    },
    {
        "slug": "no-face-personal-brand",
        "title": "不露臉個人品牌建立完全指南：用 AI 打造影響力",
        "desc": "完全不需要露臉或錄影片，用 AI 工具建立你的個人品牌",
        "sections": [
            "不露臉品牌的優勢與策略",
            "AI 生成頭像與視覺識別",
            "文字為核心的內容策略",
            "AI 語音與虛擬形象應用",
            "信任建立與社群經營",
            "常見問題 FAQ",
        ],
    },
]

def call_groq(system_prompt, user_prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=180)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"[ERROR] {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"[ERROR] {str(e)}"

def generate_guide(guide):
    title = guide["title"]
    slug = guide["slug"]
    desc = guide["desc"]
    sections = guide["sections"]

    system_prompt = """你是一個專業的個人品牌教練與 AI 行銷顧問。你擅長寫深度指南型文章。
風格：專業、實用、步驟清晰。用繁體中文。
每篇文章都要包含：痛點引入、核心概念、具體步驟、實戰案例、 actionable tips。"""

    sections_text = "\n".join([f"- {s}" for s in sections])
    user_prompt = f"""請寫一篇關於「{title}」的完整指南文章（繁體中文）。

文章描述：{desc}

文章結構需包含：
{sections_text}

要求：
- 開頭要點出讀者的痛點和常見問題
- 每個段落要有具體的 actionable 建議
- 包含實際的操作步驟或流程圖說明
- 提到 AI 工具的具體應用方式
- 全文約 2000-3000 字
- 用繁體中文
- 結尾要有總結與下一步行動建議
- 直接輸出 Markdown 格式內容"""

    return call_groq(system_prompt, user_prompt)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = len(GUIDES)
    print(f"[START] 產生 {total} 篇 AI 品牌指南")
    print("=" * 60)
    errors = []

    for i, guide in enumerate(GUIDES, 1):
        print(f"[{i}/{total}] {guide['title'][:40]}...")
        content = generate_guide(guide)

        if content.startswith("[ERROR]"):
            errors.append(f"[{i}] {guide['title']}: {content}")
            print(f"  {content}")
        else:
            filepath = os.path.join(OUTPUT_DIR, f"{guide['slug']}.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            print(f"  -> {guide['slug']}.md ({len(content)} 字)")
        time.sleep(25)

    print("\n" + "=" * 60)
    print(f"[DONE] {total} 篇")
    if errors:
        print(f"[WARN] {len(errors)} 錯誤:")
        for e in errors:
            print(f"  {e}")

if __name__ == "__main__":
    main()
