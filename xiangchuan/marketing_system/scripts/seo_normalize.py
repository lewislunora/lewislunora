#!/usr/bin/env python3
"""SEO 正規化：統一 canonical 到主站、修復 robots / sitemap（冪等）。

設計原則（重要）：
- 主站 = https://lewislunora.onrender.com （有後端、動態 sitemap、analytics 都在這）
- 關鍵 discovering：DOCS_DIR = lewislunora/docs，Render 主站與 GitHub Pages
  **共用同一份 repo/docs**（兩站 live HTML 完全相同）。因此不能加 noindex，
  否則連主站一起被屏蔽。做法是 canonical 一律指向主站 → 兩站自動正規化。
- repo/xiangchuan/docs 是較舊的副本（不部署），一併更新以保持一致。
- 只改 <head> 內的 canonical，其餘 HTML 一個字都不動
- 預設 dry-run；加 --apply 才寫入

用法：
  python3 marketing_system/scripts/seo_normalize.py            # 預覽
  python3 marketing_system/scripts/seo_normalize.py --apply    # 寫入
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

CANONICAL_RE = re.compile(r'<link\s+rel=["\']canonical["\'][^>]*>', re.I)
HEAD_RE = re.compile(r"</head>", re.I)
HREF_RE = re.compile(r'href=["\']([^"\']*)["\']', re.I)

MAIN_ORIGIN = "https://lewislunora.onrender.com"
SKIP_DIRS = {"admin"}  # 後台不算 SEO 頁面

REPO_ROOT = Path(__file__).resolve().parents[3]
TREES = [REPO_ROOT / "docs", REPO_ROOT / "xiangchuan" / "docs"]


def main_path_for(rel: str) -> str:
    """把檔案相對路徑轉成主站 URL。index.html → 目錄根（保留尾部斜線，與 sitemap 一致）。"""
    rel = rel.replace(os.sep, "/")
    parts = rel.split("/")
    is_dir_index = parts[-1] in ("index.html", "index.htm")
    if is_dir_index:
        parts = parts[:-1]
    path = "/".join(p for p in parts if p)
    if not path:
        return f"{MAIN_ORIGIN}/"
    return f"{MAIN_ORIGIN}/{path}/" if is_dir_index else f"{MAIN_ORIGIN}/{path}"


def normalize(html: str, rel: str, is_gh_pages: bool) -> tuple[str, list[str]]:
    changes: list[str] = []
    target = main_path_for(rel)
    canonical_tag = f'<link rel="canonical" href="{target}">'

    def repl(m: re.Match) -> str:
        old = m.group(0)
        h = HREF_RE.search(old)
        # 已是主站絕對 URL 就跳過（避免抖動）
        if h and h.group(1) == target:
            return old
        changes.append(f"canonical: {h.group(1) if h else old} → {target}")
        return canonical_tag

    if CANONICAL_RE.search(html):
        html = CANONICAL_RE.sub(repl, html)
    else:
        if HEAD_RE.search(html):
            html = HEAD_RE.sub(lambda m: f"    {canonical_tag}\n{m.group(0)}", html, count=1)
            changes.append(f"新增 canonical: {target}")

    return html, changes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="實際寫入（預設只預覽）")
    args = ap.parse_args()

    total = 0
    changed = 0
    for tree in TREES:
        if not tree.is_dir():
            continue
        print(f"\n=== {tree.relative_to(REPO_ROOT)} ===")
        for page in sorted(tree.rglob("*.html")):
            if any(part in SKIP_DIRS for part in page.relative_to(tree).parts):
                continue
            total += 1
            rel = page.relative_to(tree).as_posix()
            original = page.read_text(encoding="utf-8", errors="replace")
            new, changes = normalize(original, rel, False)
            if changes:
                changed += 1
                print(f"  {rel}")
                for c in changes:
                    print(f"      {c}")
                if args.apply:
                    page.write_text(new, encoding="utf-8")

    # robots.txt 兩站一致（都指向主站 sitemap）
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "\n"
        f"Sitemap: {MAIN_ORIGIN}/sitemap.xml\n"
    )
    for tree in TREES:
        rp = tree / "robots.txt"
        if not rp.exists() or rp.read_text(encoding="utf-8", errors="replace") != robots:
            print(f"  robots.txt → 更新 ({tree.relative_to(REPO_ROOT)})")
            if args.apply:
                rp.write_text(robots, encoding="utf-8")

    print(f"\n總計: {total} 頁，{changed} 頁需要修改")
    if not args.apply:
        print("這是預覽。加 --apply 才會寫入。")


if __name__ == "__main__":
    main()
