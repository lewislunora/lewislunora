#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

DOMAIN="${DOMAIN:-}"
IP=$(curl -sS --max-time 10 ifconfig.me || true)

echo "==> 1/8 基本系統套件 + UFW 防火牆"
apt-get update -y
apt-get install -y curl ca-certificates ufw docker.io

if command -v ufw >/dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable || true
fi

echo "==> 2/8 安裝 k3s（單節點，含 Traefik ingress + local-path 儲存）"
if ! command -v k3s >/dev/null; then
    curl -sfL https://get.k3s.io | INSTALL_K3S_KUBECONFIG_MODE=644 sh -
fi
k3s kubectl wait --for=condition=Ready node --all --timeout=180s

echo "==> 3/8 準備構建 context"
cd /opt/platform/src
if [ ! -f requirements.txt ]; then
    cp marketing_system/requirements.txt requirements.txt
fi

echo "==> 4/8 建置平台 image 並匯入 k3s containerd"
if ! docker images --format '{{.Repository}}' | grep -q '^platform-app$'; then
    docker build -t platform-app:latest -f /opt/platform/Dockerfile .
fi
docker save platform-app:latest | k3s ctr images import -

echo "==> 5/8 套用 k8s manifests"
if [ -z "$DOMAIN" ]; then
    DOMAIN="${IP}.sslip.io"
fi
sed -i "s/PLACEHOLDER_HOST/${DOMAIN}/g" /opt/platform/k8s-manifests/ingress.yaml
k3s kubectl apply -f /opt/platform/k8s-manifests/

echo "==> 6/8 建立可選 env secret（放 /opt/platform/platform-env 即可帶入 GROQ_API_KEY 等）"
if [ -f /opt/platform/platform-env ]; then
    k3s kubectl -n platform create secret generic platform-env \
        --from-env-file=/opt/platform/platform-env --dry-run=client -o yaml | k3s kubectl apply -f -
else
    k3s kubectl -n platform create secret generic platform-env \
        --from-literal=DUMMY=1 --dry-run=client -o yaml | k3s kubectl apply -f -
fi
k3s kubectl -n platform rollout status deploy/platform-app --timeout=300s
k3s kubectl -n platform rollout status deploy/platform-mcp --timeout=120s

echo "==> 7/8 驗證"
curl -sS --max-time 30 "http://${DOMAIN}/api/status" || true
echo
echo "==> 8/8 完成"
echo "網站：  http://${DOMAIN}"
echo "MCP：   sse://${DOMAIN}/sse  (streamable http 另走:port 8001)"
echo "admin： http://${DOMAIN}/admin/login"
echo "把 GROQ_API_KEY / TELEGRAM_BOT_TOKEN 寫進 /opt/platform/platform-env 後執行："
echo "    k3s kubectl -n platform create secret generic platform-env --from-env-file=/opt/platform/platform-env --dry-run=client -o yaml | k3s kubectl apply -f -"
echo "    k3s kubectl -n platform rollout restart deploy/platform-app deploy/platform-mcp"