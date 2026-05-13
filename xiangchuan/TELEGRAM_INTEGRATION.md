# AI 虛擬推廣行銷助手 - Telegram Bot 整合指南

## 方案概览

### 方案 A：链接分享（最简单）
在 Telegram Bot 中发送 HTML 页面链接，用户点击打开。

**实现步骤：**
1. 将 `ai-character.html` 部署到公网（k3s + Ingress）
2. Bot 发送消息：`您可在此体验 AI 助手：https://your-domain.com/ai-character.html`

### 方案 B：功能迁移到 Bot（推荐）
将 AI 回复逻辑迁移到 Telegram Bot，用户直接在 Telegram 内对话。

---

## 方案 B 详细步骤

### 1. 获取 Telegram Bot Token
1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新 Bot
3. 按提示设置 Bot 名称和用户名
4. 获得 Token（类似：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 设置环境变量
```bash
export TELEGRAM_TOKEN="你的Bot Token"
export PUBLIC_URL="你的公网地址"  # 例如：https://your-domain.com
```

### 3. 创建 Secret
```bash
# 直接编辑 k8s-deployment.yaml，替换 YOUR_TELEGRAM_BOT_TOKEN_HERE
# 或使用 kubectl 创建：
kubectl create secret generic telegram-secret \
  --from-literal=token="你的Bot Token"
```

### 4. 构建 Docker 镜像
```bash
cd /Users/wesley/Downloads/lewislunora/xiangchuan
docker build -t telegram-bot:latest .
```

### 5. 部署到 k3s
```bash
kubectl apply -f k8s-deployment.yaml
```

### 6. 设置 Webhook
```bash
# 如果你有公网地址：
curl "http://localhost:5000/set_webhook?url=https://your-domain.com"

# 或使用 ngrok 等工具做内网穿透：
ngrok http 5000
# 然后使用 ngrok 提供的地址设置 webhook
```

### 7. 测试 Bot
在 Telegram 中搜索你的 Bot，发送消息测试：
- `你好`
- `分析我的產品`
- `寫一篇推廣文案`
- `制定行銷策略`
- `社群媒體規劃`

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `telegram-bot.py` | Flask 后端，处理 Telegram 消息 |
| `requirements.txt` | Python 依赖 |
| `Dockerfile` | Docker 镜像构建文件 |
| `k8s-deployment.yaml` | Kubernetes 部署配置 |
| `ai-character.html` | 原始 Web 界面（可选部署） |

---

## 快速测试（本地）

```bash
cd /Users/wesley/Downloads/lewislunora/xiangchuan
pip3 install -r requirements.txt

# 设置环境变量
export TELEGRAM_TOKEN="你的Token"
export PUBLIC_URL="http://localhost:5000"

# 启动服务
python3 telegram-bot.py

# 在另一个终端设置 webhook（如果有公网地址）
curl "http://localhost:5000/set_webhook?url=你的公网地址"
```

---

## 注意事项

1. **公网访问**：Telegram webhook 需要公网可访问的 HTTPS 地址
   - 选项1：使用云服务器部署
   - 选项2：使用 ngrok / cloudflared 等内网穿透工具
   - 选项3：部署到 k3s + 配置 Ingress + 域名

2. **HTTPS 要求**：Telegram webhook 必须使用 HTTPS

3. **Token 安全**：不要将 Token 提交到代码仓库

---

## 整合 ai-character.html（可选）

如果想保留 Web 界面，可以：
1. 将 `ai-character.html` 部署到 k3s（使用 nginx）
2. Bot 发送消息时附上链接
3. 用户点击链接在浏览器中体验完整动画效果

部署命令：
```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-character-web
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ai-character-web
  template:
    metadata:
      labels:
        app: ai-character-web
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
        volumeMounts:
        - name: html
          mountPath: /usr/share/nginx/html
      volumes:
      - name: html
        configMap:
          name: ai-character-html
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-character-html
data:
  index.html: |
$(cat ai-character.html)
---
apiVersion: v1
kind: Service
metadata:
  name: ai-character-svc
spec:
  selector:
    app: ai-character-web
  ports:
  - port: 80
    targetPort: 80
  type: LoadBalancer
EOF
```
