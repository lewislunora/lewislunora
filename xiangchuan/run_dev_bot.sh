#!/bin/bash
# 開發助理啟動腳本
# 自動關閉 Webhook → 啟用 Polling 模式
cd "$(dirname "$0")"
TOKEN="${TELEGRAM_BOT_TOKEN:-8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8}"

echo "🔌 關閉 Webhook，切換至 Polling 模式..."
curl -s "https://api.telegram.org/bot$TOKEN/deleteWebhook" | python3 -m json.tool

echo ""
echo "🤖 啟動開發助理..."
echo "按 Ctrl+C 停止"
python3 dev_assistant.py

# 退出時自動恢復 Webhook
echo ""
echo "🔌 恢復 Webhook → Render..."
RENDER_URL="${RENDER_API_URL:-https://lewislunora.onrender.com}"
curl -s -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$RENDER_URL/api/telegram/webhook\"}" | python3 -m json.tool
