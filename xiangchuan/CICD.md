# CI/CD 自動部署指南

## 架构说明

```
本地开发 → 构建 Docker 镜像 → 部署到 k3s
    ↓
自动化脚本: deploy.sh / update.sh
```

---

## 快速部署（本地）

### 1. 首次部署
```bash
cd /Users/wesley/Downloads/lewislunora/xiangchuan
chmod +x deploy.sh update.sh
./deploy.sh
```

### 2. 更新代码后重新部署
```bash
./update.sh
```

---

## 详细步骤

### 步骤1：构建 Docker 镜像
```bash
cd /Users/wesley/Downloads/lewislunora/xiangchuan
docker build -t telegram-bot:latest .
```

### 步骤2：导入镜像到 k3d（如果使用 k3d）
```bash
k3d image import telegram-bot:latest -c mycluster
```
**如果不是用 k3d，跳过此步骤**（k3s 会直接使用本地镜像）

### 步骤3：创建 Secret
```bash
kubectl create secret generic telegram-secret \
  --from-literal=token="8653211794:AAG08xDDj0UDkX18TE60BQSVs-bwwVh8AH8"
```

### 步骤4：部署到 k3s
```bash
kubectl apply -f k8s-deployment.yaml
```

### 步骤5：查看部署状态
```bash
kubectl get pods -l app=telegram-bot
kubectl logs -l app=telegram-bot -f
```

---

## GitHub Actions（云端 CI/CD）

如果使用 GitHub，可以启用 `.github/workflows/deploy.yml`：

1. 在 GitHub 仓库设置 Secrets：
   - `KUBE_CONFIG`：k3s 的 kubeconfig 文件内容
   - `TELEGRAM_TOKEN`：Bot Token

2. 推送代码到 main/master 分支，自动触发部署

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `deploy.sh` | 首次完整部署脚本 |
| `update.sh` | 快速更新脚本（修改代码后） |
| `.github/workflows/deploy.yml` | GitHub Actions 配置 |
| `Dockerfile` | Docker 镜像构建文件 |
| `k8s-deployment.yaml` | k3s 部署配置 |

---

## 常用命令

```bash
# 查看 Pod 状态
kubectl get pods -l app=telegram-bot

# 查看日志
kubectl logs -l app=telegram-bot -f

# 重启部署
kubectl rollout restart deployment/telegram-bot

# 删除部署
kubectl delete -f k8s-deployment.yaml

# 进入 Pod 调试
kubectl exec -it $(kubectl get pod -l app=telegram-bot -o jsonpath='{.items[0].metadata.name}') -- /bin/sh
```

---

## 注意事项

1. **Token 安全**：不要将 Token 提交到代码仓库
2. **镜像拉取策略**：本地开发使用 `imagePullPolicy: Never`
3. **资源限制**：已设置内存 128Mi-256Mi，CPU 100m-200m
4. **健康检查**：应用启动在 5000 端口，k3s 会自动检查健康状态

---

## 故障排查

### Pod 无法启动
```bash
kubectl describe pod -l app=telegram-bot
kubectl logs -l app=telegram-bot --previous
```

### 镜像问题
```bash
# 检查镜像是否存在
docker images | grep telegram-bot

# 如果使用 k3d，重新导入
k3d image import telegram-bot:latest -c mycluster
```

### 查看详细事件
```bash
kubectl get events --sort-by='.lastTimestamp' | grep telegram-bot
```
