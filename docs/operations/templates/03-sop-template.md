# 標準作業程序 (SOP) 模板

> **用途**：所有維運操作之標準化步驟文件
> **適用範圍**：維運部 / SRE / DevOps
> **文件版本**：v1.0

---

## SOP 文件頭 (Header)

| 欄位 | 內容 |
|------|------|
| 文件名稱 | SOP-{系統}-{作業名稱}-v{版本}.{副版本} |
| 文件編號 | SOP-{年份}-{序號:04d} |
| 建立日期 | YYYY-MM-DD |
| 最後更新 | YYYY-MM-DD |
| 文件負責人 | 姓名 |
| 審核主管 | 姓名 |
| 適用系統 | |
| 適用環境 | □ 生產 □ Staging □ 開發 □ 全環境 |
| 機密等級 | □ 一般 □ 內部 □ 機密 |
| 相關文件 | |

---

## 1. 目的

```
（簡述此 SOP 存在的目的、解決什麼問題）
```

## 2. 適用對象與權限

| 角色 | 可執行 | 可查閱 | 備註 |
|------|--------|--------|------|
| SRE / DevOps | ✅ | ✅ | |
| 開發工程師 | ❌ | ✅ | 唯讀 |
| 維運主管 | ✅ | ✅ | |

### 前置條件

執行此 SOP 前需具備：

- [ ] VPN 連線權限
- [ ] AWS / Azure Console 權限
- [ ] kubectl 安裝與配置
- [ ] 特定 IAM Role
- [ ] 相關系統帳號

## 3. 作業頻率

| 類型 | 頻率 | 說明 |
|------|------|------|
| □ 例行 | □ 每日 □ 每週 □ 每月 □ 每季 | |
| □ 非例行 | □ 事件驅動 □ 手動觸發 | |

## 4. 操作步驟

### 4.1 前置檢查

| 步驟 | 動作 | 指令 / 操作 | 預期結果 |
|------|------|------------|----------|
| 1 | 確認系統狀態 | `systemctl status <service>` | active (running) |
| 2 | 檢查磁碟空間 | `df -h` | 使用率 < 80% |
| 3 | 備份現有配置 | `cp config.json config.json.bak` | 備份完成 |
| 4 | 通知相關人員 | Slack #ops 頻道 | 無異常回應 |

### 4.2 主要操作

| 步驟 | 動作 | 指令 / 操作 | 預期結果 |
|------|------|------------|----------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |

### 4.3 驗證

| 步驟 | 動作 | 指令 / 操作 | 預期結果 |
|------|------|------------|----------|
| 1 | 確認服務正常 | | |
| 2 | 確認監控指標 | | |
| 3 | 功能測試 | | |

## 5. 錯誤排除

> 操作過程中可能遇到的常見問題與解法

| 問題現象 | 可能原因 | 解決方法 |
|----------|----------|----------|
| Pod 起不來 | Image 不存在 | `docker pull <image>` 或檢查 Image 名稱 |
| 無法連線 DB | Security Group 未放行 | 檢查 AWS Security Group Inbound Rule |
| SSL 錯誤 | 憑證過期 | `openssl x509 -enddate -noout -in cert.pem` 確認 |
| API 回應 503 | 服務尚未完成啟動 | `kubectl logs <pod>` 確認啟動狀態 |

## 6. 回滾流程 (Rollback)

> **若操作失敗，如何恢復到變更前的狀態**

| 步驟 | 動作 | 指令 / 操作 |
|------|------|------------|
| 1 | | |
| 2 | | |
| 3 | 驗證 | |
| 4 | 通知 | |

## 7. 相關截圖 / 附圖

```
（放置操作畫面截圖或流程圖）
```

## 8. 參考資料

- 相關 SOP：SOP-xxx
- 官方文件 URL：
- Vendor 聯絡窗口：

---

## 範例：SOP-K8S-Deploy

| 欄位 | 範例內容 |
|------|----------|
| 文件名稱 | SOP-K8S-Deploy-v1.0 |
| 建立日期 | 2026-01-15 |
| 文件負責人 | 張三 |
| 適用系統 | 官網 API 服務 |

### 操作步驟（範例）

| 步驟 | 動作 | 指令 | 預期結果 |
|------|------|------|----------|
| 1 | 切換 k8s context | `kubectl config use-context prod` | Switched to context "prod" |
| 2 | 更新 image tag | `kubectl set image deployment/api api=gcr.io/prod/api:v2.3` | deployment "api" image updated |
| 3 | 監控 rollout | `kubectl rollout status deployment/api` | rollout "api" successfully rolled out |
| 4 | 驗證新版運行 | `kubectl get pods -l app=api` | 所有 pod 狀態 Running |
| 5 | 測試 API 健康 | `curl https://api.example.com/health` | `{"status":"ok"}` |

---

> **版本記錄**
> | 版本 | 日期 | 修改內容 | 修改人 |
> |------|------|----------|--------|
> | v1.0 | YYYY-MM-DD | 初版建立 | |
> | v1.1 | YYYY-MM-DD | 更新回滾步驟 | |
