"""Social login (OAuth2 / Telegram Login Widget) helpers.

Providers:
- google   : Gmail / Google 帳號登入 (OAuth2)
- facebook : Facebook 登入 (OAuth2)
- line     : LINE Login (OAuth2, 使用 LINE Login channel)
- telegram : Telegram Login Widget (無 OAuth redirect，驗證 HMAC)

設定請見 README「社群登入」章節。所有 client id/secret 都從環境變數讀取。
"""
import hashlib
import hmac
import secrets
import urllib.parse
import base64

from ..config import (
    BASE_URL,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    FACEBOOK_APP_ID, FACEBOOK_APP_SECRET,
    INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET,
    LINE_LOGIN_CHANNEL_ID, LINE_LOGIN_CHANNEL_SECRET,
    TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME,
)

PROVIDER_LABELS = {
    "google": "Google / Gmail",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "line": "LINE",
    "telegram": "Telegram",
}

FB_API_VERSION = "v21.0"


def is_configured(provider):
    if provider == "google":
        return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    if provider == "facebook":
        return bool(FACEBOOK_APP_ID and FACEBOOK_APP_SECRET)
    if provider == "instagram":
        return bool(INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET)
    if provider == "line":
        return bool(LINE_LOGIN_CHANNEL_ID and LINE_LOGIN_CHANNEL_SECRET)
    if provider == "telegram":
        return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME)
    return False


def configured_providers():
    return [p for p in ("google", "facebook", "instagram", "line", "telegram") if is_configured(p)]


def callback_uri(provider):
    return f"{BASE_URL}/api/auth/oauth/{provider}/callback"


ALLOWED_NEXT_PREFIXES = ("https://lewislunora.github.io", "https://lewislunora.onrender.com", "http://localhost")


def _allowed_next(path):
    """允許站內路徑或本站 / GH Pages 完整網址，避免開放轉址。"""
    if not path or path.startswith("//"):
        return False
    if path.startswith("/"):
        return True
    return any(path.startswith(p) for p in ALLOWED_NEXT_PREFIXES)


def _csrf_state(next_path):
    """產生 state (含 CSRF token 與回跳路徑)。"""
    return {
        "state": secrets.token_urlsafe(24),
        "next": next_path if _allowed_next(next_path) else "/login.html",
    }


def encode_next(path):
    """base64url 編碼回跳路徑 (cookie 值不含特殊字元)。"""
    return base64.urlsafe_b64encode(path.encode()).decode()


def decode_next(raw):
    if not raw:
        return "/login.html"
    try:
        path = base64.urlsafe_b64decode(raw.encode()).decode()
    except Exception:
        return "/login.html"
    return path if _allowed_next(path) else "/login.html"


def authorize_url(provider, next_path=None):
    """回傳該 provider 的 OAuth 授權網址 + state cookie 內容。"""
    state = _csrf_state(next_path)
    if provider == "google":
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": callback_uri("google"),
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "prompt": "select_account",
            "state": state["state"],
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    elif provider == "facebook":
        params = {
            "client_id": FACEBOOK_APP_ID,
            "redirect_uri": callback_uri("facebook"),
            "response_type": "code",
            "scope": "email",
            "state": state["state"],
        }
        url = f"https://www.facebook.com/{FB_API_VERSION}/dialog/oauth?" + urllib.parse.urlencode(params)
    elif provider == "instagram":
        params = {
            "client_id": INSTAGRAM_APP_ID,
            "redirect_uri": callback_uri("instagram"),
            "response_type": "code",
            "scope": "instagram_business_basic",
            "state": state["state"],
        }
        url = "https://api.instagram.com/oauth/authorize?" + urllib.parse.urlencode(params)
    elif provider == "line":
        params = {
            "client_id": LINE_LOGIN_CHANNEL_ID,
            "redirect_uri": callback_uri("line"),
            "response_type": "code",
            "scope": "profile openid",
            "state": state["state"],
        }
        url = "https://access.line.me/oauth2/v2.1/authorize?" + urllib.parse.urlencode(params)
    else:
        raise ValueError(f"不支援的登入方式: {provider}")
    return url, state


def _token_exchange(provider, code, token_url, data):
    import requests
    data["code"] = code
    data["redirect_uri"] = callback_uri(provider)
    data["grant_type"] = "authorization_code"
    resp = requests.post(token_url, data=data, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Token 交換失敗 ({provider}): {resp.status_code} {resp.text[:200]}")
    return resp.json()


def exchange_and_profile(provider, code):
    """用 authorization code 換取使用者資料。

    回傳 dict: {provider_id, name, email, avatar}
    """
    import requests
    if provider == "google":
        tokens = _token_exchange("google", code, "https://oauth2.googleapis.com/token", {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
        })
        resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo",
                            headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=20)
        resp.raise_for_status()
        u = resp.json()
        return {"provider_id": str(u["sub"]), "name": u.get("name") or u.get("email") or "",
                "email": (u.get("email") or "").lower(), "avatar": u.get("picture") or ""}
    if provider == "facebook":
        tokens = _token_exchange("facebook", code, f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token", {
            "client_id": FACEBOOK_APP_ID,
            "client_secret": FACEBOOK_APP_SECRET,
        })
        resp = requests.get(
            f"https://graph.facebook.com/{FB_API_VERSION}/me",
            params={"fields": "id,name,email,picture.type(large)", "access_token": tokens["access_token"]},
            timeout=20)
        resp.raise_for_status()
        u = resp.json()
        avatar = ""
        if u.get("picture") and u["picture"].get("data") and u["picture"]["data"].get("url"):
            avatar = u["picture"]["data"]["url"]
        return {"provider_id": str(u["id"]), "name": u.get("name") or "",
                "email": (u.get("email") or "").lower(), "avatar": avatar}
    if provider == "line":
        tokens = _token_exchange("line", code, "https://api.line.me/oauth2/v2.1/token", {
            "client_id": LINE_LOGIN_CHANNEL_ID,
            "client_secret": LINE_LOGIN_CHANNEL_SECRET,
        })
        resp = requests.get("https://api.line.me/v2/profile",
                            headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=20)
        resp.raise_for_status()
        u = resp.json()
        return {"provider_id": str(u["userId"]), "name": u.get("displayName") or "",
                "email": "", "avatar": u.get("pictureUrl") or ""}
    if provider == "instagram":
        tokens = _token_exchange("instagram", code, "https://api.instagram.com/oauth/access_token", {
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": INSTAGRAM_APP_SECRET,
        })
        ig_user_id = tokens.get("user_id")
        access_token = tokens.get("access_token", "")
        if not ig_user_id:
            raise RuntimeError("Instagram 未回傳 user_id")
        resp = requests.get("https://graph.instagram.com/me",
                            params={"fields": "id,username,account_type,profile_picture_url",
                                    "access_token": access_token}, timeout=20)
        resp.raise_for_status()
        u = resp.json()
        return {"provider_id": str(u.get("id") or ig_user_id),
                "name": u.get("username") or "Instagram 使用者",
                "email": "", "avatar": u.get("profile_picture_url") or ""}
    raise ValueError(f"不支援的登入方式: {provider}")


def verify_telegram(data):
    """驗證 Telegram Login Widget 回傳的表單資料。

    data 為 dict，需包含 id / first_name / auth_date / hash，
    （optionally: last_name / username / photo_url）。
    驗證成功回傳 profile dict，失敗拋出 ValueError。
    """
    received = data.get("hash", "")
    if not received or not data.get("id") or not data.get("auth_date"):
        raise ValueError("Telegram 回傳資料不完整")
    items = [(k, v) for k, v in data.items() if k != "hash"]
    items.sort()
    check_string = "\n".join(f"{k}={v}" for k, v in items)
    secret = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ValueError("Telegram 資料驗證失敗")
    try:
        if int(data["auth_date"]) < int(__import__("time").time()) - 86400:
            raise ValueError("Telegram 登入已過期")
    except (TypeError, ValueError):
        pass
    photo = data.get("photo_url", "")
    name = " ".join(x for x in [data.get("first_name", ""), data.get("last_name", "")] if x)
    return {"provider_id": str(data["id"]), "name": name,
            "email": "", "avatar": photo, "username": data.get("username", "")}
