#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "用法: $0 <公網IP> [ssh-user=ubuntu] [domain]"
    echo "範例: $0 146.56.111.222"
    echo "      $0 146.56.111.222 ubuntu ops.example.com"
    exit 1
fi

IP="$1"
USER="${2:-ubuntu}"
DOMAIN="${3:-}"
KEY="${ORACLE_KEY:-$HOME/.ssh/oracle_arm_ed25519}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"

SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
SCP="scp -i $KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"

echo "==> 1/6 SSH 連線測試 ($USER@$IP)"
$SSH "$USER@$IP" 'echo ok'

echo "==> 2/6 建立遠端目錄並上傳原始碼（排除 venv/快取）"
$SSH "$USER@$IP" 'sudo mkdir -p /opt/platform/src && sudo chown -R '"$USER"':'"$USER"' /opt/platform'
tar czf - \
    -C "$REPO" \
    --exclude='marketing_system/venv' \
    --exclude='marketing_system/.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    marketing_system docs k3s-platform/mcp_server.py \
    | $SSH "$USER@$IP" 'tar xzf - -C /opt/platform/src'

echo "==> 3/6 上傳 Dockerfile + bootstrap + manifests"
$SCP "$HERE/remote/Dockerfile" "$HERE/remote/bootstrap.sh" "$USER@$IP":/opt/platform/
$SCP -r "$HERE/k8s-manifests" "$USER@$IP":/opt/platform/

echo "==> 4/6 執行遠端自動化部署（k3s ＋ image ＋ ingress）"
if [ -n "$DOMAIN" ]; then
    $SSH "$USER@$IP" "sudo DOMAIN=${DOMAIN} bash /opt/platform/bootstrap.sh"
else
    $SSH "$USER@$IP" "sudo bash /opt/platform/bootstrap.sh"
fi

URL="http://${DOMAIN:-$IP.sslip.io}"
echo "==> 5/6 網站健康檢查 ($URL)"
sleep 5
curl -sS --max-time 30 "$URL/api/status" || true
echo

echo "==> 6/6 全站體檢（與 Render 同套腳本）"
python3 "$REPO/marketing_system/scripts/site_health_check.py" --base "$URL" || {
    echo "體檢有 WARN/FAIL，請看上方明細；網址仍是 $URL"
}
echo
echo "部署完成。MCP endpoint: sse://${DOMAIN:-$IP.sslip.io}/sse"