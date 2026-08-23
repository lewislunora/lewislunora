# 翔川 Neo｜曜科技 行銷自動化系統

AI 驅動的多平台內容發布系統。一次撰寫，同步發布到 Telegram、Line、Facebook、Instagram、X/Twitter、Threads、Dcard、小紅書。內建即時通知（Telegram / LINE / Email）與社群平台留言即時接收（Meta / X Webhook）。

## 快速啟動

```bash
cd marketing_system
./start.sh
```

啟動後開啟 http://localhost:8742/dashboard

## 設定環境變數

```bash
export GROQ_API_KEY="your-groq-api-key"      # AI 內容生成
export TELEGRAM_BOT_TOKEN="your-bot-token"    # Telegram 發文
export TELEGRAM_NOTIFY_CHAT_ID="626453598"    # 即時通知收件 chat id
export LINE_NOTIFY_TOKEN="your-line-token"    # LINE 即時通知（選擇性）
```

所有變數皆可在 Web Dashboard 上設定，不需修改程式碼。

### 即時通知（Telegram / LINE / Email）

| 通道 | 環境變數 | 說明 |
|---|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_NOTIFY_CHAT_ID` | 主要通道，推薦 |
| LINE | `LINE_NOTIFY_TOKEN` | 至 https://notify-bot.line.me/ 發行權杖後填入 |
| Email | `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_USER` | **Gmail API（HTTPS）**，Render 免費版封鎖 SMTP 587 埠，因此改用 Gmail API |
| Email（備援） | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | 僅在未設定 Gmail API 時使用 |

即時通知會推播：預約諮詢、站內留言、發案/貼文、回覆。測試用 `GET /api/notify/test`。

### 社群平台留言即時接收（Webhook）

程式已就緒，需先向各平台申請官方 API 存取權後填入對應環境變數：

| 平台 | 端點 | 環境變數 |
|---|---|---|
| Facebook / Instagram / Threads | `GET/POST /api/webhooks/{platform}` | `FB_WEBHOOK_VERIFY_TOKEN`（Meta App Dashboard 設定的驗證 token） |
| X | `GET/POST /api/webhooks/x` | `TWITTER_API_SECRET`（Consumer Secret，用於 CRC 驗證） |

進站訊息會寫入 `incoming_messages` 表並觸發即時通知，可用 `GET /api/incoming-messages` 查看。

## 社群登入（Gmail / Facebook / LINE / Telegram）

網頁版 `docs/login.html` 提供五種第三方登入（Gmail / Facebook / Instagram / LINE / Telegram），統一走 `/api/auth/*`，登入後以 httpOnly cookie `token` 識別身份（沿用 `users` 表）。`/api/auth/me` 可用 cookie 或 `?token=` 查詢目前使用者。

### 環境變數

| 登入方式 | 環境變數 | 必要設定 |
|---|---|---|
| 通用 | `BASE_URL` | 網站正式網址（如 `https://你的網域`），OAuth callback 會以它為基底 |
| Google / Gmail | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | 見下方「Google 設定」 |
| Facebook | `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | 見下方「Facebook 設定」 |
| Instagram | `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | 見下方「Instagram 設定」 |
| LINE | `LINE_LOGIN_CHANNEL_ID`, `LINE_LOGIN_CHANNEL_SECRET` | 見下方「LINE 設定」（注意：與 LINE Notify 不同） |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` | 見下方「Telegram 設定」 |

### 各平台後台設定步驟

**Google / Gmail**
1. 到 [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → 建立專案（或沿用）。
2. OAuth consent screen → 設為「External」並發布（公開），加入測試使用者或提交審核。
3. Credentials → Create credentials → **OAuth client ID → Web application**。
4. Authorized redirect URIs 加入 `{BASE_URL}/api/auth/oauth/google/callback`。
5. 複製 Client ID / Client Secret 填入環境變數。

**Facebook**
1. 到 [Meta for Developers](https://developers.facebook.com) → My Apps → 建立 App（類型選「Consumer」或企業）。
2. 左側 Products → 新增 **Facebook Login**。
3. Valid OAuth Redirect URIs 加入 `{BASE_URL}/api/auth/oauth/facebook/callback`。
4. App Review 發布（Public）或加入測試人員；`App ID` / `App Secret` 填入環境變數。
5. 若需 Email，需在 App Review 送出 `public_profile, email` 權限審核。

**Instagram**（Instagram API with Instagram Login，需「商業/創作者」帳號）
1. 到 [Meta for Developers](https://developers.facebook.com) → 同一 Meta App → Products → 新增 **Instagram**。
2. Instagram → **Instagram API with Instagram Login** → Set up，產生 `Instagram App ID` / `Instagram App Secret`。
3. Instagram Login → 把 `{BASE_URL}/api/auth/oauth/instagram/callback` 加入 **Redirect URI**。
4. 模式需切到 **Live**（或用測試帳號），個人版 Instagram 帳號無法以此流程登入，需先切換為「專業帳號（商業/創作者）」。
5. 填入 `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET`。Instagram 不提供 Email，只取得使用者名稱與大頭貼。

**LINE**
1. 到 [LINE Developers](https://developers.line.biz) → 建立 Provider → **LINE Login** Channel（不是 Messaging API，也不是 Notify）。
2. Channel 基本設定取得 `Channel ID`；Channel Secret 在「Issue」產生。
3. LINE Login → Callback URL 加入 `{BASE_URL}/api/auth/oauth/line/callback`。
4. 填入 `LINE_LOGIN_CHANNEL_ID` / `LINE_LOGIN_CHANNEL_SECRET`。LINE 的 Email 需額外申請（預設不提供），登入只取得名稱與大頭貼。

**Telegram**
1. 用 [@BotFather](https://t.me/BotFather) 建立機器人（沿用現有 bot token 即可），記錄 Bot username。
2. 對 BotFather 送出 `/setdomain`，設定你的網域（Telegram Login Widget 只允許白名單網域）。
3. 填入 `TELEGRAM_BOT_USERNAME`（不含 `@`）。因 widget 與 callback 需同源，請由後端網域（`{BASE_URL}/api/auth/telegram/start`）執行 Telegram 登入。

### 相關 API

- `GET /api/auth/providers` - 列出已啟用的登入方式與授權網址
- `GET /api/auth/oauth/{google|facebook|instagram|line}/authorize?next=/路徑` - 導向第三方登入
- `GET /api/auth/oauth/{google|facebook|instagram|line}/callback` - 回呼（換 token、建帳號、寫 cookie）
- `GET /api/auth/telegram/start` - Telegram Login Widget 頁
- `POST /api/auth/telegram/callback` - 驗證 Telegram widget 回傳並登入
- `GET /api/auth/set-cookie?token=...&next=/...` - 讓 email/密碼登入也寫入 httpOnly cookie
- `GET /api/auth/logout` - 登出（清除 cookie）

網頁可用 `docs/js/auth.js`（`Auth.me()` / `Auth.providers()` / `Auth.updateAuthUI()`）快速接入：在頁面放入 `<div data-auth="in">已登入</div><div data-auth="out">未登入</div>` 並呼叫 `Auth.updateAuthUI()`。

## 系統架構

```
marketing_system/
├── config.py              # 系統設定
├── database.py            # SQLite 資料庫
├── scheduler.py           # 自動排程發布
├── ai/generator.py        # AI 內容生成 (Groq)
├── api/server.py          # FastAPI 後端
├── frontend/dashboard.html # Web 管理介面
├── platforms/
│   ├── telegram_connector.py   # Telegram Bot API
│   ├── line_connector.py       # Line Messaging API
│   ├── facebook_connector.py   # Facebook Graph API
│   ├── twitter_connector.py    # X/Twitter API v2
│   └── browser_automation.py   # Playwright 自動化
└── start.sh               # 一鍵啟動
```

## 支援平台

| 平台 | 方式 | 設定需求 |
|------|------|---------|
| Telegram | Bot API | Bot Token + Chat ID |
| Line | Messaging API | Channel Access Token |
| Facebook | Graph API | Page Access Token |
| Instagram | Graph API | Instagram Business Account |
| X/Twitter | API v2 | Bearer Token ($100/mo) |
| Threads | Playwright | 帳號密碼 |
| Dcard | Playwright | 帳號密碼 |
| 小紅書 | Playwright | 帳號密碼 |

## 社交平台（交友＋聊天＋動態牆）

整合 Threads（動態牆）、Facebook（私訊/交友）、Dcard（匿名討論）功能的會員社群。網頁在 `docs/social/`（動態牆、私訊、找人、個人頁），需要登入。

### 動態牆 Feed
- `POST /api/feed` - 發文（body: `content`）
- `GET /api/feed?page=1&per_page=15` - 動態牆列表（含作者、讚數、留言數）
- `POST /api/feed/{id}/like` - 按讚/收回讚（reactions key `feed:{id}` + ❤）
- `POST /api/feed/{id}/comment` - 留言（body: `content`）
- `GET /api/feed/{id}/comments` - 留言列表

### 交友 Follow
- `GET /api/users?q=關鍵字&per_page=50` - 搜尋/列出使用者（含 `is_following`）
- `GET /api/users/{id}` - 個人頁資料（貼文數、追蹤者/追蹤中、bio）
- `POST /api/users/{id}/follow` / `DELETE /api/users/{id}/follow` - 追蹤/取消
- `GET /api/me/following` - 我的追蹤名單
- `GET/PUT /api/me/profile` - 讀取/更新自我介紹（name、bio）

### 私訊 Chat
- `GET /api/chat/conversations` - 對話列表（含未讀數、最後訊息）
- `POST /api/chat/open` - 開啟/建立與某人的對話（body: `user_id`）
- `GET /api/chat/conversations/{id}/messages?limit=80` - 讀訊息
- `POST /api/chat/send` - 送訊息（body: `conversation_id`, `body`）
- `GET /api/chat/unread` - 未讀總數（導覽列紅點）
- `POST /api/chat/suggest` - AI 回覆建議（需 `GROQ_API_KEY`）

前端共用層 `docs/js/social.js`：`Social.api()`、`Social.requireLogin()`、`Social.renderNav()`（含未讀輪詢）、`Social.avatarHtml()`、`Social.timeAgo()`、`Social.notify()`。github.io 上自動改用 `https://lewislunora.onrender.com` 為 API 基底。

## API 端點

- `GET /api/status` - 系統狀態
- `POST /api/content` - 建立內容
- `GET /api/content` - 列出內容
- `POST /api/content/{id}/publish` - 立即發布
- `POST /api/content/ai-generate` - AI 生成內容
- `POST /api/accounts` - 新增平台帳號
- `GET /api/schedules` - 排程狀態
- `GET /dashboard` - Web 管理介面
- `GET /api/notify/test` - 測試所有通知通道
- `GET/POST /api/webhooks/facebook|instagram|threads|x` - 社群留言即時接收
- `GET /api/incoming-messages` - 查看進站訊息

## SDLC

完整生命週期設計文件見專案根目錄 `SDLC.md`。
