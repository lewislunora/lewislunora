import os, re, json
from pathlib import Path

GUIDES_DIR = Path(__file__).parent.parent / "docs" / "guides"
OUTPUT_DIR = GUIDES_DIR

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - AI 品牌知識庫</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  background: #0a0a0f; color: #e0e0e0; line-height: 1.8;
}}
.container {{ max-width: 760px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
.back {{
  display: inline-block; margin-bottom: 2rem; font-size: 0.85rem;
  color: rgba(255,255,255,0.4); text-decoration: none;
}}
.back:hover {{ color: #7b68ee; }}
h1 {{ font-size: 2rem; font-weight: 800; margin-bottom: 0.5rem;
  background: linear-gradient(135deg,#7b68ee,#00d4ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
h2 {{ font-size: 1.4rem; font-weight: 700; margin: 2rem 0 0.8rem; padding-bottom: 0.3rem; border-bottom: 1px solid rgba(255,255,255,0.08); }}
h3 {{ font-size: 1.1rem; font-weight: 600; margin: 1.5rem 0 0.5rem; }}
p {{ margin-bottom: 1rem; color: rgba(255,255,255,0.75); }}
ul, ol {{ margin: 0.5rem 0 1rem 1.5rem; color: rgba(255,255,255,0.75); }}
li {{ margin-bottom: 0.3rem; }}
strong {{ color: #fff; }}
blockquote {{
  border-left: 3px solid rgba(123,104,238,0.4); padding: 0.8rem 1.2rem;
  margin: 1rem 0; background: rgba(123,104,238,0.05); border-radius: 0 8px 8px 0;
  color: rgba(255,255,255,0.6);
}}
.footer {{ text-align: center; padding: 2rem; font-size: 0.75rem; color: rgba(255,255,255,0.2); }}
.cta-box {{
  text-align: center; padding: 2rem; margin: 2rem 0;
  background: linear-gradient(135deg, rgba(123,104,238,0.1), rgba(0,212,255,0.05));
  border: 1px solid rgba(123,104,238,0.2); border-radius: 16px;
}}
.cta-box p {{ margin-bottom: 1rem; }}
.btn {{
  display: inline-block; padding: 0.7rem 2rem; border-radius: 10px;
  font-size: 0.95rem; font-weight: 600; text-decoration: none;
  background: linear-gradient(135deg, #7b68ee, #00d4ff); color: #fff;
  transition: all 0.2s;
}}
.btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px rgba(123,104,238,0.3); }}
code {{
  background: rgba(255,255,255,0.05); padding: 0.15rem 0.4rem;
  border-radius: 4px; font-size: 0.85rem;
}}
</style>
</head>
<body>
<div class="container">
  <a class="back" href=".">← 返回知識庫</a>
  {content}
  <div class="cta-box">
    <p>📥 想獲得完整指南套裝 + AI 提示詞模板？</p>
    <a class="btn" href="../ai-brand/">免費下載</a>
  </div>
</div>
<div class="footer">© 翔川 Neo｜曜科技</div>
</body>
</html>"""

def md_to_html(md_text):
    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("# "):
            if in_list: html_lines.append(f"</{list_type}>"); in_list = False
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            if in_list: html_lines.append(f"</{list_type}>"); in_list = False
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            if in_list: html_lines.append(f"</{list_type}>"); in_list = False
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("- "):
            if not in_list or list_type != "ul":
                if in_list: html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>"); in_list = True; list_type = "ul"
            html_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped.startswith("1. ") or stripped.startswith("2. ") or stripped.startswith("3. ") or stripped.startswith("4. ") or stripped.startswith("5. "):
            if not in_list or list_type != "ol":
                if in_list: html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>"); in_list = True; list_type = "ol"
            html_lines.append(f"<li>{stripped[3:]}</li>")
        elif stripped.startswith("> "):
            html_lines.append(f"<blockquote>{stripped[2:]}</blockquote>")
        elif stripped == "":
            if in_list: html_lines.append(f"</{list_type}>"); in_list = False
            html_lines.append("")
        else:
            if in_list: html_lines.append(f"</{list_type}>"); in_list = False
            html_lines.append(f"<p>{stripped}</p>")

    if in_list:
        html_lines.append(f"</{list_type}>")

    return "\n".join(html_lines)

def main():
    for md_file in sorted(GUIDES_DIR.glob("*.md")):
        slug = md_file.stem
        html_file = OUTPUT_DIR / f"{slug}.html"
        if html_file.exists():
            print(f"  SKIP {slug}.html (already exists)")
            continue

        md_content = md_file.read_text(encoding="utf-8")
        html_body = md_to_html(md_content)

        title = slug.replace("-", " ").title()
        for line in md_content.split("\n"):
            if line.startswith("# "):
                title = line[2:]
                break

        html = TEMPLATE.replace("{title}", title).replace("{content}", html_body)
        html_file.write_text(html, encoding="utf-8")
        print(f"  -> {slug}.html ({len(html)} bytes)")

    print("[DONE]")

if __name__ == "__main__":
    main()
