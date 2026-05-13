import os, json, re
from datetime import datetime

OUTPUT_JSON = "brand_app_assets/content.json"
SOURCES = {
    "generated_content": "article",
    "guide_content": "guide",
    "ai_drama_scripts": "drama",
}

def parse_md(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {"body": text, "metadata": {}}
    yaml_text = match.group(1)
    body = match.group(2).strip()
    metadata = {}
    for line in yaml_text.strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            metadata[k.strip()] = v.strip()
    return {"body": body, "metadata": metadata}


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    all_content = []
    for folder, ctype in SOURCES.items():
        folder_path = os.path.join(base, folder)
        if not os.path.isdir(folder_path):
            continue
        for fname in sorted(os.listdir(folder_path)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(folder_path, fname)
            parsed = parse_md(fpath)
            meta = parsed["metadata"]
            all_content.append({
                "id": fname.replace(".md", ""),
                "type": ctype,
                "title": meta.get("title", fname),
                "platform": meta.get("platform", ""),
                "language": meta.get("language", "zh-tw"),
                "genre": meta.get("genre", ""),
                "style": meta.get("style", ""),
                "keywords": meta.get("keywords", ""),
                "body": parsed["body"][:5000],
            })

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_content, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(all_content)} 篇內容轉換完成 -> {OUTPUT_JSON}")
    types = {}
    for c in all_content:
        types[c["type"]] = types.get(c["type"], 0) + 1
    for t, n in types.items():
        print(f"   {t}: {n} 篇")


if __name__ == "__main__":
    main()
