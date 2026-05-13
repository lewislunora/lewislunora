#!/bin/bash
# 快速更新腳本 - 修改代碼後快速重新部署

set -e

echo "🔧 更新 Telegram Bot..."

# 1. 重新構建鏡像
echo "1. 構建新鏡像..."
docker build -t telegram-bot:latest /Users/wesley/Downloads/lewislunora/xiangchuan/

# 2. 導入到 k3d（如果在用 k3d）
if command -v k3d &> /dev/null; then
    echo "2. 導入鏡像到 k3d..."
    k3d image import telegram-bot:latest -c mycluster
fi

# 3. 重啟部署
echo "3. 重啟部署..."
kubectl rollout restart deployment/telegram-bot

# 4. 等待更新完成
echo "4. 等待更新完成..."
kubectl rollout status deployment/telegram-bot --timeout=120s

echo "✅ 更新完成！"
kubectl get pods -l app=telegram-bot
