#!/bin/bash
# 啟動 Telegram Bot + SSH Tunnel
# 使用方式: ./start_bot.sh

cd "$(dirname "$0")"

# 設定 Token（請替換為你的實際 Token 或使用環境變數）
TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8}"

echo "=== 啟動 Telegram Bot @ailunora_bot ==="

# 啟動 Flask Bot
pkill -f "telegram-bot.py" 2>/dev/null
nohup env TELEGRAM_TOKEN="$TELEGRAM_TOKEN" python3 telegram-bot.py > /tmp/bot.log 2>&1 &
BOT_PID=$!
echo "Bot PID: $BOT_PID"
sleep 2

# 驗證 Bot 是否運行
if curl -s http://localhost:5001/ > /dev/null 2>&1; then
    echo "✅ Flask Bot 運行中 (port 5001)"
else
    echo "❌ Bot 啟動失敗，請查看 /tmp/bot.log"
    exit 1
fi

# 啟動 SSH Tunnel
pkill -f "localhost.run" 2>/dev/null
sleep 1
nohup ssh -o StrictHostKeyChecking=no -R 80:localhost:5001 nokey@localhost.run > /tmp/tunnel.log 2>&1 &
echo "SSH Tunnel PID: $!"
sleep 8

# 取得 Tunnel URL
TUN_URL=$(grep -o 'https://[a-z0-9]*\.lhr\.life' /tmp/tunnel.log | head -1)
if [ -n "$TUN_URL" ]; then
    echo "✅ Tunnel URL: $TUN_URL"
    # 設定 Webhook
    RESULT=$(curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook?url=${TUN_URL}/webhook")
    if echo "$RESULT" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin)['ok'] else 1)" 2>/dev/null; then
        echo "✅ Webhook 已設定"
    else
        echo "❌ Webhook 設定失敗"
    fi
else
    echo "❌ Tunnel 啟動失敗，請查看 /tmp/tunnel.log"
    exit 1
fi

echo ""
echo "=== Bot 已上線 ==="
echo "Telegram: https://t.me/ailunora_bot"
echo "頻道: https://t.me/+QgAyWlVyIxFjNmRl"
echo "Bot Log: /tmp/bot.log"
echo "Tunnel Log: /tmp/tunnel.log"
echo "停止 Bot: pkill -f telegram-bot.py && pkill -f localhost.run"
