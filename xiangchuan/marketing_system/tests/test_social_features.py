"""Social features tests: chat, follow, feed."""
import pytest
from marketing_system.database import execute, fetch_one


def _register(client, email, password="password123"):
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _login_as(client, email, password="password123"):
    token = _register(client, email, password)
    client.cookies.set("token", token, path="/")


def _login_as_second(client, email, password="password123"):
    token = _register(client, email, password)
    client.cookies.set("token", token, path="/")
    return token


class TestChat:
    def test_chat_requires_login(self, client):
        assert client.get("/api/chat/conversations").status_code == 401

    def test_send_list_and_read(self, client):
        _login_as(client, "alice@test.com")
        # alice's own id
        me = client.get("/api/auth/me").json()
        # register bob separately (alice's cookie remains)
        bob_token = client.post("/api/auth/register", json={"email": "bob@test.com", "password": "pw123456"}).json()["token"]
        bob = client.get(f"/api/auth/me?token={bob_token}").json()
        assert me["id"] != bob["id"]

        resp = client.post("/api/chat/open", json={"user_id": bob["id"]})
        assert resp.status_code == 200
        cid = resp.json()["conversation_id"]

        send = client.post("/api/chat/send", json={"conversation_id": cid, "body": "你好！"})
        assert send.status_code == 200
        assert send.json()["message"]["sender_id"] == me["id"]

        convs = client.get("/api/chat/conversations").json()
        assert convs["items"]
        assert convs["items"][0]["id"] == cid

        msgs = client.get(f"/api/chat/conversations/{cid}/messages").json()
        assert msgs["items"]
        assert msgs["items"][0]["body"] == "你好！"

    def test_send_by_user_id_creates_conversation(self, client):
        _login_as(client, "carol@test.com")
        me = client.get("/api/auth/me").json()
        dave = client.post("/api/auth/register", json={"email": "dave@test.com", "password": "pw123456"}).json()
        dave = client.get(f"/api/auth/me?token={dave['token']}").json()
        resp = client.post("/api/chat/send", json={"to_user_id": dave["id"], "body": "哈囉"})
        assert resp.status_code == 200
        assert resp.json()["message"]["conversation_id"]

    def test_unread_count_and_mark_read(self, client):
        _login_as(client, "erin@test.com")
        me = client.get("/api/auth/me").json()
        frank = client.post("/api/auth/register", json={"email": "frank@test.com", "password": "pw123456"}).json()
        frank_id = client.get(f"/api/auth/me?token={frank['token']}").json()["id"]

        cid = client.post("/api/chat/open", json={"user_id": frank_id}).json()["conversation_id"]
        # bob (frank) replies
        execute("INSERT INTO messages (conversation_id, sender_id, body) VALUES (?,?,?)", (cid, frank_id, "在嗎？"))
        assert client.get("/api/chat/unread").json()["unread"] >= 1
        client.get(f"/api/chat/conversations/{cid}/messages")  # marks read
        assert client.get("/api/chat/unread").json()["unread"] == 0

    def test_chat_suggest_fallback_without_groq(self, client):
        _login_as(client, "grace@test.com")
        resp = client.post("/api/chat/suggest", json={"body": "嗨"})
        assert resp.status_code == 200
        assert resp.json()["fallback"] is True


class TestFollow:
    def test_follow_unfollow_profile(self, client):
        _login_as(client, "henry@test.com")
        me = client.get("/api/auth/me").json()
        ivan = client.post("/api/auth/register", json={"email": "ivan@test.com", "password": "pw123456"}).json()
        ivan_id = client.get(f"/api/auth/me?token={ivan['token']}").json()["id"]

        users = client.get("/api/users").json()
        assert any(u["id"] == ivan_id for u in users["items"])

        resp = client.post(f"/api/users/{ivan_id}/follow")
        assert resp.status_code == 200
        prof = client.get(f"/api/users/{ivan_id}").json()
        assert prof["is_following"] is True
        assert prof["followers"] >= 1

        following = client.get("/api/me/following").json()
        assert any(u["id"] == ivan_id for u in following["items"])

        resp = client.delete(f"/api/users/{ivan_id}/follow")
        assert resp.status_code == 200
        prof = client.get(f"/api/users/{ivan_id}").json()
        assert prof["is_following"] is False

    def test_follow_self_rejected(self, client):
        _login_as(client, "jack@test.com")
        me = client.get("/api/auth/me").json()
        assert client.post(f"/api/users/{me['id']}/follow").status_code == 400

    def test_profile_update(self, client):
        _login_as(client, "kate@test.com")
        resp = client.put("/api/me/profile", json={"name": "小凱", "bio": "喜歡聊天交友"})
        assert resp.status_code == 200
        me = client.get("/api/auth/me").json()
        assert me["name"] == "小凱"
        assert me["bio"] == "喜歡聊天交友"


class TestFeed:
    def test_feed_post_like_comment(self, client):
        _login_as(client, "lily@test.com")
        me = client.get("/api/auth/me").json()

        created = client.post("/api/feed", json={"content": "今天天氣真好，有人要一起聊天嗎？"})
        assert created.status_code == 200
        pid = created.json()["post"]["id"]

        feed = client.get("/api/feed").json()
        post = feed["items"][0]
        assert post["author"]["id"] == me["id"]
        assert post["like_count"] == 0

        assert client.post(f"/api/feed/{pid}/like").json()["liked"] is True
        feed = client.get("/api/feed").json()
        assert feed["items"][0]["like_count"] == 1
        assert feed["items"][0]["liked"] is True

        c = client.post(f"/api/feed/{pid}/comment", json={"content": "我也覺得！"}).json()
        assert c["status"] == "ok"
        comments = client.get(f"/api/feed/{pid}/comments").json()
        assert len(comments["items"]) == 1

        assert client.post(f"/api/feed/{pid}/like").json()["liked"] is False

    def test_feed_requires_login_for_like(self, client):
        created = client.post("/api/feed", json={"content": "匿名發文仍可用"})
        assert created.status_code == 200
        pid = created.json()["post"]["id"]
        assert client.post(f"/api/feed/{pid}/like").status_code == 401
        assert client.post(f"/api/feed/{pid}/comment", json={"content": "x"}).status_code == 401
