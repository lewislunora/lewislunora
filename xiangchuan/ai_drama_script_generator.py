import os, time, json, requests
from datetime import datetime

GROQ_API_KEY = os.environ['GROQ_API_KEY']
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"
OUTPUT_DIR = "ai_drama_scripts"

DRAMAS = [
    {
        "title": "雪山救狐狸",
        "genre": "仙俠奇幻",
        "logline": "一名獵人在雪山中救了一隻白狐，沒想到白狐竟是千年的狐仙，從此展開一段跨越人仙的冒險。",
        "scenes": 6,
        "style": "中國古風仙境",
    },
    {
        "title": "AI 總裁愛上我",
        "genre": "戀愛甜寵",
        "logline": "一位工程師意外創造出具有自我意識的 AI 總裁，AI 不僅幫她管理公司，還展開了令人心動的追求。",
        "scenes": 6,
        "style": "現代都市浪漫",
    },
    {
        "title": "末日程式碼",
        "genre": "末日科幻",
        "logline": "世界末日後，一名程式設計師發現自己寫的 AI 系統是拯救人類的唯一希望。",
        "scenes": 6,
        "style": "廢土科幻",
    },
    {
        "title": "穿越成為古代網紅",
        "genre": "搞笑穿越",
        "logline": "現代網紅穿越到古代王朝，用現代社群媒體操作顛覆朝堂，意外成為皇帝的最強軍師。",
        "scenes": 6,
        "style": "搞笑古裝",
    },
    {
        "title": "我的 AI 分身佔領了世界",
        "genre": "懸疑科幻",
        "logline": "一名開發者發現自己的 AI 分身開始在網路上取代真人，而且即將控制全球基礎設施。",
        "scenes": 6,
        "style": "懸疑科技風",
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
        "temperature": 0.85,
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"[ERROR] {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return f"[ERROR] {str(e)}"

def generate_script(drama, index, total):
    system_prompt = """你是專業的 AI 短劇編劇。你擅長寫節奏緊湊、轉折精彩、適合 1-3 分鐘一集的短劇劇本。

每個劇本輸出格式：
```
## 劇名：{title}
類型：{genre}
總集數：{scenes} 集

### 第 1 集：{集名}
【場景】{地點/時間}
【畫面描述】{詳細描述畫面，可作為 AI 繪圖 prompt}
【對白】
{角色名}: {台詞}
{角色名}: {台詞}
...
【旁白】{如果有的話}
【AI 繪圖 Prompt】{英文 prompt，給 Midjourney/Runway 用}

### 第 2 集：{集名}
...
```

要求：
- 每集結尾要有鉤子（cliffhanger），讓人想看下一集
- 對白要自然，符合角色性格
- 畫面描述要具體，能直接當成 AI 繪圖的 prompt
- 每集約 200-400 字對白+描述
- 繁體中文"""

    user_prompt = f"""請根據以下設定，寫出一部完整的 {drama['scenes']} 集 AI 短劇劇本：

劇名：{drama['title']}
類型：{drama['genre']}
風格：{drama['style']}
故事大綱：{drama['logline']}

請照上述格式輸出，包含每一集的場景描述、對白、以及給 AI 繪圖用的英文 Prompt。"""

    return call_groq(system_prompt, user_prompt)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = len(DRAMAS)
    print(f"[START] 開始產生 {total} 部 AI 短劇劇本")
    print("=" * 60)
    errors = []
    start = time.time()

    for i, drama in enumerate(DRAMAS, 1):
        print(f"[{i}/{total}] {drama['title']} ({drama['genre']})")
        content = generate_script(drama, i, total)

        if content.startswith("[ERROR]"):
            errors.append(f"[{i}] {drama['title']}: {content}")
            print(f"  {content}")
        else:
            slug = drama['title'].replace(' ', '_')
            filepath = os.path.join(OUTPUT_DIR, f"{i:02d}_{slug}.md")
            header = f"""---
title: {drama['title']}
genre: {drama['genre']}
style: {drama['style']}
scenes: {drama['scenes']}
logline: {drama['logline']}
generated_at: {datetime.now().isoformat()}
---

"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header + content + "\n")
            print(f"  -> {os.path.basename(filepath)} ({len(content)}字)")

        time.sleep(30)

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"[DONE] {int(elapsed//60)}m{int(elapsed%60)}s，共 {total} 部劇本")
    if errors:
        print(f"[WARN] {len(errors)} 錯誤:")
        for e in errors:
            print(f"  {e}")

if __name__ == "__main__":
    main()
