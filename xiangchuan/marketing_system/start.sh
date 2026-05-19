#!/bin/bash
# 翔川 Neo｜曜科技 行銷自動化系統 - 啟動腳本
# 使用方法: ./start.sh
# Render 部署: 直接使用 start.sh (Render 會設定 PORT 環境變數)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

PORT="${PORT:-8742}"

echo "========================================"
echo "  翔川 Neo｜曜科技 行銷自動化系統"
echo "========================================"
echo "  Port: $PORT"

# 在 Render 上跳過虛擬環境 (Render 已有 Python)
if [ -z "$RENDER" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "❌ 需要 Python 3.10+"
        exit 1
    fi

    if [ ! -d "venv" ]; then
        echo "📦 建立虛擬環境..."
        python3 -m venv venv
    fi
    source venv/bin/activate

    echo "📥 安裝依賴..."
    pip install -q -r requirements.txt

    if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
        echo "🌐 安裝 Playwright 瀏覽器..."
        playwright install chromium
    fi
fi

if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY 未設定，AI 生成功能將使用離線模式"
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  TELEGRAM_BOT_TOKEN 未設定，Telegram 發文功能不可用"
fi

echo ""
echo "🚀 啟動系統..."
echo "    Dashboard: http://localhost:$PORT/dashboard"
echo "    API:       http://localhost:$PORT/api/status"
echo ""

RELOAD_FLAG=""
if [ -z "$RENDER" ]; then
    RELOAD_FLAG="--reload"
fi

exec uvicorn marketing_system.api.server:app --host 0.0.0.0 --port $PORT $RELOAD_FLAG
