# 回滾手冊（2026-11-27 安全加固）

適用範圍：程式／部署設定、後台 `site_settings`、管理員權限、資料庫內容。
所有操作都先在**本機／測試環境驗證**，再上正式環境。

---

## 0. Checkpoint

安全加固已提交並打標：

```bash
git show --stat security-hardening-2026-11-27  # 查看這次改了哪些檔案
git revert security-hardening-2026-11-27       # 建立反向 commit（保留可追溯性）
git rev-parse security-hardening-2026-11-27    # 需要 hash 時用這個取得，勿寫死在文件裡
```

---

## 1. 程式／部署設定回滾

### 整批退回加固前

```bash
git revert security-hardening-2026-11-27     # 建議：留下可追溯的反向 commit
# 或
git checkout security-hardening-2026-11-27^ -- xiangchuan/marketing_system/api/server.py
```

### 只退回單一檔案

```bash
git checkout security-hardening-2026-11-27^ -- <檔案路徑>
git diff --cached                            # 檢查後再 commit
```

### Telegram webhook／環境變數誤改

加固後 webhook 是**失敗關閉**：缺少或寫錯 `TELEGRAM_WEBHOOK_SECRET` 時，
`/api/telegram/webhook` 全部回 403，`setWebhook` 也不會註冊。

```bash
export TELEGRAM_BOT_TOKEN='...'              # 或 deploy.sh 用的 TELEGRAM_TOKEN
export TELEGRAM_WEBHOOK_SECRET='...'         # 必須與 Telegram 端註冊時一致

cd xiangchuan
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py \
  webhook --url https://你的網域.onrender.com

# 臨時停用 webhook（改回本機 poller）
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py webhook --delete
```

> 若舊 token 已外洩，回滾**不應該**把它寫回檔案；先到 @BotFather `/revoke`，再換新 token。

---

## 2. 後台 `site_settings` 被改錯

每次 `PUT /api/site-settings` 都會把舊值寫入 `site_settings_history`。

```bash
# 管理端 API：看歷史 / 還原上一版 / 還原指定版本
curl -b 'token=管理員token' https://你的網域/api/site-settings/<key>/history
curl -X POST -b 'token=管理員token' https://你的網域/api/site-settings/<key>/rollback
curl -X POST -b 'token=管理員token' 'https://你的網域/api/site-settings/<key>/rollback?history_id=3'
```

本機（不經 API，管理員被鎖住也能用）：

```bash
cd xiangchuan
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py site-settings <key> --list
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py site-settings <key>
```

---

## 3. 管理員權限被改錯（break-glass）

`/api/admin/set-admin` 本身需要管理員，且每次變動都會寫入 `admin_audit`。
若最後一位管理員把自己降權，用本機腳本直接改 DB：

```bash
cd xiangchuan
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py \
  admin --email me@example.com --grant

# 查看 audit（需管理員）
curl -b 'token=管理員token' https://你的網域/api/admin/audit
```

>`--revoke` 請謹慎；腳本同樣會寫 audit，便于追責。

---

## 4. 資料庫內容被誤刪／誤改

```bash
cd xiangchuan
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py db status
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py db dump    # 先備份現在
./marketing_system/venv/bin/python marketing_system/scripts/ops_rollback.py db restore # 從 backup JSON 還原
```

- `database.py` 已有保護：若 backup 的內容表比現 DB 多，自動 dump 會**跳過**，不會覆蓋備份。
- `db restore` 會先 `init_db()` 建表，再依 backup 逐表還原；backup 沒有的表不會被清空。

---

## 5. 回滾後驗證

```bash
cd xiangchuan
./marketing_system/venv/bin/python -m pytest marketing_system/tests -q
curl https://你的網域/api/admin/check -b 'token=管理員token'
curl -i https://你的網域/api/telegram/webhook   # 應為 403（失敗關閉仍生效）
```

測試病例在 `marketing_system/tests/test_security_permissions.py::TestRollbackPaths`。
