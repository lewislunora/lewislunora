# OMNITEST gfg.win 全站測試報告

> **測試工具**：OMNITEST 全域全頻譜網站自動化測試平台  
> **測試目標**：`gfg.win`（Vue3 SPA 遊戲門戶，共 67 款遊戲）  
> **測試時間**：`2026-08-26` ｜ 測試範圍：smoke / e2e / api / games / value / vuln / human / load / login-storm  
> **命令列**：`python -m omnitest run --target omnitest.targets.gfg_win --modules e2e,games --game-wait 10 --game-observe 6`

---

## 總覽

| 模組 | PASS | WARN | FAIL | 狀態 |
|------|------|------|------|------|
| e2e（靜態頁面） | 13 | 5 | 2 | FAIL |
| games（67 款遊戲） | 60 | 5 | 2 | FAIL |
| **合計** | **73** | **10** | **4** | — |

---

## 靜態頁面（e2e）

| 頁面 | Console | 圖片 | 標題 | 狀態 |
|------|---------|------|------|------|
| `#/games` | ✅ 乾淨 | ✅ 全載入 | ✅ GFG GAMES - games | ✅ |
| `#/gameInfo/300001` | ✅ 乾淨 | ✅ 全載入 | ✅ GFG GAMES - games | ✅ |
| `#/game/300001` | ✅ 乾淨 | ✅ 全載入 | ✅ GFG GAMES - play | ✅ |
| `#/about` | ✅ 乾淨 | ✅ 全載入 | ✅ GFG GAMES - general information | ✅ |
| **`#/` 首頁** | — | **9 張破圖** | — | 🔴 |

### 首頁問題詳情

- **banner / 影片網域**：`dnxl7xaw6auyx.gfg.win`（DNS 無法解析，非有效 CloudFront 網域）
- **失效圖片**：9 張 `.webp` 圖片返回 404 / 無法載入
- **建議**：檢查 CDN 配置，確認圖片網域正確（應為 `*.cloudfront.net`）

---

## 全部 67 款遊戲運行狀況

每一款遊戲均經過以下四層驗證：
1. **API 詳情**：`getGameDetail` 回傳完整遊戲資料（name / description / banner）
2. **發牌 URL**：`getGameUrl` 正常回傳可播放 provider iframe 網址
3. **詳情頁 UI**：`#/gameInfo/<id>` 渲染正常、遊戲名稱顯示、無破圖
4. **遊玩頁運行**：`#/game/<id>` iframe 啟動、有即時網路流量、畫面非全黑

| 遊戲 ID | 名稱 | API 詳情 | 發牌 URL | 遊玩頁 | 畫面分析 | 狀態 |
|---------|------|---------|---------|--------|---------|------|
| 300001 | 1-MIN HASH ROULETTE | ✅ | ✅ 224ms | ✅ live 6ms | 80% dark | ⚠️ 詳情頁破圖×2 |
| 300010 | FORTUNE DICE | ✅ | ✅ 232ms | ✅ live 2ms | 74% dark | ✅ |
| 300013 | SEA BATTLE | ✅ | ✅ 280ms | ✅ live 3ms | 2% bright | ✅ |
| 300014 | HASH RING | ✅ | ✅ 116ms | ✅ live 3ms | 10% | ✅ |
| 300015 | HASH TWIST | ✅ | ✅ 216ms | ✅ live 3ms | 2% | ✅ |
| **300016** | **HASH MAFIA** | **🔴 description 空** | ✅ 209ms | ✅ live 3ms | 44% | **🔴** |
| 300002 | 1-MIN HASH SIC BO | ✅ | ✅ 204ms | ✅ live 3ms | 51% | ✅ |
| 300003 | 3-MIN HASH SIC BO | ✅ | ✅ 113ms | ✅ live 3ms | 18% | ✅ |
| 300004 | 1-MIN HASH EVEN ODD | ✅ | ✅ 217ms | ✅ live 3ms | — | ⚠️ 遊戲名未找到 |
| 300005 | 3-MIN HASH EVEN ODD | ✅ | ✅ 237ms | ✅ live 6ms | — | ⚠️ 詳情頁破圖×2 |
| 300006 | 1-MIN HASH LUCKY | ✅ | ✅ 119ms | ✅ live 4ms | 18% | ✅ |
| 300007 | 3-MIN HASH LUCKY | ✅ | ✅ 217ms | ✅ live 3ms | 18% | ✅ |
| 300008 | 1-MIN HASH BULL BULL | ✅ | ✅ 215ms | ✅ live 4ms | 22% | ✅ |
| 300009 | 3-MIN HASH BULL BULL | ✅ | ✅ 123ms | ✅ live 4ms | 22% | ✅ |
| 300011 | 1-MIN HASH SSC | ✅ | ✅ 109ms | ✅ live 5ms | 69% | ✅ |
| 300012 | 5-MIN HASH SSC | ✅ | ✅ 115ms | ✅ live 3ms | 69% | ✅ |
| 201 | Golden Toad Fish | ✅ | ✅ 1375ms | ✅ live 824ms | — | ✅ |
| 5 | Red vs Black | ✅ | ✅ 1402ms | ✅ live 832ms | — | ✅ |
| 9 | Baccarat | ✅ | ✅ 1363ms | ✅ live 824ms | — | ✅ |
| 10 | Bull-Bull | ✅ | ✅ 1197ms | ✅ live 825ms | — | ✅ |
| 11 | Dragon Tiger Game | ✅ | ✅ 1273ms | ✅ live 827ms | — | ✅ |
| 12 | Golden Flower | ✅ | ✅ 1172ms | ✅ live 845ms | — | ✅ |
| 14 | Banker This Bar | ✅ | ✅ 1407ms | ✅ live 416ms | — | ✅ |
| 18 | Blackjack | ✅ | ✅ 1207ms | ✅ live 415ms | — | ✅ |
| 22 | Banker Pai Gow | ✅ | ✅ 1586ms | ✅ live 833ms | — | ✅ |
| 25 | Casino Bull-Bull | ✅ | ✅ 1681ms | ✅ live 826ms | — | ✅ |
| 27 | Bull-Bull Wild | ✅ | ✅ 1415ms | ✅ live 855ms | — | ⚠️ 詳情頁破圖×1 |
| 29 | No Commission Baccarat | ✅ | ✅ 1518ms | ✅ live 418ms | — | ✅ |
| 32 | Super Bull-Bull | ✅ | ✅ 1180ms | ✅ live 833ms | — | ✅ |
| 113 | Banker Bull-Bull | ✅ | ✅ 1345ms | ✅ live 435ms | — | ✅ |
| 115 | Three Cards Up Banker | ✅ | ✅ 1169ms | ✅ live 876ms | — | ✅ |
| 117 | Banker Three-Facecard | ✅ | ✅ 1216ms | ✅ live 829ms | — | ✅ |
| 126 | Four Cards Up Banker | ✅ | ✅ 1276ms | ✅ live 824ms | — | ✅ |
| 202 | God of Wealth Fish | ✅ | ✅ 1334ms | ✅ live 826ms | — | ✅ |
| 203 | Dragon | ✅ | ✅ 1175ms | ✅ live 826ms | — | ✅ |
| 204 | Mermaid Story | ✅ | ✅ 1307ms | ✅ live 420ms | — | ✅ |
| 205 | World Cup Shooting | ✅ | ✅ 1191ms | ✅ live 412ms | — | ✅ |
| 301 | Lucky Pixiu | ✅ | ✅ 1187ms | ✅ live 823ms | — | ✅ |
| 302 | Good Fortune | ✅ | ✅ 1239ms | ✅ live 827ms | — | ✅ |
| 303 | Xmas Mission | ✅ | ✅ 1385ms | ✅ live 820ms | — | ✅ |
| 304 | Wang Lai | ✅ | ✅ 1400ms | ✅ live 829ms | — | ✅ |
| 305 | Mahjong Win | ✅ | ✅ 1350ms | ✅ live 825ms | — | ✅ |
| 306 | Gemstone | ✅ | ✅ 1327ms | ✅ live 835ms | — | ✅ |
| 307 | 777 | ✅ | ✅ 1284ms | ✅ live 824ms | — | ✅ |
| 308 | Joker Triple | ✅ | ✅ 1161ms | ✅ live 826ms | — | ✅ |
| 309 | Buffalo | ✅ | ✅ 1185ms | ✅ live 822ms | — | ✅ |
| 310 | Book of Death | ✅ | ✅ 1052ms | ✅ live 415ms | — | ✅ |
| 311 | Roma | ✅ | ✅ 1236ms | ✅ live 823ms | — | ✅ |
| 313 | LongLongLong | ✅ | ✅ 1265ms | ✅ live 830ms | — | ✅ |
| 320 | Super Ace | ✅ | ✅ 1300ms | ✅ live 847ms | — | ✅ |
| 323 | Wonderland Treasure | ✅ | ✅ 1411ms | ✅ live 876ms | — | ✅ |
| 324 | Piggy Fortune | ✅ | ✅ 1488ms | ✅ live 823ms | — | ✅ |
| 901 | Fortune Tiger | ✅ | ✅ 1367ms | ✅ live 817ms | — | ✅ |
| 902 | Wild Bandito | ✅ | ✅ 1327ms | ✅ live 827ms | — | ✅ |
| 903 | Mahjong Ways | ✅ | ✅ 1239ms | ✅ live 831ms | — | ✅ |
| 904 | Fortune Ox | ✅ | ✅ 1231ms | ✅ live 827ms | — | ✅ |
| 80002 | Four Cards Up Banker | ✅ | ✅ 125ms | ✅ live 6ms | 89% | ✅ |
| 80003 | Three Cards Up Banker | ✅ | ✅ 116ms | ✅ live 3ms | 88% | ✅ |
| 80004 | Banker Bull-Bull 2 | ✅ | ✅ 109ms | ✅ live 3ms | 88% | ✅ |
| 80005 | Supreme Baccarat | ✅ | ✅ 108ms | ✅ live 3ms | 88% | ✅ |
| **80006** | **Supreme Dragon Tiger** | ✅ | ✅ 239ms | **⚠️ blank-screen** | **100% black** | **⚠️** |
| 81001 | 777 plus | ✅ | ✅ 114ms | ✅ live 6ms | 88% | ✅ |
| 81002 | Mahjong Win 2 | ✅ | ✅ 107ms | ✅ live 4ms | 88% | ✅ |
| 81003 | Super Ace 2 | ✅ | ✅ 122ms | ✅ live 5ms | 88% | ✅ |
| 81004 | Mahjong Ways 3 | ✅ | ✅ 116ms | ✅ live 3ms | 88% | ✅ |
| **82005** | **Dragon Vein Treasure** | **🔴 description 空** | ✅ 118ms | ✅ live 7ms | 88% | **🔴** |
| 250001 | Rock Paper Scissors | ✅ | ✅ 195ms | ✅ live 3ms | 88% | ✅ |

---

## 需修復項目（依優先序）

| 優先序 | 問題 | 影響範圍 | 建議 |
|--------|------|---------|------|
| **🔴 P1** | #300016 HASH MAFIA：`gameDescription` 空值 | API 回傳不完整 | 補充遊戲描述 |
| **🔴 P1** | #82005 Dragon Vein Treasure：`gameDescription` 空值 | API 回傳不完整 | 補充遊戲描述 |
| **⚠️ P2** | #80006 Supreme Dragon Tiger：畫面全黑（blank=100%） | 用戶看到黑屏 | 排查遊戲載入邏輯 |
| **⚠️ P3** | #300001 / #300005 / #27 詳情頁破圖 | 部分遊戲無法顯示 banner | 檢查圖片資源配置 |
| **⚠️ P3** | #300004 詳情頁找不到遊戲名稱 | UI 渲染問題 | 檢查前端路由或模板 |
| **🔴 P3** | 首頁 `dnxl7xaw6auyx.gfg.win` DNS 解析失敗 | banner / 影片無法載入 | 修正 CDN 網域配置 |
| **🔴 P3** | 首頁 9 張 `.webp` 圖片 404 | 部分圖片缺失 | 確認靜態資源部署完整 |

---

## 其他發現（歷史測試）

- **安全標頭缺失**：無 HSTS / CSP / X-Frame-Options / X-Content-Type-Options
- **API 錯誤處理**：畸形 JSON payload 回傳 500（非預期錯誤碼）
- **CDN 網域拼寫**：`dnxl7xaw6auyx.gfg.win` ≠ `*.cloudfront.net`（建議確認）
- **Baccarat (#9)**：曾偵測到指向 staging 主機 `stagegameweb.geodwfeowkg.com`（建議複查）
- **抗壓極限**：約 120 RPS 時回應時間急遽上升至不可接受水平

---

## 附錄

- **遊戲截圖目錄**：`omnitest_artifacts/games/<gameId>.png`（每款遊戲各一張）
- **遊戲截圖拼圖**：`omnitest_artifacts/games_collage.png`（67 款遊戲縮圖網格）
- **JSON 結果檔**：`omnitest_artifacts/results.json`
- **CSV 結果檔**：`omnitest_artifacts/results.csv`

---

*報告由 OMNITEST 自動化測試平台產生*
