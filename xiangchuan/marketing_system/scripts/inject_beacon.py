#!/usr/bin/env python3
"""把 analytics-beacon.js 注入 docs/ 與 xiangchuan/docs/ 的頁面（冪等）。

交接鐵則：兩個 docs 目錄結構不同、不是同一份，**不可整份互相覆蓋**。
因此本腳本只在各自的 HTML 內原地插入一行 script，不做檔案複製。

- 已注入過的頁面會跳過。
- admin/ 不注入，避免後台瀏覽污染流量數據。
- product/ 與 stock-trading/ 已自帶追蹤，跳過以免重複計算。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TREES = [REPO_ROOT / "docs", REPO_ROOT / "xiangchuan" / "docs"]
SNIPPET = '<script src="analytics-beacon.js" defer></script>'
SKIP_DIRS = {"admin", "assets", "canvaskit", "product", "stock-trading"}
MARKER = "analytics-beacon.js"


def inject(html: str) -> tuple[str, bool]:
    if MARKER in html:
        return html, False
    lower = html.lower()
    idx = lower.rfind("</body>")
    if idx != -1:
        return html[:idx] + SNIPPET + "\n" + html[idx:], True
    idx = lower.rfind("</html>")
    if idx != -1:
        return html[:idx] + SNIPPET + "\n" + html[idx:], True
    return html + "\n" + SNIPPET + "\n", True


def main() -> int:
    grand_total = 0
    for tree in TREES:
        if not tree.exists():
            print(f"跳過（目錄不存在）：{tree}")
            continue
        changed = []
        for path in sorted(tree.rglob("*.html")):
            rel = path.relative_to(tree)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            html = path.read_text(encoding="utf-8", errors="replace")
            new_html, did = inject(html)
            if not did:
                continue
            path.write_text(new_html, encoding="utf-8")
            changed.append(rel)
        grand_total += len(changed)
        print(f"{tree.relative_to(REPO_ROOT)}：注入 {len(changed)} 頁")
        for rel in changed:
            print(f"  {rel.as_posix()}")
    print(f"合計注入 {grand_total} 頁（未複製任何檔案）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
