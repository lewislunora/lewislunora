# 統一命名規範與溝通語言對照表

> **用途**：統一文件命名、資源命名、技術語言白話化、跨部門溝通標準
> **適用範圍**：全公司 IT 部門
> **文件版本**：v1.0

---

## 一、文件命名規範

### 格式

```
{類型}-{系統}-{描述}-v{版本}.{副版本}.{副檔名}
```

### 類型代碼

| 類型 | 代碼 | 範例 |
|------|------|------|
| SOP | SOP | SOP-K8S-Deploy-v1.0.md |
| Incident Report | INC | INC-2026-001.md |
| Change Request | CR | CR-2026-010.md |
| Knowledge Transfer | KT | KT-ERP-System-v1.0.md |
| Architecture | ARCH | ARCH-System-Overview-v2.1.drawio |
| Meeting Notes | MEET | MEET-Sprint-Review-2026-W20.md |
| Policy | POL | POL-Backup-Policy-v1.0.md |
| Report | RPT | RPT-Weekly-2026-W20.md |

### 版本命名

| 版本變化 | 規則 | 範例 |
|----------|------|------|
| 初版 | v1.0 | SOP-K8S-Deploy-v1.0.md |
| 小幅更新（錯字、格式） | v1.1 | SOP-K8S-Deploy-v1.1.md |
| 重大更新（步驟改變） | v2.0 | SOP-K8S-Deploy-v2.0.md |

---

## 二、系統命名規範

### 格式

```
{環境}-{系統}-{角色}-{序號}
```

| 元素 | 允許值 | 範例 |
|------|--------|------|
| 環境 | prod / stg / dev / dr | prod |
| 系統 | erp / web / api / db / cache | api |
| 角色 | app / worker / lb / master / slave | worker |
| 序號 | 01, 02, ... | |

**範例**：`prod-api-app-01`、`stg-db-master-01`、`dev-cache-01`

### DNS 命名

```
{服務}.{環境}.{部門}.{公司}.local
```

**範例**：`api.prod.engineering.company.local`

### Kubernetes Namespace

| 環境 | Namespace 格式 | 範例 |
|------|---------------|------|
| 生產 | {專案}-prod | erp-prod |
| Staging | {專案}-stg | erp-stg |
| 開發 | {專案}-dev | erp-dev |

---

## 三、Git Repository 命名

### 格式

```
{部門}-{系統}-{元件}
```

| 類型 | 範例 |
|------|------|
| 後端 | backend-erp-api |
| 前端 | frontend-erp-web |
| 基礎設施 | infra-kubernetes-manifest |
| IaC | iac-terraform-aws |
| 文件 | docs-operations |
| Helm Chart | helm-nginx-service |

---

## 四、程式碼命名規範

### 分支命名

```
{類型}/{描述}
```

| 類型 | 範例 |
|------|------|
| feature | feature/add-login-page |
| bugfix | bugfix/fix-null-pointer |
| hotfix | hotfix/critical-security-fix |
| release | release/v2.1.0 |
| chore | chore/update-dependencies |

### Commit Message

```
{類型}({範圍}): {簡短說明}

{詳細說明（可選）}
```

| 類型 | 使用時機 |
|------|----------|
| feat | 新功能 |
| fix | Bug 修正 |
| docs | 文件變更 |
| style | 格式調整（不影響邏輯） |
| refactor | 重構 |
| perf | 效能優化 |
| test | 測試相關 |
| chore | 雜項（CI、設定、依賴） |
| infra | 基礎設施變更 |

### Tag 命名

```
v{MAJOR}.{MINOR}.{PATCH}
```

**範例**：`v2.1.0`

---

## 五、技術 → 白話溝通對照表

> 與 PM、主管、非技術人員溝通時使用

### 基礎設施

| 技術用語 | 白話文（對 PM/主管） |
|----------|---------------------|
| Pod CrashLoopBackOff | 服務啟動後一直異常重啟 |
| Node NotReady | 伺服器異常離線 |
| OOMKilled | 記憶體不足導致服務中斷 |
| Disk I/O Wait 過高 | 硬碟讀寫太慢，影響系統效能 |
| Network Latency Spike | 網路不穩定，回應速度變慢 |
| DNS Resolution Failed | 網址解析失敗，使用者無法連線 |
| SSL Certificate Expired | 安全憑證過期，瀏覽器會顯示不安全 |
| Load Balancer 502 | 後端服務無回應，顯示錯誤頁面 |

### 資料庫

| 技術用語 | 白話文（對 PM/主管） |
|----------|---------------------|
| DB Connection Pool Full | 資料庫連線數爆滿，無法服務 |
| Replication Lag | 資料同步延遲，部分資料顯示較慢 |
| Slow Query | 查詢太慢，影響頁面載入速度 |
| Deadlock | 多筆資料互相等待，系統卡住 |
| Table Lock | 資料表被鎖住，暫時無法寫入 |
| Index Missing | 缺少索引，查詢效率低 |
| Migration Failed | 資料庫結構更新失敗 |

### Kubernetes / Container

| 技術用語 | 白話文（對 PM/主管） |
|----------|---------------------|
| Rolling Update | 逐步更新，不中斷服務 |
| Blue/Green Deploy | 準備新版本環境，切換時不停機 |
| Canary Release | 先讓 5% 使用者用新版本測試 |
| Horizontal Pod Autoscaling | 系統會自動增加/減少運算資源 |
| Resource Quota Exceeded | 容器資源配額不足 |
| Image Pull BackOff | 無法下載更新檔 |
| Evicted Pod | 資源不足被系統強制關閉 |

### Monitoring / Alerting

| 技術用語 | 白話文（對 PM/主管） |
|----------|---------------------|
| P1 Incident | 系統中斷，使用者完全無法使用 |
| MTTR | 從出問題到修好的平均時間 |
| SLA 99.9% | 一年最多當機 8.76 小時 |
| RTO | 災難發生後，多久能恢復服務 |
| RPO | 最多可能遺失多久的資料 |
| Alert Fatigue | 太多無意義的告警，反而忽略真正的問題 |
| False Positive | 誤報，系統其實沒問題 |

### CI/CD / DevOps

| 技術用語 | 白話文（對 PM/主管） |
|----------|---------------------|
| CI Pipeline Failed | 自動化測試失敗，程式無法上線 |
| Build Artifact | 編譯完成的程式檔案 |
| Artifact Registry | 程式檔案倉庫 |
| IaC (Infrastructure as Code) | 用程式碼管理伺服器設定 |
| GitOps | 用 Git 管理一切變更 |
| Change Failure Rate | 上線後出問題的比例 |
| Deployment Frequency | 多久上線一次 |

---

## 六、跨部門溝通原則

### 對 PM 溝通

```
避免：Pod 在 CrashLoopBackOff，kubectl describe 看到 OOMKilled
改用：系統因記憶體不足異常重啟，影響部分使用者，預計 30 分鐘內恢復
```

### 對主管報告

```
避免：今天有三個 P2 Incident
改用：今天有三個需要處理的事件，其中一個影響到 ERP 登入，已於 30 分鐘內排除
```

### 對非技術部門

```
避免：因為 SSL cert expiry 導致 TLS handshake failed
改用：網站的安全憑證到期，使用者連線會出現「不安全」的警告
```

### 對高階主管簡報（口訣：狀況→影響→解法→時程）

```
「今天發生了一個事件，影響了官網約 15 分鐘（狀況+影響），
原因是資料庫連線數異常升高（原因），
我們已經調整設定並增加監控告警（解法），
預計明天前完成根本改善（時程）。」
```

---

> **版本記錄**
> | 版本 | 日期 | 修改內容 | 修改人 |
> |------|------|----------|--------|
> | v1.0 | YYYY-MM-DD | 初版建立 | |
