"""SEO 標準化：canonical 指向 Render 主站、GitHub Pages 鏡像 noindex、sitemap 完整。"""
from pathlib import Path

from marketing_system.config import DOCS_DIR


def test_docs_sitemap_points_to_render_canonical():
    xml = (DOCS_DIR / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://lewislunora.onrender.com/</loc>" in xml
    assert "<loc>https://lewislunora.onrender.com/social/</loc>" in xml


def test_docs_robots_txt_points_to_render_sitemap():
    txt = (DOCS_DIR / "robots.txt").read_text(encoding="utf-8")
    assert "https://lewislunora.onrender.com/sitemap.xml" in txt
    assert "Disallow: /admin/" in txt
    assert "Disallow: /api/" in txt


def test_content_pages_have_absolute_canonical():
    html = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://lewislunora.onrender.com/"' in html
    html_social = (DOCS_DIR / "social" / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://lewislunora.onrender.com/social/"' in html_social
    html_pricing = (DOCS_DIR / "pricing.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://lewislunora.onrender.com/pricing.html"' in html_pricing
    html_money = (DOCS_DIR / "money.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://lewislunora.onrender.com/money.html"' in html_money


def test_content_pages_do_not_carry_noindex():
    """Render 主站與 GitHub Pages 共用 repo/docs；內容頁一律不加 noindex，
    否則主站也會被 Google 排出來。只有後台頁保留 noindex。"""
    html = (DOCS_DIR / "social" / "index.html").read_text(encoding="utf-8")
    assert 'name="robots"' not in html
    html_home = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    assert 'name="robots"' not in html_home


def test_admin_pages_carry_noindex():
    html = (DOCS_DIR / "admin" / "monetize.html").read_text(encoding="utf-8")
    assert 'name="robots"' in html
    assert "noindex" in html
