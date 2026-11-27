"""AI 精靈：單檔腳本、頁面掛載、版本指紋。"""
from marketing_system.config import DOCS_DIR


def test_status_exposes_current_build(client):
    assert client.get("/api/status").json()["build_fingerprint"] == "intent-learning-2026-11-27"


def test_spirit_script_is_served(client):
    r = client.get("/spirit.js")
    assert r.status_code == 200
    assert "AI 精靈" in r.text
    assert "spiritBubble" in r.text


def test_pages_load_script(client):
    for path in ("/", "/ai-tools.html", "/personal-tools.html", "/login.html"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "spirit.js" in r.text, path


def test_dashboard_injects_script_once(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert r.text.count("spirit.js") == 1


def test_script_has_no_eval_or_external_deps():
    src = (DOCS_DIR / "spirit.js").read_text(encoding="utf-8")
    assert "eval(" not in src
    assert "http://" not in src and "https://cdn" not in src
