# 翔川 Neo｜曜科技 行銷自動化系統

AI 驅動的多平台內容發布系統。一次撰寫，同步發布到 Telegram、Line、Facebook、Instagram、X/Twitter、Threads、Dcard、小紅書。

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
```

所有變數皆可在 Web Dashboard 上設定，不需修改程式碼。

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

## API 端點

- `GET /api/status` - 系統狀態
- `POST /api/content` - 建立內容
- `GET /api/content` - 列出內容
- `POST /api/content/{id}/publish` - 立即發布
- `POST /api/content/ai-generate` - AI 生成內容
- `POST /api/accounts` - 新增平台帳號
- `GET /api/schedules` - 排程狀態
- `GET /dashboard` - Web 管理介面
