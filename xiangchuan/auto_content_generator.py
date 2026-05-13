import os
import json
import time
import requests
from datetime import datetime

GROQ_API_KEY = os.environ['GROQ_API_KEY']
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OUTPUT_DIR = "generated_content"

ROUNDS = 2

TOPICS = [
    "個人品牌故事與定位",
    "AI創業日記與心路歷程",
    "自動化行銷策略與技巧",
    "AI工具推薦與教學",
    "創業者生產力提升",
    "社群媒體經營術",
    "內容行銷趨勢",
    "品牌建立實戰",
    "AI客服與客戶體驗",
    "低成本創業方法",
    "知識變現策略",
    "自媒體經營入門",
    "AI時代的職涯規劃",
    "自動化銷售漏斗",
    "數據驅動行銷",
    "創業者時間管理",
]

PLATFORMS = {
    "blog": "部落格長文（800-1200字）",
    "facebook": "Facebook貼文（150-300字）",
    "threads": "Threads短貼文（100-200字）",
    "linkedin": "LinkedIn專業貼文（200-400字）",
    "email": "電子報行銷信（300-500字）",
}

LANGUAGES = {"zh-tw": "繁體中文", "en": "English"}

def call_groq(system_prompt, user_prompt, model="llama-3.3-70b-versatile"):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.8,
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"[ERROR] {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"[ERROR] {str(e)}"


def generate_content(topic, platform, lang_code, lang_name, index):
    system_prompt = f"""你是一個AI創業者和個人品牌專家的內容創作助理。
你擅長用{lang_name}寫出高品質、有洞察力的內容。
你的風格：真誠、專業、有故事性、給 actionable 建議。
每篇文章都要包含具體的例子或親身經歷感。"""

    platform_desc = PLATFORMS[platform]
    user_prompt = f"""請寫一篇關於「{topic}」的{platform_desc}（{lang_name}）。

要求：
- 語氣自然，像真人分享經驗
- 開頭要吸引人
- 結尾要有 call to action
- 如果適合，加入 hashtag

內容主題參考（可自行發揮）：
- AI 如何改變創業方式
- 自動化工具讓行銷效率提升 10 倍
- 個人品牌為何是創業者的最佳資產
- 從 0 到 1 建立自動化行銷系統
- AI 時代的創業者 mindset

請直接輸出內容，不要加說明。"""

    content = call_groq(system_prompt, user_prompt)
    return content


def save_content(topic, platform, lang_code, content, index):
    topic_slug = topic.replace(" ", "_").replace(" ", "_")
    filename = f"{index:03d}_{lang_code}_{platform}_{topic_slug}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    header = f"""---
title: {topic}
platform: {platform}
language: {lang_code}
generated_at: {datetime.now().isoformat()}
---

"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + content + "\n")
    return filepath


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_per_round = len(TOPICS) * len(PLATFORMS) * len(LANGUAGES)
    total = total_per_round * ROUNDS
    print(f"[START] 開始產生 {total} 篇內容（約 2 小時）")
    print(f"[INFO] 輪次: {ROUNDS}, 每輪: {total_per_round} 篇")
    print(f"[INFO] 主題: {len(TOPICS)} 個, 平台: {len(PLATFORMS)} 個, 語言: {len(LANGUAGES)} 個")
    print("=" * 60)

    index = 0
    start_time = time.time()
    errors = []

    for round_num in range(1, ROUNDS + 1):
        print(f"\n{'='*60}")
        print(f" 第 {round_num}/{ROUNDS} 輪 ")
        print(f"{'='*60}")
        for lang_code, lang_name in LANGUAGES.items():
            print(f"\n--- 語言: {lang_name} ---")
            for topic in TOPICS:
                for platform, platform_desc in PLATFORMS.items():
                    index += 1
                    elapsed = time.time() - start_time
                    eta_remaining = ((total * ROUNDS - index) * 35) / 60
                    print(
                        f"[{index}/{total * ROUNDS}] R{round_num} {lang_code} "
                        f"{platform:10s} {topic[:12]:12s} "
                        f"({int(elapsed//60)}m{int(elapsed%60)}s "
                        f"ETA:{int(eta_remaining)}m)"
                    )

                    content = generate_content(
                        topic, platform, lang_code, lang_name, index
                    )

                    if content.startswith("[ERROR]"):
                        errors.append(
                            f"[{index}] R{round_num} {lang_code}/{platform}/"
                            f"{topic}: {content}"
                        )
                        print(f"  {content}")
                    else:
                        filepath = save_content(
                            topic, platform, lang_code, content, index
                        )
                        print(f"  -> {os.path.basename(filepath)}")

                    time.sleep(25)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"[DONE] 完成！耗時 {int(elapsed//60)} 分 {int(elapsed%60)} 秒")
    print(f"[DONE] 共產生 {index} 篇內容")
    print(f"[DONE] 輸出目錄: {OUTPUT_DIR}/")

    summary_path = os.path.join(OUTPUT_DIR, "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": index,
                "rounds": ROUNDS,
                "topics": len(TOPICS),
                "platforms": len(PLATFORMS),
                "languages": len(LANGUAGES),
                "errors": len(errors),
                "elapsed_minutes": round(elapsed / 60, 1),
                "generated_at": datetime.now().isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[DONE] summary -> {summary_path}")
    print(f"[DONE] 回目錄: find {OUTPUT_DIR}/ -name '*.md' | wc -l")

    if errors:
        print(f"\n[WARN] {len(errors)} 個錯誤:")
        for e in errors[:5]:
            print(f"  {e}")
        if len(errors) > 5:
            print(f"  ... 還有 {len(errors) - 5} 個錯誤")


if __name__ == "__main__":
    main()
