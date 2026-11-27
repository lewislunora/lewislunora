#!/usr/bin/env bash
# setup_ai_stack.sh — AI 自動化／分潤／自動發文前置 key 自動設定
#
# 功能：
#   1) 自動把 GROQ_API_KEY 寫入 GitHub repo secret（Actions）
#      - POST /repos/{repo}/actions/secrets/encryptions → PUT /repos/{repo}/actions/secrets/{name}
#   2) 自動把 GROQ_API_KEY / TELEGRAM_BOT_TOKEN 寫入 Render 環境變數
#      - 需提供 RENDER_API_KEY 與 RENDER_SERVICE_ID；未提供則只印說明
#
# 用法：
#   export GROQ_API_KEY="gsk_xxx"
#   export TELEGRAM_BOT_TOKEN="123456:ABC-xxx"
#   ./setup_ai_stack.sh
#
#   # 或直接帶參數
#   ./setup_ai_stack.sh --groq "gsk_xxx" --telegram "123:ABC"
#
# 前置：
#   - 手機／電腦上裝好 curl 與 bash
#   - GitHub PAT（classic，repo scope）— 用於寫 Actions secret
#   - Render API Key + Service ID（用於寫 Render env var）

set -euo pipefail

REPO="${REPO_NAME:-lewislunora/lewislunora}"
GROQ_KEY="${GROQ_API_KEY:-}"
TG_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
RENDER_API_KEY="${RENDER_API_KEY:-}"
RENDER_SERVICE_ID="${RENDER_SERVICE_ID:-}"

usage() {
  cat <<EOF
用法：./setup_ai_stack.sh [--groq "KEY"] [--telegram "TOKEN"] [--render-service-id "ID"] [--render-api-key "KEY"]

環境變數也可：GROQ_API_KEY, TELEGRAM_BOT_TOKEN, RENDER_API_KEY, RENDER_SERVICE_ID

範例：
  GROQ_API_KEY=gsk_xxx TELEGRAM_BOT_TOKEN=123:ABC ./setup_ai_stack.sh
  ./setup_ai_stack.sh --groq "gsk_xxx" --telegram "123:ABC" --render-service-id svc_xxx
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --groq) GROQ_KEY="$2"; shift 2 ;;
    --telegram) TG_TOKEN="$2"; shift 2 ;;
    --render-service-id) RENDER_SERVICE_ID="$2"; shift 2 ;;
    --render-api-key) RENDER_API_KEY="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "未知參數：$1"; usage ;;
  esac
done

if [[ -z "$GROQ_KEY" ]]; then echo "✖ GROQ_API_KEY 未提供"; usage; fi
if [[ -z "$TG_TOKEN" ]]; then echo "✖ TELEGRAM_BOT_TOKEN 未提供"; usage; fi

echo "▶ GitHub secret 設定：${REPO} → GROQ_API_KEY"
ENCRYPT_RESP=$(curl -sS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN:-ghp_xxx}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d "{\"plaintext\": \"${GROQ_KEY}\"}" \
  "https://api.github.com/repos/${REPO}/actions/secrets/encryptions")
echo "$ENCRYPT_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin))'
ENC_VALUE=$(echo "$ENCRYPT_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["encrypted_value"])')
ENC_KEY=$(echo "$ENCRYPT_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["key_id"])')
curl -sS -X PUT \
  -H "Authorization: Bearer ${GITHUB_TOKEN:-ghp_xxx}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d "{\"encrypted_value\": \"${ENC_VALUE}\", \"key_id\": \"${ENC_KEY}\"}" \
  "https://api.github.com/repos/${REPO}/actions/secrets/GROQ_API_KEY"
echo ""
echo "✅ GitHub secret GROQ_API_KEY 已寫入"

echo ""
echo "▶ Render 環境變數設定"
if [[ -n "${RENDER_API_KEY:-}" && -n "${RENDER_SERVICE_ID:-}" ]]; then
  curl -sS -X PATCH \
    -H "Authorization: Bearer ${RENDER_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"envVars\": [
      {\"key\": \"GROQ_API_KEY\", \"value\": \"${GROQ_KEY}\", \"sync\": false},
      {\"key\": \"TELEGRAM_BOT_TOKEN\", \"value\": \"${TG_TOKEN}\", \"sync\": false}
    ]}" \
    "https://api.render.com/v1/services/${RENDER_SERVICE_ID}"
  echo ""
  echo "✅ Render env vars 已寫入（Render 通常會自動 redeploy）"
else
  echo "⚠️ 未提供 RENDER_API_KEY / RENDER_SERVICE_ID，跳過 Render 寫入。"
  echo "   之後請到 Render Dashboard → Environment → Add Environment Variable 手動加："
  echo "     GROQ_API_KEY = ${GROQ_KEY}"
  echo "     TELEGRAM_BOT_TOKEN = ${TG_TOKEN}"
fi

echo ""
echo "🎉 完成。驗證順序："
echo "   1) Render Dashboard 確認 Environment 已更新"
echo "   2) 觸發 redeploy（Render 免費層約 15 分鐘冷啟動）"
echo "   3) 開手機瀏覽器到 https://lewislunora.onrender.com/api/status"
echo "      → ai_available 應為 true、telegram_bot_token_set 應為 true"
