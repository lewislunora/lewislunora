# OMNITEST — 通用網站全維度測試平台

任何域名皆可測。模組化、CLI 報告、內建授權防護閘門（沒有授權不動手）。

```
┌────────────────────────────────────────────────────────────────┐
│  discover   全站探索（SPA 感知爬蟲 → 自動產生 target 骨架）      │
│  smoke      全面頁面測試（每條路由：狀態/TTFB/錯誤頁）           │
│  e2e        真瀏覽器渲染驗證（console error / 斷圖 / 死鏈）     │
│  api        API 合約＋健壯性矩陣（方法/缺欄位/壞JSON/XML型別）   │
│  value      數值邊界 fuzzing（整數溢位/浮點極限/注入字串）       │
│  vuln       安全姿態稽核＋唯讀探測（headers/CORS/TLS/SQLi指紋） │
│  human      擬真行為模擬（高斯停留/滑動/滑鼠遊走/鍵入節奏）     │
│  load       高併發負載引擎（Poisson 到達、多階段 RPS、多進程）  │
│  login-storm 海量登入風暴（N 萬帳號登入＋session 保活心跳）      │
│  games      通用產品掃描器（遊戲/彩票/體育/直播/真人娛樂）      │
└────────────────────────────────────────────────────────────────┘
```

## 各平台類型支援（games 模組）

`games` 模組已擴充成**通用產品掃描器**，透過 target profile 設定播放類型與觀測模式，即可掃描不同平台：

| 平台類型 | play_type | observation | 觀測重點 |
|---------|-----------|-------------|---------|
| **遊戲門戶**（如 gfg.win） | `iframe` | `traffic` | iframe 啟動、即時流量、WebSocket |
| **彩票** | `native` | `ws` | 原生選號頁面、開獎 WebSocket 推送 |
| **體育投注** | `native` | `odds` | 賽事頁面、賠率變化、即時比分 |
| **直播** | `video` | `stream` | video 串流健康（playing/buffering/stalled） |
| **真人娛樂** | `iframe` | `traffic` | 真人荷官 iframe、即時流量 |

**games 模組可設定欄位**（寫在 target profile）：

```python
TARGET = Target(
    ...
    games_list_endpoint="room-list",      # 取得產品/房間列表的 Endpoint.name
    games_detail_endpoint="room-detail",  # 取得產品詳情的 Endpoint.name
    games_url_endpoint="",                 # 播放 URL API（非 iframe 平台可留空）
    games_catalog_path="data.rooms",      # JSON dot-path：列表在 response 的位置
    games_id_field="roomId",              # 唯一 ID 欄位名
    games_name_field="roomName",          # 顯示名稱欄位名
    games_play_type="video",              # iframe | video | canvas | native
    games_play_selector="video, .player video",  # 播放器 CSS selector
    games_info_selector=".room-info, main",      # 詳情頁內容 CSS selector
    games_observation="stream",           # traffic | ws | odds | stream | none
    games_detail_extra_fields=["streamUrl", "viewerCount"],  # 額外必填欄位
)
```

**內建平台範本**（把 URL / API / 欄位名改為你的實際值即可）：

| 範本 | 檔案 |
|------|------|
| 遊戲門戶 | `omnitest/targets/gfg_win.py` |
| 彩票 | `omnitest/targets/lottery_template.py` |
| 體育投注 | `omnitest/targets/sports_template.py` |
| 直播 | `omnitest/targets/livestream_template.py` |
| 通用網站 | `omnitest/targets/wikipedia.py`、`github.py` |

```bash
# 掃描直播平台所有直播間（每個房間：串流健康 + 截圖）
./run.sh run --target omnitest.targets.livestream_template --modules games \
    --game-wait 12 --game-observe 8
```

## 匯出與報表

每次執行會自動產生：

- **JSON**：`omnitest_artifacts/results.json`（每筆 finding：timestamp/module/check/status/detail）
- **CSV**：`omnitest_artifacts/results.csv`（可用 Excel 開啟）
- **遊戲截圖拼圖**：`omnitest_artifacts/games_collage.png`（所有產品縮圖網格）
- **監控模式**：`--watch 3600` 每小時自動重跑一套並匯出

```bash
./run.sh run --target omnitest.targets.gfg_win --modules smoke --watch 3600 \
    --watch-out omnitest_artifacts/watch   # 排程監控
```

## 安裝

```bash
cd omnitest
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# Chrome 需已安裝；chromedriver 由 Selenium Manager 自動下載
```

## 快速開始

```bash
# 查看模組
./run.sh list-modules

# 對既有 target profile 跑輕量全套
./run.sh run --target omnitest.targets.gfg_win --modules smoke,e2e,api,value

# 任何新網站：先探索，自動生成骨架 profile
./run.sh discover https://example.com --out omnitest/targets/example.py

# 擬真人（3 人逛 10 分鐘）
./run.sh run --target omnitest.targets.example --modules human --users 3 --minutes 10

# 多域名同時測試：逗號分隔 target，--parallel 控制同時站點數
./run.sh run --target omnitest.targets.a,omnitest.targets.b,omnitest.targets.c \
    --modules smoke,e2e,api,value --parallel 3
```

## 高併發 / 高流量 / 海量登入（HEAVY 模組）

> **授權閘門**：`load`、`login-storm`、`vuln` 必須同時滿足
> ① CLI 加 `--i-am-authorized`　② target 的 `authorized_domains` 含目標主機。
> 對「看起來是 production」的域名跑 login-storm 另需 `--allow-prod-login-storm`。

```bash
# 階段式負載：60 秒爬到 100 RPS → 120 秒撐 1000 RPS，8 個 worker process
./run.sh run --target omnitest.targets.gfg_win --modules load \
    --stages "60:100,120:1000" --processes 8 --i-am-authorized

# 登入風暴：5 萬帳號登入並保活 5 分鐘（單機）
./run.sh run --target omnitest.targets.gfg_win --modules login-storm \
    --users 50000 --storm-hold 300 --processes 16 \
    --i-am-authorized --allow-prod-login-storm
```

### 規模對照表（login-storm / CCU）

| 節點規格 | 可支撐同時在線 | 指令 |
|---|---|---|
| 1 台 8 核 | ~1–2 萬 | `--processes 8` |
| 1 台 32 核 | ~5–8 萬 | `--processes 24`（記得 `ulimit -n 1000000`）|
| N 台機器 | 線性擴展 | 每台跑同一指令、各自分攤 users，事後彙總 |
| 幾十萬 | ~20–40 台小機 或 4–8 台大機 | 同上 |
| 幾百萬 | 100+ 台 或改用 k6 cloud/LGTM 分散式 | 本引擎可作為單節點 agent |

引擎特性：Poisson 到達（擬真）、連線池共享、每 VU 獨立 cookie jar、
p50/p95/p99 延遲、峰值 CCU、登入成功率、錯誤 Top-N。

## Target Profile 寫法

```python
from omnitest.core.config import Endpoint, LoginProfile, Target

def ok(d): return d.get("code") == 0

TARGET = Target(
    name="mysite",
    base_url="https://staging.mysite.com",
    seed_paths=["/", "/#/games", "/about"],          # SPA hash route OK
    global_headers={"language": "US"},
    endpoints=[                                       # api/value/load 用
        Endpoint(name="list", method="POST", path="/ow/getGameList",
                 json_body={"language": "en_us"}, success_check=ok, weight=3),
    ],
    login=LoginProfile(                               # login-storm 用
        url="https://staging.mysite.com/api/login",
        username_field="account", password_field="pwd",
        success_path="code", success_value=0,
        token_path="data.token",
        username_pattern="qa_load_{n}@test.local", password="***",
        heartbeat_path="/api/ping", heartbeat_interval=30,
    ),
    authorized_domains=["staging.mysite.com"],        # 授權範圍
    console_error_allowlist=[r"favicon"],
)
```

## 各模組判定邏輯

| 模組 | PASS | WARN | FAIL |
|---|---|---|---|
| smoke | 200 且 TTFB ≤ 預算 | 非 200／逾時 | 5xx／堆疊蹤跡 |
| e2e | console 乾淨、圖片全載 | 無內部連結可驗 | JS SEVERE、斷圖、死鏈 |
| api | baseline 符約定 | 變體 envelope 不一致 | 5xx／trace |
| value | ≥98% 注入被優雅處理 | 90–98% | <90% 或洩漏 SQL/trace |
| vuln | 有標頭、無暴露 | 缺安全標頭 | 檔案暴露／XSS 反射／SQL 洩漏 |
| load | 錯誤率 <2% 且 p95 ≤ 預算 | — | 反之 |
| login-storm | 登入成功率 ≥99% | ≥95% | 反之 |

## gfg.win 首輪實測發現（2026-08-26）

- `value`：`null`/array body 打 `/ow/getNews`、`getTopWins` 等 → **HTTP 500**（code 1001）
- `api`：malformed JSON、XML content-type、型別翻轉 → 多端點 **HTTP 500**
- `e2e`：首頁 9 張斷圖（certification-mobile*.webp）、banner 影片指向不存在網域
  `dnxl7xaw6auyx.gfg.win`（應為 cloudfront.net）
- `vuln`：HSTS/CSP/X-Content-Type-Options/X-Frame-Options/Referrer-Policy 全缺
- `load`：~120 RPS 即出現 33% ReadError、p95≈8s（CloudFront→origin 容量或限流）
- TLS 1.3 正常、憑證剩 148 天、無 SQL 錯誤洩漏、CORS 無任意反射

## 安全原則（對齊滲透服務規範）

1. 沒有授權書，heavy 模組直接拒跑
2. 只測 `authorized_domains` 宣告範圍
3. vuln 模組僅唯讀探測，無破壞性 payload
4. login-storm 預設導向 staging；production 需額外明示同意
5. 全域 `--max-rps` 政治性限速保護輕量模組
