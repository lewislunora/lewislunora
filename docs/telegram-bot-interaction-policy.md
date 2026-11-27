# Telegram 機器人互動政策：對外社群 vs 對內群組

適用對象：`@ailunora_bot`（翔川 Neo｜曜科技）

## 1. 目的

同一個 bot 會被加進不同性質的 Telegram 群組。為避免外部社群干擾、內部資訊外洩，明確定義**兩種身份、不同權限**的互動規則，並讓 polling 與 webhook 兩條入口共用同一套政策。

## 2. 身份判定

| 身份 | 判定方式 | 預設值 |
|---|---|---|
| **對內（私人工作群）**（internal） | chat_id 在 `TELEGRAM_INTERNAL_CHAT_IDS` 或站長私聊 | `-1003739611959`（翔川 Neo \| 曜科技 ｜Ai）、`626453598` |
| **對外（網站進來的 Group/Channel）** | 以上皆非，包含連動頻道 | 任何由網站連入的群組／頻道，不用 @，自動判斷提問後回短訊 |

> 核心原則：**私人的工作群要 @ 才處理並可控制伺服器；網站來的 Group/Channel 不用 @、只回約 15 字短訊，不能控制伺服器。**
> 目前 bot 在對內群組是**管理員**（可管理聊天、刪訊息、邀請、置頂），但 `can_change_info=false`，不能改群組設定。

## 3. 行為矩陣

| 行為 | 對內（私人工作群／站長私聊） | 對外（網站 Group/Channel，含連動頻道） |
|---|---|---|
| 自由文字是否自動回覆 | ⚠️ 必須 `@ailunora_bot` 才觸發（避免誤吃聊天） | ✅ 不用 @，判斷為提問就自動回覆 |
| 回覆長度 | 完整 AI 回覆 | 約 15 字短訊（最長 60 字，可分段） |
| 非提問的聊天 | 靜默忽略 | 靜默忽略 |
| 內容靈感 `/靈感` | ✅ | ✅（公開安全 prompt） |
| AI 自動化 `/自動化` | ✅ | 🔒 拒絕：「僅供對內群組使用」 |
| 觸發部署 `/部署` | ✅ | 🔒 拒絕，不碰 deploy hook |
| 系統狀態 `/狀態` | ✅（含 API/部署鉤子狀態） | 🔒 拒絕（不揭露內部設定） |
| 知識庫問答 | — | ✅ 優先，找不到才 fallback AI |
| 主動推播 `auto_push` | ✅ 可推到內部 chat | ❌ 永不推播到對外 Group/Channel |

## 4. 指令白名單

| 指令 | 對內 | 對外 | 說明 |
|---|---|---|---|
| `/start`、`/help` | ✅ | ✅ | 自我介紹 / 指令列表（依身份顯示不同清單） |
| `/靈感 [主題]`、`/idea` | ✅ | ✅ | 行銷創意，公開安全 |
| `/自動化 [主題]`、`/auto` | ✅ | 🔒 | 觸發 AI 自動化任務 |
| `/部署`、`/deploy` | ✅ | 🔒 | 觸發 Render deploy hook |
| `/狀態`、`/status` | ✅ | 🔒 | 系統狀態、金鑰設定 |

## 5. 訊息流程

### 5.1 Polling（`openclaw_agent.run_poller`）

```
getUpdates → _process_update
  → telegram_policy.should_respond(message)?
      ├─ 否 → 靜默忽略
      └─ 是 → 身份判定 → 指令白名單檢查 → _handle_command → sendMessage
```

### 5.2 Webhook（`/api/telegram/webhook`）

```
Telegram POST → telegram_webhook
  → should_respond? （對內群組強制 @；對外群組自動判斷提問）
      ├─ 指令 → 白名單檢查 → openclaw_handle
      └─ 自由文字 → 對內：openclaw_handle("靈感")（完整）
                    對外：get_kb_reply → shorten → fallback short_answer（約 15 字）
  → sendMessage（AI 回覆用 Markdown；KB 回覆用 HTML）
```

## 6. 安全邊界

1. 對外社群**不得**取得：`GROQ_API_KEY` 是否存在、deploy hook URL/狀態、DB 內容、內部 chat_id。
2. 對外社群**不得**觸發部署或 AI 自動化排程。
3. 對外 Group/Channel 預設「可互動但不能控制」；若需限制特定群，可設 `TELEGRAM_EXTERNAL_CHAT_IDS` 白名單。
4. 主動推播僅限 `TELEGRAM_PUSH_CHAT_IDS` 內的內部 chat / 頻道，且每日上限 3 則（見 `channels.py`）。
5. 指令支援 `/cmd@ailunora_bot` 形式，避免與群內其他 bot 衝突。

## 7. 環境變數

| 變數 | 用途 |
|---|---|
| `TELEGRAM_INTERNAL_CHAT_IDS` | 對內群組 ID，逗號分隔 |
| `TELEGRAM_LINKED_CHANNEL_IDS` | 連動頻道 ID（比照對外，無控制權） |
| `TELEGRAM_EXTERNAL_CHAT_IDS` | 選用：限制可互動的對外群組 ID；未設則所有 Group/Channel 皆可互動 |
| `TELEGRAM_ALLOWED_CHAT_IDS` | 舊版白名單，仍相容（會與內部 ID 聯集） |
| `TELEGRAM_NOTIFY_CHAT_ID` | 站長私人 chat（預設 `626453598`） |
| `TELEGRAM_BOT_USERNAME` | 標記辨識（預設 `ailunora_bot`） |

## 8. 現況驗證（2026-11-27）

在 `-1003739611959` 實測：

| 時間 | 訊息 | 結果 |
|---|---|---|
| 13:16:55 | `測試 AI 回覆`（自由文字） | ✅ 3 秒內 AI 回覆（舊規則，現已改為需 @） |
| 13:17:12 | `/自動化 AI 行銷` | ✅ 4 秒內回覆自動化任務規劃（舊規則，現已改為需 @） |

新規則已有自動化測試覆蓋：對內未 @ 不回、對外提問免 @ 且回約 15 字、控制指令僅對內可用。webhook 路徑與 poller 共用政策，待 Render env + `setWebhook` 後生效。

## 9. 身份通知（已發送）

| 對象 | chat_id | 角色 | 訊息 |
|---|---|---|---|
| 網站上的 Channel `@lewislunora` | `-1003937328575` | 對外知識機器人 | 🤖 我是翔川 Neo 的對外知識機器人。在這裡只回答問題、查知識庫，回覆盡量簡短（約 15 字）。直接發問即可，不用 @ 我；我不會控制伺服器，也不會主動推播。 |
| 私人工作群 | `-1003739611959` | 自動化維護機器人（訊息查驗） | 🔧 我是自動化維護機器人，負責訊息查驗。在這個私人工作群，請 @ailunora_bot 才會處理，避免誤吃一般聊天。可用 /狀態、/自動化、/部署 等維護指令。 |

> 兩個 chat 互為 linked chat（Channel 的討論群）；網站邀請連結 `t.me/+QgAyWlVyIxFjNmRl` 即指向該 Channel，目前沒有其他已登記的對外群組 ID。新的對外群組第一次發訊息後，可再補發第一列通知。

## 10. 安全加固（2026-11-27）

滲透測試發現身份政策本身安全，但 HTTP 層可绕过，已修復：

| 風險 | 修復 |
|---|---|
| `/api/telegram/webhook` 可偽造 `chat.id`（例如站長私聊）觸發 `/部署` | 改為**失敗關閉**：必須帶 `X-Telegram-Bot-Api-Secret-Token` 且符合 `TELEGRAM_WEBHOOK_SECRET`，否則 403；`setWebhook` 時一併帶 `secret_token` |
| `accounts / content / kb / pages / telegram.broadcast` 匿名可改配置 | 全部補上 `_require_admin(request)`；管理面板的 `api()` 已帶 `credentials: 'include'` |
| `auto-promote / roam/*` 匿名可產生內容並對外發文（耗用 Groq 額度、寫入外部網站） | 補上 `_require_admin(request)`；`admin/promo.html`、`admin/roam.html` 的 fetch 攜帶 cookie |
| `DELETE /api/comments/{id}` 匿名可刪除任意留言 | 補上 `_require_admin(request)` |
| `/api/govdata/ingest` 匿名可用 `force=true` 繞過 10 分鐘冷卻反覆下載 | 公開端點固定走冷卻，不再接受 `force` |
| Bot token 寫死在公開 repo 的 `deploy.sh`、`run_dev_bot.sh`、`start_bot.sh`、`bot_test.log` | 改為只讀環境變數（缺少即終止），log 內 token 已遮罩 |

**仍需人工處理：** 到 @BotFather 執行 `/revoke` 作廢舊 token。舊 token 已公開在 git history，單純改檔案不夠；作廢後才更安全。

> Render 必須設 `TELEGRAM_WEBHOOK_SECRET`，否則 webhook 端點會拒絕所有請求（`setWebhook` 也會略過）。本機 poller 不受影響。

測試：`tests/test_security_permissions.py`（webhook 密鑰、外部群控制指令、匿名改配置/操作、冷卻繞過、憑證外洩掃描），全套 340 passed。
