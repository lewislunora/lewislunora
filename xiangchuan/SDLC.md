# 翔川 Neo 行銷自動化系統 — SDLC 設計文件

**專案**：翔川 Neo（AI 行銷自動化 + 即時通知 + 社群自動發文 + 多平台即時接收）
**日期**：2026-08-07
**版本**：v1.0

---

## 1. 目標

- 透過單一網站（GitHub Pages 前端 + Render 後端）獲得**客戶詢單、留言、發案、回覆的即時通知**
- 通知推送至 **Telegram（主）、LINE（備援）、Email（補充）**
- 內容自動發文至 **Facebook / Threads / X**（WebRoamer 或官方 API）
- 逐步支援 **Facebook / Instagram / Threads / X 留言即時接收**（官方 Webhook）
- 全系統以免費 / 低價 tier 運作，成本近零

---

## 2. SDLC 階段總覽

| 階段 | 產出物 | 狀態 |
|---|---|---|
| 1. 規劃 | 需求清單、可行性評估 | ✅ 完成 |
| 2. 分析 | 系統流程圖、資料流 | ✅ 完成 |
| 3. 設計 | 架構、API 規格、DB schema | ✅ 完成 |
| 4. 開發 | 程式碼（可審查） | 🔶 進行中 |
| 5. 測試 | 測試計畫與結果 | 🔶 進行中 |
| 6. 部署 | Render + GH Pages 部署 | ✅ 完成 |
| 7. 維護 | 監控、備份、維運 SOP | 🔶 進行中 |

---

## 3. Phase 1 — 規劃（Planning）

### 3.1 需求來源

- 即時通知：客戶任何動作（表單/留言/發案/回覆）→ 立刻推播給商家
- 多管道：Telegram（主要）、LINE（備援）、Email（補充）
- 自動發文：內容發布後同步至 FB / Threads / X
- 即時接收：社群平台的留言/私訊 → 回傳網站 → 通知商家
- 極低成本：免費方案為主

### 3.2 可行性評估

| 方案 | 成本 | 可行性 | 決策 |
|---|---|---|---|
| Render SMTP 寄信 | 免費但**封鎖出站 587** | ❌ 實測失敗 | **改用 Gmail API（HTTPS）** |
| Gmail API 寄信 | 免費 | ✅ 走 HTTPS 不受限 | **採用** |
| Telegram Bot API | 免費 | ✅ 實測成功 | **採用** |
| LINE Notify | 免費 | ✅ 待 token | **採用** |
| Meta Graph Webhook（FB/IG/Threads）| 免費（需審核）| 🔶 程式已備好，待審核 | 採用 |
| X API v2 Webhook | 付費方案 | 🔶 程式已備好，待訂閱 | 採用 |
| WebRoamer 社群發文 | 付費（已購）| ✅ 已上線 | 採用 |

---

## 4. Phase 2 — 分析（Analysis）

### 4.1 系統流程圖（簡化）

```
客戶動作 ─► 後端 API (Render)
                ├─► 寫入資料庫（各 form 專用 table）
                ├─► 通知模組
                │     ├─► Telegram ✅
                │     ├─► LINE Notify ⚠️ 待 token
                │     └─► Email（Gmail API ✅ / SMTP ❌ 被封）
                └─► WebRoamer ─► FB / Threads / X 自動發文

社群平台留言 ─► 官方 Webhook ─► 後端驗證 ─► 寫入 incoming_messages ─► 通知商家
```

### 4.2 角色與權限

| 角色 | 動作 |
|---|---|
| 客戶 | 填表單、留言、發案、回覆 |
| 社群訪客 | 在 FB/IG/Threads/X 留言或私訊 |
| 商家 | 接收通知、管理內容 |
| 系統 | 自動轉發、推播、發文、接收 webhook |

---

## 5. Phase 3 — 設計（Design）

### 5.1 架構

- **前端**：GitHub Pages（靜態，無伺服器）
- **後端**：Render.com（FastAPI，免費 tier，Cron 每 10 分鐘喚醒）
- **資料**：SQLite（SQLite 檔存於 data/，每日備份並 push 到 repo）
- **通知**：Telegram Bot API + LINE Notify REST API + Gmail API（HTTPS）
- **即時接收**：Meta Graph Webhook / X Account Activity Webhook

### 5.2 資料表

| 表 | 用途 |
|---|---|
| contacts | 預約諮詢表單 |
| comments / community_threads / community_replies | 站內留言與討論區 |
| promo_queue | 自動發文佇列 |
| **incoming_messages**（新增）| 社群平台 webhook 進站訊息 |

### 5.3 API 規格（REST）

| Method | 路徑 | 用途 |
|---|---|---|
| POST | /api/notify | 即時通知統一入口（內部） |
| POST | /api/contact | 預約諮詢表單 |
| POST | /api/comments | 站內留言 |
| GET/POST | /api/webhooks/facebook | Meta Graph 驗證 + 接收 |
| GET/POST | /api/webhooks/instagram | 同上（IG） |
| GET/POST | /api/webhooks/threads | 同上（Threads） |
| GET/POST | /api/webhooks/x | X Account Activity |
| GET | /api/incoming-messages | 查看進站訊息 |
| GET | /api/status | 系統狀態 |
| GET | /api/notify/test | 全通道測試 |
| GET | /api/health | 健康檢查 |

---

## 6. Phase 4 — 開發（Development）

### 6.1 已實作模組

| 模組 | 狀態 |
|---|---|
| `send_to_telegram()` | ✅ 推播成功 |
| `send_to_line()` | ✅ 程式完成，待 token |
| `send_email()` | 🔶 SMTP 失敗 → 改 Gmail API（HTTPS）|
| 通知 retry 機制 | 🔶 待加入（exponential backoff）|
| FB/IG/Threads/X Webhook 接收 | 🔶 待加入 |
| Cron 排程 → 定時檢查 → 自動觸發通知 | ✅ |
| WebRoamer 自動發文 | ✅ 已上線 |

### 6.2 環境變數

```
# 通知
TELEGRAM_BOT_TOKEN / TELEGRAM_NOTIFY_CHAT_ID
LINE_NOTIFY_TOKEN                        # LINE 即時通知
# Email（Gmail API，取代 SMTP）
GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN / GMAIL_USER
# SMTP（僅備援，Render 免費版封鎖出站 587）
SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS
# Webhook 驗證 token
FB_WEBHOOK_VERIFY_TOKEN
X_WEBHOOK_VERIFY_TOKEN
# 平台發文憑證
FACEBOOK_PAGE_TOKEN / LINE_CHANNEL_ACCESS_TOKEN / TWITTER_API_KEY / ...
```

---

## 7. Phase 5 — 測試（Testing）

### 7.1 測試策略

| 層級 | 工具 | 範圍 |
|---|---|---|
| 單元 | pytest | 通知服務、Gmail API、retry、webhook 驗證 |
| 整合 | pytest（TestClient）| API 端點行為 |
| 手動 | 實機提交 | 表單/留言 → Telegram 收到 |

### 7.2 已知限制

- Render 免費 tier 封鎖 SMTP 出站埠 587 → 已改用 Gmail API（HTTPS 443 不受限）
- FB/IG/Threads/X 即時接收需官方審核/訂閱 → 程式已備好，待憑證

---

## 8. Phase 6 — 部署（Deployment）

### 8.1 環境

- 生產：Render（Free）＋ GitHub Pages
- Webhook 需公開 HTTPS 網址：`https://lewislunora.onrender.com/api/webhooks/...`

### 8.2 部署 SOP

1. 前端：`git push` → GH Pages 自動部署
2. 後端：`git push` → Render 自動部署
3. 每次修改後：跑 `pytest` + 實機測試通知

---

## 9. Phase 7 — 維護（Maintenance）

| 項目 | 頻率 | 方式 |
|---|---|---|
| Render 免費 tier 喚醒 | 每 10 分鐘 | Cron ping |
| 資料庫備份 | 每週 | 自動 push `db_backup.json` |
| 通知通道檢查 | 每日 | Telegram 自檢訊息 |
| 錯誤監控 | 即時 | 後端 log + 通知失敗回報 |
| Webhook 憑證有效期 | 定期 | FB/X token 過期偵測 |

---

## 10. Backlog

| 項目 | 狀態 |
|---|---|
| Email 改用 Gmail API | 🔶 開發中 |
| 通知 retry 機制 | 🔶 開發中 |
| FB/IG/Threads/X 即時接收 | 🔶 開發中 |
| LINE token 設定 | ⏳ 等使用者提供 |
| FB/IG/Threads/X 官方審核 | ⏳ 等使用者申請 |
