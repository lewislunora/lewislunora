import os, time, json, requests
from datetime import datetime

GROQ_API_KEY = os.environ['GROQ_API_KEY']
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
OUTPUT_DIR = "guide_content"

ARTICLES = [
    {
        "title": "2026 AI 工具全攻略：創業者必備的 10 個免費 AI 工具",
        "keywords": "AI工具, 創業, 免費, 2026",
        "sections": ["AI 工具是什麼？為什麼創業者必用", "10 大免費 AI 工具推薦", "工具比較表", "如何選擇適合你的 AI 工具", "常見問題 FAQ"],
    },
    {
        "title": "AI 自動化行銷完整教學：從零開始建立你的自動化系統",
        "keywords": "自動化行銷, AI, 教學, 漏斗",
        "sections": ["什麼是 AI 自動化行銷", "自動化行銷的三大核心", "Step-by-step 建置流程", "推薦工具組合", "成效追蹤與優化", "常見問題"],
    },
    {
        "title": "2026 個人品牌經營趨勢：AI 時代的個人IP打造攻略",
        "keywords": "個人品牌, AI, IP, 經營, 2026",
        "sections": ["為什麼個人品牌比以前更重要", "AI 如何改變個人品牌經營", "7 天建置個人品牌系統", "內容策略與多平台分發", "變現模式分析", "常見問題"],
    },
    {
        "title": "Telegram Bot 從零到一：用 AI 打造你的 24 小時客服機器人",
        "keywords": "Telegram Bot, AI客服, 機器人, 教學",
        "sections": ["Telegram Bot 可以做什麼", "事前準備", "Bot 基本架構", "串接 AI（LLM）讓 Bot 變聰明", "部署與上線", "進階功能與優化", "常見問題"],
    },
    {
        "title": "2026 最強 AI 影片生成工具評比：MyEdit vs Runway vs 即夢 AI",
        "keywords": "AI影片, 生成工具, 比較, 2026",
        "sections": ["AI 影片生成技術現況", "三大工具詳細介紹", "功能比較表", "價格方案比較", "適用場景推薦", "常見問題 FAQ"],
    },
    {
        "title": "AI 創業入門：沒有技術背景也能啟動的 5 個 AI 生意點子",
        "keywords": "AI創業, 入門, 生意點子, 無技術",
        "sections": ["AI 創業的迷思與真相", "5 個低成本的 AI 生意點子", "每個點子的啟動步驟", "所需工具與預算", "成功案例參考", "常見問題"],
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
        "temperature": 0.8,
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"[ERROR] {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"[ERROR] {str(e)}"

def generate_article(article, index, total):
    title = article["title"]
    sections = article["sections"]
    lang = "zh-tw" if "中文" not in title else "zh-tw"

    system_prompt = """你是一個專業的科技部落格作者。你擅長寫攻略型、比較型、教學型的長篇文章。
風格：資訊豐富、結構清晰、語氣專業但不枯燥。
每篇文章都需要：吸引人的開頭、清楚的段落標題、具體的步驟或數據、結論與CTA。

輸出格式請用 Markdown。"""

    sections_text = "\n".join([f"- {s}" for s in sections])
    user_prompt = f"""請寫一篇關於「{title}」的完整部落格文章（繁體中文）。

文章結構應包含：
{sections_text}

要求：
- 開頭要吸引人，點出讀者的痛點
- 每個段落要有實際的資訊或建議，不能空泛
- 如果有工具推薦，請包含具體的功能說明和適合族群
- 結尾要有總結和 call to action
- 全文約 1500-2500 字
- 用繁體中文
- 直接輸出文章內容，不要額外說明"""

    return call_groq(system_prompt, user_prompt)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = len(ARTICLES)
    print(f"[START] 開始產生 {total} 篇攻略文")
    print("=" * 60)
    errors = []
    start = time.time()

    for i, article in enumerate(ARTICLES, 1):
        print(f"[{i}/{total}] {article['title'][:40]}...")
        content = generate_article(article, i, total)

        if content.startswith("[ERROR]"):
            errors.append(f"[{i}] {article['title']}: {content}")
            print(f"  {content}")
        else:
            slug = article['title'].replace(' ', '_').replace('', '_')[:30]
            filepath = os.path.join(OUTPUT_DIR, f"{i:02d}_{slug}.md")
            header = f"""---
title: {article['title']}
keywords: {article['keywords']}
generated_at: {datetime.now().isoformat()}
---

"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header + content + "\n")
            print(f"  -> {os.path.basename(filepath)} ({len(content)}字)")

        time.sleep(30)

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"[DONE] {int(elapsed//60)}m{int(elapsed%60)}s，共 {total} 篇")
    if errors:
        print(f"[WARN] {len(errors)} 錯誤:")
        for e in errors:
            print(f"  {e}")

if __name__ == "__main__":
    main()
