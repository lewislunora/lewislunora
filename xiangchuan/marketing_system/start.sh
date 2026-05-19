#!/bin/bash
# 翔川 Neo｜曜科技 行銷自動化系統 - 啟動腳本
# 使用方法: ./start.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "  翔川 Neo｜曜科技 行銷自動化系統"
echo "========================================"

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python 3.10+"
    exit 1
fi

# 建立虛擬環境
if [ ! -d "venv" ]; then
    echo "📦 建立虛擬環境..."
    python3 -m venv venv
fi

source venv/bin/activate

# 安裝依賴
echo "📥 安裝依賴..."
pip install -q -r requirements.txt

# 安裝 Playwright 瀏覽器
if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    echo "🌐 安裝 Playwright 瀏覽器..."
    playwright install chromium
fi

# 檢查環境變數
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY 未設定，AI 生成功能將使用離線模式"
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  TELEGRAM_BOT_TOKEN 未設定，Telegram 發文功能不可用"
fi

# 啟動
echo ""
echo "🚀 啟動系統..."
echo "    Dashboard: http://localhost:8742/dashboard"
echo "    API:       http://localhost:8742/api/status"
echo ""

exec uvicorn marketing_system.api.server:app --host 0.0.0.0 --port 8742 --reload
