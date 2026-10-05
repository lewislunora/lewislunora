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