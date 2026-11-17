#!/usr/bin/env python3
"""移除 docs/ 共用作業目錄裡誤加的 <meta name="robots" content="noindex">。

原因：Render 主站與 GitHub Pages 共用 repo/docs。若加 noindex，
連主站一起被 Google 屏蔽。admin/ 可保留（後台本來就不該被索引）。

預設 dry-run；加 --apply 才寫入。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NOINDEX_RE = re.compile(r'\s*<meta\s+name=["\']robots["\'][^>]*noindex[^>]*>', re.I)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = 0
    for tree in (REPO_ROOT / "docs", REPO_ROOT / "xiangchuan" / "docs"):
        if not tree.is_dir():
            continue
        print(f"\n=== {tree.relative_to(REPO_ROOT)} ===")
        for page in sorted(tree.rglob("*.html")):
            rel = page.relative_to(tree).as_posix()
            if rel.startswith("admin/"):
                continue  # 後台保留 noindex
            html = page.read_text(encoding="utf-8", errors="replace")
            new, n = NOINDEX_RE.subn("", html)
            if n:
                total += 1
                print(f"  {rel} ({n})")
                if args.apply:
                    page.write_text(new, encoding="utf-8")
    print(f"\n共 {total} 頁有誤加的 noindex")
    if not args.apply:
        print("這是預覽。加 --apply 才寫入。")


if __name__ == "__main__":
    main()
