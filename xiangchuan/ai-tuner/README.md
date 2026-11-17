# AI Tuner — 自動量測與調整網站

這個目錄是「Site AI Tuner」的狀態與設定，對應工具是
`xiangchuan/marketing_system/scripts/ai_tuner.py`。

## 它做什麼

每天（GitHub Actions `site-ai-tuner.yml`）：

1. 抓真實數據：Render `/api/analytics/summary`、`/api/status`、兩站 HTTP 探測。
2. 掃描 `docs/` 產生頁面庫存（角色、標題、大小）。
3. 把數據 + 庫存 + 前次決策丟給 Groq，要求輸出結構化 JSON。
4. 只自動套用 **low risk** 的「逐字字串替換」，套用後跑測試、commit、push。
5. push 會觸發 Render 與 GitHub Pages 重新部署。
6. 決策寫入 `decisions.jsonl`，下一輪用新數據驗證效果。

## 守門規則（config.json）

- 只能替換既有文字，不能整檔重寫、新增或刪除檔案。
- `old_text` 必須在檔案中**恰好出現一次**。
- 每次最多 8 個檔案、120 行變更、6 個行動。
- 黑名單（不可碰）：DB／backup JSON、`.env`／金鑰／憑證、k8s manifests、
  terraform、`k3s-platform/`、`.github/`、`omnitest/`、`work/`、
  `marketing_system/data/`、`marketing_system/tests/`、本目錄
  `ai-tuner/`、以及 tuner 自己的腳本（防止 AI 改掉守門邏輯）。
- 中風險（medium）預設不自動套用，高風險（high）一律不自動。

## 手動操作

```bash
cd xiangchuan/marketing_system/scripts

# 只收集與提案（需要 GROQ_API_KEY）
python ai_tuner.py collect --since 168
python ai_tuner.py inventory
python ai_tuner.py propose

# 看報告
python ai_tuner.py report --out ../ai-tuner/reports/$(date +%F).md

# 乾跑：只驗證會套用哪些變更
python ai_tuner.py apply --proposals ../ai-tuner/proposals/$(date +%F).json --dry-run

# 真正套用（會跑測試；--push 才會推送）
python ai_tuner.py apply --proposals ../ai-tuner/proposals/$(date +%F).json --yes --push
```

## 決策紀錄

`decisions.jsonl` 每行一筆 JSON：日期、診斷、已套用/被跳過的行動與原因。
同一變更（檔案 + 新文字）在 `dedupe_days` 天內不會重複套用。

## 紅線

- 不造假流量、不捏造數字；AI 的輸入只能是 API 實測值。
- 不碰資料庫、憑證、部署 manifest。
- 若測試失敗，不 commit、不部署。
