#!/usr/bin/env python3
"""
翔川 Lewis AI 創業系統 - 基礎範例
功能：AI + DevOps + SRE + 命理 + 社群登入 + Telegram Bot
"""

from flask import Flask, render_template_string, request, jsonify, redirect
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import os
import hashlib
import secrets
from datetime import datetime

# ==================== 初始化 ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lewis_ai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== 資料庫模型 ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    email = db.Column(db.String(150), unique=True)
    phone = db.Column(db.String(20), unique=True)
    provider = db.Column(db.String(50))  # google, apple, line, facebook, etc.
    provider_id = db.Column(db.String(150))
    avatar = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

class FortuneRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    birth_date = db.Column(db.String(20))
    zodiac = db.Column(db.String(20))
    chinese_zodiac = db.Column(db.String(20))
    five_element = db.Column(db.String(20))
    result = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MusicRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    prompt = db.Column(db.Text)
    style = db.Column(db.String(50))
    result_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=True)
    level = db.Column(db.Integer, default=1)
    commission_rate = db.Column(db.Float, default=0.1)
    total_earn = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== 命理功能 ====================
ZODIAC = {
    '01/01-01/19': '摩羯座', '01/20-02/18': '水瓶座', '02/19-03/20': '雙魚座',
    '03/21-04/19': '白羊座', '04/20-05/20': '金牛座', '05/21-06/20': '雙子座',
    '06/21-07/22': '巨蟹座', '07/23-08/22': '獅子座', '08/23-09/22': '處女座',
    '09/23-10/22': '天秤座', '10/23-11/21': '天蠍座', '11/22-12/21': '射手座',
    '12/22-12/31': '摩羯座'
}

CHINESE_ZODIAC = {
    1980: '猴', 1981: '雞', 1982: '狗', 1983: '豬', 1984: '鼠',
    1985: '牛', 1986: '虎', 1987: '兔', 1988: '龍', 1989: '蛇',
    1990: '馬', 1991: '羊', 1992: '猴', 1993: '雞', 1994: '狗'
}

FIVE_ELEMENTS = ['木', '火', '土', '金', '水']

def get_zodiac(date_str):
    try:
        for k, v in ZODIAC.items():
            if date_str in k:
                return v
    except:
        pass
    return '未知'

def get_chinese_zodiac(year):
    return CHINESE_ZODIAC.get(year, '未知')

def get_five_element(year):
    cycle = (year - 1984) % 10
    elements = ['木', '火', '土', '金', '水']
    return elements[cycle % 5]

# ==================== 路由 ====================

# 首頁
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# OAuth 登入（模擬）
@app.route('/login/<provider>')
def oauth_login(provider):
    # 這裡應該調用真實的 OAuth API
    # 模擬自動創建帳號
    user_id = hashlib.md5(f"{provider}_{secrets.token_hex(8)}".encode()).hexdigest()[:8]
    
    user = User.query.filter_by(provider=provider, provider_id=user_id).first()
    if not user:
        user = User(
            username=f"{provider}_{user_id}",
            email=f"{user_id}@{provider}.com",
            provider=provider,
            provider_id=user_id,
            avatar=f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_id}"
        )
        db.session.add(user)
        db.session.commit()
    
    login_user(user)
    return redirect('/dashboard')

# 儀表板
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE, user=current_user)

# 命理分析
@app.route('/fortune', methods=['GET', 'POST'])
@login_required
def fortune():
    result = None
    if request.method == 'POST':
        birth_date = request.form.get('birth_date')
        year = int(birth_date.split('-')[0])
        
        result = {
            'zodiac': get_zodiac(birth_date[5:]),
            'chinese_zodiac': get_chinese_zodiac(year),
            'five_element': get_five_element(year),
            'message': f'你是{birth_date}出生的{get_chinese_zodiac(year)}座，{get_five_element(year)}屬旺。'
        }
        
        # 存儲記錄
        record = FortuneRecord(
            user_id=current_user.id,
            birth_date=birth_date,
            zodiac=result['zodiac'],
            chinese_zodiac=result['chinese_zodiac'],
            five_element=result['five_element'],
            result=result['message']
        )
        db.session.add(record)
        db.session.commit()
    
    return render_template_string(FORTUNE_TEMPLATE, result=result)

# AI 音樂生成（模擬）
@app.route('/music', methods=['GET', 'POST'])
@login_required
def music():
    result = None
    if request.method == 'POST':
        prompt = request.form.get('prompt')
        style = request.form.get('style', 'pop')
        
        # 模擬 AI 音樂生成
        result = {
            'prompt': prompt,
            'style': style,
            'result_url': f'https://example.com/music/{secrets.token_hex(8)}.mp3',
            'message': f'已生成 {style} 風格的音樂：{prompt[:20]}...'
        }
        
        record = MusicRecord(
            user_id=current_user.id,
            prompt=prompt,
            style=style,
            result_url=result['result_url']
        )
        db.session.add(record)
        db.session.commit()
    
    return render_template_string(MUSIC_TEMPLATE, result=result)

# DevOps/SRE 工具
@app.route('/devops')
@login_required
def devops():
    return render_template_string(DEVOPS_TEMPLATE)

# Telegram Bot Webhook
@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    from telegram import Update
    from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
    
    update = Update.de_json(request.get_json(encoding='utf-8'))
    
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        if text == '/start':
            await update.message.reply_text('🚀 歡迎使用翔川 AI！\n輸入你的出生日期 (YYYY-MM-DD) 獲得命理分析')
        elif text and '-' in text and len(text) == 10:
            year = int(text.split('-')[0])
            result = f"🎯 命理分析：\n星座：{get_zodiac(text[5:])}\n生肖：{get_chinese_zodiac(year)}\n五行：{get_five_element(year)}"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text('請輸入 /start 或你的出生日期')
    
    return jsonify({'status': 'ok'})

# 登出
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

# API: 代理推廣
@app.route('/api/agent/register', methods=['POST'])
def agent_register():
    data = request.json
    user_id = data.get('user_id')
    parent_id = data.get('parent_id')
    
    agent = Agent(user_id=user_id, parent_id=parent_id)
    db.session.add(agent)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': '代理註冊成功'})

# ==================== HTML 模板 ====================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>翔川 Lewis AI - 未來科技</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
               background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        .hero { text-align: center; padding: 60px 0; }
        h1 { font-size: 48px; background: linear-gradient(135deg, #00d4ff, #00ff88); 
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 20px; }
        .subtitle { font-size: 24px; color: #aaa; margin-bottom: 40px; }
        .login-methods { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin: 40px 0; }
        .login-btn { padding: 15px 30px; border-radius: 30px; text-decoration: none; font-weight: bold;
                     transition: transform 0.3s, box-shadow 0.3s; display: inline-block; }
        .login-btn:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .google { background: #fff; color: #333; }
        .apple { background: #000; color: #fff; }
        .line { background: #00C300; color: #fff; }
        .facebook { background: #1877F2; color: #fff; }
        .telegram { background: #0088cc; color: #fff; }
        .github { background: #333; color: #fff; }
        .wechat { background: #07C160; color: #fff; }
        .instagram { background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888); color: #fff; }
        .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 30px; margin-top: 60px; }
        .feature { background: rgba(255,255,255,0.05); padding: 30px; border-radius: 20px; text-align: center; }
        .feature-icon { font-size: 48px; margin-bottom: 20px; }
        .feature h3 { font-size: 24px; margin-bottom: 15px; }
        .feature p { color: #aaa; }
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>🚀 翔川 Lewis AI</h1>
            <p class="subtitle">連接靈感與未來 | AI × 命理 × 創作 × DevOps</p>
            <p>登入開始你的 AI 創業之旅</p>
        </div>
        
        <div class="login-methods">
            <a href="/login/google" class="login-btn google">🔵 Google 登入</a>
            <a href="/login/apple" class="login-btn apple">🍎 Apple 登入</a>
            <a href="/login/line" class="login-btn line">💚 LINE 登入</a>
            <a href="/login/facebook" class="login-btn facebook">🔵 Facebook 登入</a>
            <a href="/login/telegram" class="login-btn telegram">✈️ Telegram 登入</a>
            <a href="/login/github" class="login-btn github">🐙 GitHub 登入</a>
            <a href="/login/wechat" class="login-btn wechat">💚 WeChat 登入</a>
            <a href="/login/instagram" class="login-btn instagram">📸 Instagram 登入</a>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">🤖</div>
                <h3>AI 工具</h3>
                <p>Telegram Bot / 自動化 / AI 助理</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🪐</div>
                <h3>命理系統</h3>
                <p>八字 / 五行 / 星座 / 命名分析</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🎵</div>
                <h3>AI 音樂</h3>
                <p>AI 音樂生成 / 影片剪輯</p>
            </div>
            <div class="feature">
                <div class="feature-icon">☁️</div>
                <h3>DevOps/SRE</h3>
                <p>監控 / CI/CD / K8s / 自動化</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🤝</div>
                <h3>代理推廣</h3>
                <p>多級分銷 / 自動結算 / 佣金系統</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🌐</div>
                <h3>多平台</h3>
                <p>Discord / LinkedIn / TikTok / Threads</p>
            </div>
        </div>
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>儀表板 - 翔川 Lewis AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f6fa; }
        .nav { background: #2c3e50; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
        .nav-brand { color: white; font-size: 24px; font-weight: bold; }
        .nav-links a { color: white; text-decoration: none; margin-left: 20px; }
        .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
        .card { background: white; padding: 30px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .user-info { display: flex; align-items: center; gap: 20px; }
        .avatar { width: 80px; height: 80px; border-radius: 50%; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 30px; }
        .stat { background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; }
        .stat-num { font-size: 32px; font-weight: bold; color: #3498db; }
        .stat-label { color: #666; margin-top: 5px; }
        .menu { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 30px; }
        .menu-item { background: #3498db; color: white; padding: 30px; border-radius: 15px; text-align: center; text-decoration: none; font-size: 18px; transition: transform 0.3s; }
        .menu-item:hover { transform: translateY(-5px); }
    </style>
</head>
<body>
    <div class="nav">
        <div class="nav-brand">🚀 翔川 Lewis AI</div>
        <div class="nav-links">
            <a href="/dashboard">儀表板</a>
            <a href="/fortune">命理</a>
            <a href="/music">音樂</a>
            <a href="/devops">DevOps</a>
            <a href="/logout">登出</a>
        </div>
    </div>
    <div class="container">
        <div class="card">
            <div class="user-info">
                <img src="{{ user.avatar }}" alt="avatar" class="avatar">
                <div>
                    <h2>歡迎回來，{{ user.username }}！</h2>
                    <p>註冊方式：{{ user.provider }} | 加入時間：{{ user.created_at.strftime('%Y-%m-%d') }}</p>
                </div>
            </div>
            <div class="stats">
                <div class="stat"><div class="stat-num">0</div><div class="stat-label">命理分析</div></div>
                <div class="stat"><div class="stat-num">0</div><div class="stat-label">AI 音樂</div></div>
                <div class="stat"><div class="stat-num">0</div><div class="stat-label">代理推薦</div></div>
                <div class="stat"><div class="stat-num">0</div><div class="stat-label">收益</div></div>
            </div>
        </div>
        <div class="menu">
            <a href="/fortune" class="menu-item">🪐 命理分析</a>
            <a href="/music" class="menu-item">🎵 AI 音樂</a>
            <a href="/devops" class="menu-item">☁️ DevOps 工具</a>
            <a href="#" class="menu-item">🤝 代理中心</a>
            <a href="#" class="menu-item">📊 數據分析</a>
            <a href="#" class="menu-item">⚙️ 設定</a>
        </div>
    </div>
</body>
</html>
'''

FORTUNE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>命理分析 - 翔川 Lewis AI</title>
    <style>
        body { font-family: sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); min-height: 100vh; padding: 40px 20px; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 20px; }
        h1 { color: #2c3e50; text-align: center; }
        form { margin-top: 30px; }
        input { width: 100%; padding: 15px; margin: 10px 0; border: 2px solid #ddd; border-radius: 10px; font-size: 16px; }
        button { width: 100%; padding: 15px; background: #3498db; color: white; border: none; border-radius: 10px; font-size: 18px; cursor: pointer; }
        button:hover { background: #2980b9; }
        .result { margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 15px; }
        .result-item { margin: 15px 0; font-size: 18px; }
        .result-label { font-weight: bold; color: #2c3e50; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🪐 命理分析系統</h1>
        <form method="POST">
            <label>輸入你的出生日期：</label>
            <input type="date" name="birth_date" required>
            <button type="submit">開始分析</button>
        </form>
        {% if result %}
        <div class="result">
            <h2>🎯 分析結果</h2>
            <div class="result-item"><span class="result-label">星座：</span>{{ result.zodiac }}</div>
            <div class="result-item"><span class="result-label">生肖：</span>{{ result.chinese_zodiac }}</div>
            <div class="result-item"><span class="result-label">五行：</span>{{ result.five_element }}</div>
            <div class="result-item"><span class="result-label">解說：</span>{{ result.message }}</div>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

MUSIC_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 音樂 - 翔川 Lewis AI</title>
    <style>
        body { font-family: sans-serif; background: linear-gradient(135deg, #00d4ff, #00ff88); min-height: 100vh; padding: 40px 20px; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 20px; }
        h1 { color: #2c3e50; text-align: center; }
        form { margin-top: 30px; }
        textarea { width: 100%; padding: 15px; margin: 10px 0; border: 2px solid #ddd; border-radius: 10px; font-size: 16px; min-height: 100px; }
        select { width: 100%; padding: 15px; margin: 10px 0; border: 2px solid #ddd; border-radius: 10px; font-size: 16px; }
        button { width: 100%; padding: 15px; background: #27ae60; color: white; border: none; border-radius: 10px; font-size: 18px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 AI 音樂生成</h1>
        <form method="POST">
            <label>輸入你的音樂描述：</label>
            <textarea name="prompt" placeholder="例如：放鬆的鋼琴曲，適合冥想..." required></textarea>
            <label>選擇風格：</label>
            <select name="style">
                <option value="pop">流行</option>
                <option value="classical">古典</option>
                <option value="jazz">爵士</option>
                <option value="electronic">電子</option>
                <option value="rock">搖滾</option>
            </select>
            <button type="submit">生成音樂</button>
        </form>
        {% if result %}
        <div class="result" style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 15px;">
            <h2>✅ 生成完成</h2>
            <p>風格：{{ result.style }}</p>
            <p>描述：{{ result.prompt }}</p>
            <p>音樂檔：{{ result.result_url }}</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

DEVOPS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DevOps/SRE 工具 - 翔川 Lewis AI</title>
    <style>
        body { font-family: sans-serif; background: #1a1a2e; color: white; min-height: 100vh; padding: 40px 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; font-size: 36px; margin-bottom: 40px; }
        .tools { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .tool { background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; text-align: center; }
        .tool-icon { font-size: 48px; }
        .tool h3 { margin: 15px 0; }
        .tool p { color: #aaa; }
        .btn { display: inline-block; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 20px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>☁️ DevOps / SRE 工具中心</h1>
        <div class="tools">
            <div class="tool">
                <div class="tool-icon">📊</div>
                <h3>監控面板</h3>
                <p>Zabbix / Prometheus / Grafana</p>
                <a href="#" class="btn">開啟</a>
            </div>
            <div class="tool">
                <div class="tool-icon">🔄</div>
                <h3>CI/CD</h3>
                <p>Jenkins / GitLab CI / GitHub Actions</p>
                <a href="#" class="btn">開啟</a>
            </div>
            <div class="tool">
                <div class="tool-icon">☸️</div>
                <h3>K8s 管理</h3>
                <p>Kubernetes / Helm / Dashboard</p>
                <a href="#" class="btn">開啟</a>
            </div>
            <div class="tool">
                <div class="tool-icon">📝</div>
                <h3>日誌分析</h3>
                <p>ELK / Graylog / Loki</p>
                <a href="#" class="btn">開啟</a>
            </div>
            <div class="tool">
                <div class="tool-icon">🛡️</div>
                <h3>安全掃描</h3>
                <p>SonarQube / Trivy / OWASP</p>
                <a href="#" class="btn">開啟</a>
            </div>
            <div class="tool">
                <div class="tool-icon">🤖</div>
                <h3>自動化腳本</h3>
                <p>Ansible / Terraform / Shell</p>
                <a href="#" class="btn">開啟</a>
            </div>
        </div>
    </div>
</body>
</html>
'''

# ==================== 啟動 ====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("🚀 翔川 Lewis AI 系統啟動中...")
    print("📍 訪問 http://10.1.0.226:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)