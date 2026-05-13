#!/bin/bash
# AI 虛擬推廣行銷助手 - 自動部署腳本
# 將 Telegram Bot 部署到本地 k3s 集群

set -e  # 遇到錯誤立即退出

echo "=================================================="
echo "AI 虛擬推廣行銷助手 - k3s 部署"
echo "=================================================="

# 配置
BOT_TOKEN="${TELEGRAM_TOKEN:-8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8}"
IMAGE_NAME="telegram-bot"
IMAGE_TAG="latest"
NAMESPACE="default"

echo "1. 檢查 k3s 集群狀態..."
kubectl cluster-info || {
    echo "錯誤：k3s 集群未運行，請先啟動集群"
    exit 1
}

echo "2. 構建 Docker 鏡像..."
cd "$(dirname "$0")"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "3. 準備部署到 k3s..."
# 在 k3d/k3s 中，使用本地鏡像需要導入
if command -v k3d &> /dev/null; then
    echo "  檢測到 k3d，導入鏡像到集群..."
    k3d image import ${IMAGE_NAME}:${IMAGE_TAG} -c mycluster
else
    echo "  警告：未檢測到 k3d，假設使用本地鏡像（imagePullPolicy: Never）"
fi

echo "4. 創建/更新 Secret..."
kubectl create secret generic telegram-secret \
    --from-literal=token="${BOT_TOKEN}" \
    --namespace=${NAMESPACE} \
    --dry-run=client \
    -o yaml | kubectl apply -f -

echo "5. 部署到 k3s..."
kubectl apply -f k8s-deployment.yaml

echo "6. 等待部署完成..."
kubectl rollout status deployment/telegram-bot --namespace=${NAMESPACE} --timeout=120s

echo "7. 檢查部署狀態..."
kubectl get pods -l app=telegram-bot
kubectl get svc telegram-bot-svc

echo ""
echo "=================================================="
echo "部署完成！"
echo "=================================================="
echo ""
echo "查看日誌："
echo "  kubectl logs -l app=telegram-bot -f"
echo ""
echo "查看狀態："
echo "  kubectl get pods,svc -l app=telegram-bot"
echo ""
echo "刪除部署："
echo "  kubectl delete -f k8s-deployment.yaml"
echo "=================================================="
