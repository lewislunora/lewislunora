#!/bin/bash
# 翔川 Lewis AI 系統部署腳本

echo "🚀 開始部署翔川 Lewis AI 系統..."

# 1. 創建目錄
mkdir -p /var/www/lewis-ai
cd /var/www/lewis-ai

# 2. 複製檔案（從本地上傳）
# 請先將 lewis_ai_app.py 和 requirements.txt 上傳到伺服器

# 3. 創建虛擬環境
python3 -m venv venv
source venv/bin/activate

# 4. 安裝依賴
pip install -r requirements.txt

# 5. 初始化資料庫
export FLASK_APP=lewis_ai_app.py
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 6. 設定 Nginx
cat > /etc/nginx/sites-available/lewis-ai << 'EOF'
server {
    listen 80;
    server_name lewis-ai.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

ln -sf /etc/nginx/sites-available/lewis-ai /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# 7. 建立 Systemd 服務
cat > /etc/systemd/system/lewis-ai.service << 'EOF'
[Unit]
Description=Lewis AI Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/lewis-ai
Environment="PATH=/var/www/lewis-ai/venv/bin"
ExecStart=/var/www/lewis-ai/venv/bin/python lewis_ai_app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable lewis-ai
systemctl start lewis-ai

echo "✅ 部署完成！"
echo "📍 訪問 http://10.1.0.226:5000"
echo "📍 或 http://your-domain.com"