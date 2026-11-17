"""AI 社交夥伴：機器人帳號、發佈版分類、私訊，以及無金鑰時完全安靜。"""
import marketing_system.services.ai_social as ai_social
from marketing_system.database import execute, fetch_one


def _login(client, email="botfan@test.com", password="password123"):
    token = client.post("/api/auth/register", json={"email": email, "password": password}).json()["token"]
    client.cookies.set("token", token, path="/")
    return token


def _post(pid_type, content):
    """直接寫入一則貼文，模擬機器人或真人已發文。"""
    execute(
        "INSERT INTO feed_posts (user_id, content, post_type, author) VALUES (?, ?, ?, ?)",
        [None, content, pid_type, "測試"],
    )


def test_ensure_bots_is_idempotent():
    bots = ai_social.ensure_bots()
    assert len(bots) == 4
    assert {b["username"] for b in bots} == {"ai_xiaoxiang", "ai_lele", "ai_nini", "ai_kuge"}
    assert all(b["is_bot"] == 1 for b in bots)
    # 再跑一次不應重複建立
    ai_social.ensure_bots()
    assert fetch_one("SELECT COUNT(*) AS c FROM users WHERE is_bot=1")["c"] == 4


def test_bots_endpoint_lists_four_without_secrets(client):
    r = client.get("/api/social/bots")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 4
    assert {i["persona"] for i in items} == {"auto", "life", "idea", "tech"}
    for i in items:
        assert set(i) == {"id", "username", "name", "avatar", "bio", "persona"}


def test_feed_type_filter_and_ai_badge(client):
    ai_social.ensure_bots()
    bot_id = fetch_one("SELECT id FROM users WHERE username='ai_lele'")["id"]
    execute(
        "INSERT INTO feed_posts (user_id, content, post_type, author) VALUES (?, ?, ?, ?)",
        [bot_id, "今天下班去走了河堤。", "life", "阿樂"],
    )
    _post("tech", "新的 AI 工具實測。")

    life = client.get("/api/feed?type=life").json()
    assert life["total"] == 1
    assert life["items"][0]["post_type"] == "life"
    assert life["items"][0]["author"]["is_bot"] is True

    tech = client.get("/api/feed?type=tech").json()
    assert tech["total"] == 1
    assert tech["items"][0]["author"]["is_bot"] is False

    # 未知分類不可注入，退回全部
    assert client.get("/api/feed?type=../etc").json()["total"] == 2
    assert client.get("/api/feed").json()["total"] == 2


def test_post_type_is_validated(client):
    _login(client)
    r = client.post("/api/feed", json={"content": "今天想分享一件小事。", "post_type": "hacker"})
    assert r.status_code == 200
    assert r.json()["post"]["post_type"] == "life"

    r2 = client.post("/api/feed", json={"content": "剛試了一個新工具。", "post_type": "tech"})
    assert r2.json()["post"]["post_type"] == "tech"


def test_tick_silent_without_api_key(monkeypatch):
    monkeypatch.setattr(ai_social, "GROQ_API_KEY", "")
    before = fetch_one("SELECT COUNT(*) AS c FROM feed_posts")["c"]
    result = ai_social.tick()
    assert result.get("skipped")
    assert fetch_one("SELECT COUNT(*) AS c FROM feed_posts")["c"] == before
    assert fetch_one("SELECT COUNT(*) AS c FROM ai_bot_actions")["c"] == 0


def test_chat_with_bot_opens_greeting(client):
    _login(client, "dmfan@test.com")
    r = client.post("/api/social/chat-with-bot", json={"username": "ai_nini"})
    assert r.status_code == 200
    data = r.json()
    assert data["bot"]["name"] == "妮妮"

    msgs = client.get(f"/api/chat/conversations/{data['conversation_id']}/messages").json()["items"]
    assert msgs and msgs[0]["sender_id"] == data["bot"]["id"]

    # 第二次開啟同一對話，不應重複塞開場白
    r2 = client.post("/api/social/chat-with-bot", json={"username": "ai_nini"})
    assert r2.json()["conversation_id"] == data["conversation_id"]
    msgs2 = client.get(f"/api/chat/conversations/{data['conversation_id']}/messages").json()["items"]
    assert len(msgs2) == len(msgs)


def test_chat_with_bot_requires_login(client):
    assert client.post("/api/social/chat-with-bot", json={"username": "ai_lele"}).status_code == 401


def test_send_to_bot_stores_message_without_key(client):
    _login(client, "sender@test.com")
    cid = client.post("/api/social/chat-with-bot", json={"username": "ai_kuge"}).json()["conversation_id"]
    r = client.post("/api/chat/send", json={"conversation_id": cid, "body": "酷哥，你覺得哪個工具好用？"})
    assert r.status_code == 200
    assert r.json()["message"]["body"] == "酷哥，你覺得哪個工具好用？"


def _bot_row(username="ai_lele"):
    ai_social.ensure_bots()
    row = fetch_one("SELECT * FROM users WHERE username=?", [username])
    row["persona_style"] = "溫暖"
    return row


def test_create_bot_post_respects_6h_limit(monkeypatch):
    monkeypatch.setattr(ai_social, "GROQ_API_KEY", "stub")
    monkeypatch.setattr(ai_social, "_generate", lambda *a, **k: "今天騎車經過河堤，風很舒服。你最近有讓自己放空嗎？")
    bot = _bot_row()
    first = ai_social.create_bot_post(bot)
    assert first
    assert ai_social.create_bot_post(bot) is None  # 6 小時內不重複發文
    post = fetch_one("SELECT * FROM feed_posts WHERE id=?", [first])
    assert post["user_id"] == bot["id"]
    assert post["post_type"] == "life"


def test_bot_dm_reply_and_dedupe(monkeypatch):
    bot = _bot_row()
    uid = execute("INSERT INTO users (username, password_hash, name) VALUES ('realperson', 'x', '真人')")
    cid = execute("INSERT INTO conversations (user_a, user_b) VALUES (?, ?)", [min(uid, bot["id"]), max(uid, bot["id"])])
    execute(
        "INSERT INTO messages (conversation_id, sender_id, body) VALUES (?, ?, ?)",
        [cid, uid, "今天工作好累"],
    )
    history = [{"sender_id": uid, "body": "今天工作好累"}]

    monkeypatch.setattr(ai_social, "GROQ_API_KEY", "stub")
    monkeypatch.setattr(ai_social, "_generate", lambda *a, **k: "辛苦了，先喝口水吧。累的是工作本身，還是人的部分？")

    mid = ai_social.bot_reply_to_dm(bot, cid, history)
    assert mid
    reply = fetch_one("SELECT * FROM messages WHERE id=?", [mid])
    assert reply["sender_id"] == bot["id"]
    assert fetch_one("SELECT last_message_at FROM conversations WHERE id=?", [cid])

    # 5 秒內同一對話不重複回覆，避免前端輪詢造成連發
    assert ai_social.bot_reply_to_dm(bot, cid, history) is None


def test_tick_stops_at_daily_post_cap(monkeypatch):
    bot = _bot_row()
    for _ in range(8):
        execute(
            "INSERT INTO ai_bot_actions (bot_user_id, action, ref) VALUES (?, 'post', 'x')",
            [bot["id"]],
        )
    monkeypatch.setattr(ai_social, "GROQ_API_KEY", "stub")
    monkeypatch.setattr(ai_social, "_generate", lambda *a, **k: "今天想聊一件小事。你最近好嗎？")
    result = ai_social.tick()
    assert result["posted"] == 0
    assert fetch_one("SELECT COUNT(*) AS c FROM feed_posts")["c"] == 0


def test_prune_actions_drops_old_rows():
    bot = _bot_row()
    execute(
        "INSERT INTO ai_bot_actions (bot_user_id, action, ref, created_at) VALUES (?, 'post', '1', '2020-01-01 00:00:00')",
        [bot["id"]],
    )
    ai_social._prune_actions(days=7)
    assert fetch_one("SELECT COUNT(*) AS c FROM ai_bot_actions WHERE action='post'")["c"] == 0
