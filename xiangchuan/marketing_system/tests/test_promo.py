"""免費推廣工具（promo）測試：分享素材包、週報、RSS。"""


def _seed():
    from marketing_system.database import execute
    execute("INSERT INTO seo_articles (slug,title,summary,content_html) VALUES (?,?,?,?)",
            ["promo-test", "測試文章標題", "這是摘要，用來驗證分享文案產生。",
             "<p>內文</p>"])
    execute("INSERT INTO feed_posts (content,post_type) VALUES (?,?)",
            ["測試短文內容，驗證 share kit。", "short"])
    execute("INSERT INTO novels (title,summary,status,chapter_count) VALUES (?,?,?,?)",
            ["測試連載", "連載簡介", "serializing", 7])


def test_share_kit_covers_all_platforms_with_utm():
    _seed()
    from marketing_system.services.promo import share_kit
    kit = share_kit(limit=3)
    assert kit["items"], "應有素材"
    for item in kit["items"]:
        labels = {p["platform"] for p in item["posts"]}
        assert {"threads", "line", "facebook_group", "x", "reddit", "hn"} <= labels
        for p in item["posts"]:
            assert "utm_source=" in p["text"], f"{p['platform']} 貼文需帶 UTM 追蹤"
            assert p["label"]


def test_share_kit_respects_character_limits():
    _seed()
    from marketing_system.services.promo import share_kit
    item = share_kit(limit=1)["items"][0]
    for p in item["posts"]:
        assert p["within_limit"] is True
        assert p["chars"] <= 500


def test_share_kit_empty_db_is_safe():
    from marketing_system.services.promo import share_kit
    kit = share_kit(limit=3)
    assert isinstance(kit["items"], list)


def test_weekly_digest_reports_counts_and_link():
    _seed()
    from marketing_system.services.promo import weekly_digest
    d = weekly_digest()
    assert "本週更新" in d["text"]
    assert "免費試用" in d["text"]
    assert "小說累計" in d["stats"]


def test_rss_xml_is_valid_envelope():
    _seed()
    from marketing_system.services.promo import rss_xml
    xml = rss_xml(limit=5)
    assert xml.startswith("<?xml")
    assert "<rss version=\"2.0\">" in xml and "</channel></rss>" in xml
    assert xml.count("<item>") >= 2
    assert "utm_source=rss" in xml


def test_promo_endpoints_available():
    from fastapi.testclient import TestClient
    from marketing_system.api.server import app
    c = TestClient(app)
    r = c.get("/api/promo/share-kit?limit=2")
    assert r.status_code == 200 and "items" in r.json()
    d = c.get("/api/promo/weekly-digest")
    assert d.status_code == 200 and d.json()["text"]
    f = c.get("/feed.xml")
    assert f.status_code == 200 and "<rss" in f.text

# ── 免費社群管道（Telegram／Bluesky）────────────────────────────────────
def _seed_one_article():
    from marketing_system.database import execute
    execute("INSERT INTO seo_articles (slug,title,summary,content_html) VALUES (?,?,?,?)",
            ["chan-test", "推播測試文章", "摘要：確認推播管線。", "<p>x</p>"])


def _fake_channels(monkeypatch, calls):
    from marketing_system.services import channels
    monkeypatch.setattr(channels, "channels_configured",
                        lambda: {"telegram": True, "bluesky": False})
    monkeypatch.setattr(channels, "PUSHERS",
                        {"telegram": lambda t: (calls.append(t), {"ok": True, "detail": "mock"})[1]})
    return channels


def test_auto_push_without_credentials_is_noop():
    from marketing_system.services import channels
    _seed_one_article()
    r = channels.auto_push()
    assert r["ok"] is False and "憑證" in r["detail"]


def test_auto_push_sends_once_per_item(monkeypatch):
    from marketing_system.database import execute
    _seed_one_article()
    # 隔離其它測試可能留下的候選內容，只留一筆
    execute("DELETE FROM feed_posts")
    execute("DELETE FROM novels")
    calls = []
    channels = _fake_channels(monkeypatch, calls)
    r1 = channels.auto_push()
    assert r1["ok"] is True and len(calls) == 1
    assert "utm_source=auto_push" in calls[0]
    # 同一筆不重複推
    r2 = channels.auto_push()
    assert len(calls) == 1
    assert r2["detail"] == "沒有待推的新內容"


def test_auto_push_respects_daily_cap(monkeypatch):
    from marketing_system.database import execute
    _seed_one_article()
    calls = []
    channels = _fake_channels(monkeypatch, calls)
    for i in range(5):
        execute("INSERT INTO seo_articles (slug,title,summary,content_html) VALUES (?,?,?,?)",
                [f"cap-{i}", f"第{i}篇", "摘要", "<p>x</p>"])
    for _ in range(5):
        channels.auto_push()
    assert len(calls) == channels.DAILY_CAP["telegram"]
    skipped = channels.auto_push()
    assert all(r.get("skipped") for r in skipped["channels"].values())


def test_channel_status_shape():
    from marketing_system.services import channels
    s = channels.status()
    assert set(s["configured"]) == {"telegram", "bluesky"}
    assert "today" in s and "recent" in s


def test_channels_endpoint_available():
    from fastapi.testclient import TestClient
    from marketing_system.api.server import app
    c = TestClient(app)
    r = c.get("/api/promo/channels")
    assert r.status_code == 200 and "configured" in r.json()


def test_sitemap_includes_key_and_new_pages():
    """sitemap 必須含 govdata／product 等重點頁，並自動帶入 guides 底下的新頁。"""
    from fastapi.testclient import TestClient
    from marketing_system.api.server import app
    xml = TestClient(app).get("/sitemap.xml").text
    for must in ("/govdata", "/product/", "/guides/google-indexing.html",
                 "/guides/ai-content-system.html"):
        assert must in xml, f"sitemap 缺少 {must}"
    assert "admin/" not in xml, "後台頁不應被索引"
