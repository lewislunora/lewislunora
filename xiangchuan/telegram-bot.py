#!/usr/bin/env python3
"""
AI 虛擬推廣行銷助手 - Telegram Bot 後端 (升級版)
功能：LLM驅動、上下文記憶、知識庫檢索、多語言、人性化回覆、知識自增長
使用 Webhook 模式
"""

import os
import json
import time
import re
import requests
from flask import Flask, request, jsonify
from difflib import get_close_matches

app = Flask(__name__)

# Telegram Bot Token（必须设置环境变量）
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
if not TELEGRAM_TOKEN:
    print('錯誤：未设置 TELEGRAM_TOKEN 环境变量！', flush=True)
    exit(1)
TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# 用戶上下文記憶存儲 (保留最近10輪對話)
USER_HISTORY_FILE = 'user_history.json'
user_history = {}

# 知識庫
KNOWLEDGE_BASE_FILE = 'knowledge_base.json'
knowledge_base = []

# 等待反饋的狀態 {chat_id: {user_message, bot_reply, timestamp}}
pending_feedback = {}

# 系統提示
SYSTEM_PROMPT = """你是 翔川 Neo｜曜科技 |Ai_bot，一個人性化的AI客服與行銷助手。

業務規則：
- 提現審核：1-3個工作日，耐心等待
- 客服時間：9:00-24:00
- 充值教程：https://gfg-official.com/recharge 滿100減20
- 支持語言：繁體中文、簡體中文、英文，自動識別用戶語言

人性化的特點：
- 回覆自然口語化，適當使用表情符號
- 記住對話上下文，不重複提問
- 主動關心用戶需求，提供具體幫助

歷史對話示例：
用戶: 你好、充值、今天天氣怎麼樣
助手: 充值教程：https://gfg-official.com/recharge 滿100減20！💰 天氣查詢我暫時不支持哦～有其他需要幫忙的嗎？

用戶: 客服
助手: 需要客服幫助嗎？工作時間9:00-24:00，隨時為你服務～
"""

def load_knowledge_base():
    """載入知識庫"""
    global knowledge_base
    try:
        with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
            knowledge_base = json.load(f)
        print(f'已載入 {len(knowledge_base)} 條知識庫數據', flush=True)
    except Exception as e:
        print(f'載入知識庫失敗: {e}', flush=True)
        knowledge_base = []

def save_knowledge_base():
    """保存知識庫"""
    try:
        with open(KNOWLEDGE_BASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
        print(f'知識庫已保存，共 {len(knowledge_base)} 條', flush=True)
    except Exception as e:
        print(f'保存知識庫失敗: {e}', flush=True)

def extract_keywords(text, max_keywords=5):
    """從文本中提取關鍵詞（簡單實現）"""
    # 移除標點符號和常見詞
    stop_words = {'的', '是', '了', '在', '有', '和', '與', '或', '對', '就', '都', '而', '及', '等', '這', '那', '你', '我', '他', '她', '它', '們', '什麼', '怎麼', '嗎', '啊', '哦', '呢', '吧', '啦', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might'}
    
    # 簡單分詞（按空格和標點分割）
    words = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
    # 過濾停用詞和短詞
    keywords = [w for w in words if len(w) > 1 and w not in stop_words]
    # 返回前 N 個
    return list(dict.fromkeys(keywords[:max_keywords]))  # 去重保留順序

def add_to_knowledge_base(question, answer, keywords=None):
    """添加新條目到知識庫"""
    if keywords is None:
        keywords = extract_keywords(question + ' ' + answer)
    
    new_id = max([item['id'] for item in knowledge_base], default=0) + 1
    new_item = {
        'id': new_id,
        'keywords': keywords,
        'question': question[:100],  # 限制長度
        'answer': answer
    }
    knowledge_base.append(new_item)
    save_knowledge_base()
    return new_id

def search_knowledge_base(query, threshold=0.6):
    """搜尋知識庫，返回最相關的條目"""
    query_lower = query.lower()
    results = []
    
    for item in knowledge_base:
        keyword_match = any(keyword.lower() in query_lower for keyword in item.get('keywords', []))
        if keyword_match:
            results.append(item)
    
    return results[:3]

def load_user_history():
    """載入用戶歷史對話"""
    global user_history
    try:
        with open(USER_HISTORY_FILE, 'r', encoding='utf-8') as f:
            user_history = json.load(f)
    except Exception as e:
        print(f'載入歷史失敗: {e}', flush=True)
        user_history = {}

def save_user_history():
    """保存用戶歷史對話"""
    try:
        with open(USER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'保存歷史失敗: {e}', flush=True)

def detect_language(text):
    """檢測用戶語言"""
    simplified_chars = set('这们为发会时过对开说现进关点动体问实工业电计节术认')
    english_words = set(text.lower().split())
    common_english = {'hello', 'hi', 'how', 'are', 'you', 'what', 'the', 'is', 'a', 'an'}
    
    if any(char in text for char in simplified_chars):
        return 'zh-CN'
    elif len(english_words & common_english) > 0:
        return 'en'
    else:
        return 'zh-TW'

def get_llm_response(user_id, user_message):
    """LLM回覆生成"""
    kb_results = search_knowledge_base(user_message)
    kb_text = ""
    if kb_results:
        kb_text = "\n\n相關知識庫內容：\n"
        for item in kb_results:
            kb_text += f"Q: {item['question']}\nA: {item['answer']}\n"
    
    history = user_history.get(str(user_id), [])
    language = detect_language(user_message)
    
    context = ""
    for item in history[-5:]:
        context += f"用戶: {item['user']}\n助手: {item['bot']}\n"
    
    try:
        if GROQ_API_KEY:
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': 'llama3-8b-8192',
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT + kb_text},
                    {'role': 'user', 'content': f'歷史對話:\n{context}\n用戶: {user_message}'}
                ],
                'max_tokens': 300,
                'temperature': 0.7
            }
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=15
            )
            if response.ok:
                reply = response.json()['choices'][0]['message']['content'].strip()
                return reply
    except Exception as e:
        print(f'LLM調用失敗: {e}', flush=True)
    
    if kb_results:
        return kb_results[0]['answer']
    
    return get_local_response(user_message, language)

def get_local_response(message, language='zh-TW'):
    """本地規則回覆"""
    text = message.lower()
    
    if any(word in text for word in ['充值', 'recharge', '儲值']):
        return '充值教程：https://gfg-official.com/recharge 满100减20！💰'
    
    if any(word in text for word in ['提现', '出金', 'withdraw']):
        return '提现审核一般1-3个工作日，耐心等待一下哦～💸'
    
    if any(word in text for word in ['客服', '帮助', 'help', 'support']):
        return '需要客服幫助嗎？工作時間9:00-24:00，隨時為你服務～'
    
    if any(word in text for word in ['你好', 'hi', 'hello', '嗨']):
        if language == 'en':
            return 'Hello! I\'m 翔川 Neo｜曜科技 |Ai_bot 🤖 How can I help you today?'
        elif language == 'zh-CN':
            return '你好！我是 翔川 Neo｜曜科技 |Ai_bot 🤖 有什么可以帮你的吗？'
        else:
            return '你好！我是 翔川 Neo｜曜科技 |Ai_bot 🤖 有什麼可以幫你的嗎？'
    
    if any(word in text for word in ['天气', 'weather']):
        return '天氣查詢我暫時不支持哦～有其他需要幫忙的嗎？'
    
    if any(word in text for word in ['產品分析', '分析產品', '產品', 'product']):
        return '太好了！請告訴我：\n\n📦 產品名稱：？\n🎯 目標客群：？\n💰 價格區間：？\n✨ 產品特色：？\n\n我會為您生成完整的產品分析與行銷建議！'
    
    if any(word in text for word in ['文案', '推廣文案', '寫文案']):
        return '沒問題！請告訴我：\n\n1️⃣ 產品/服務類型\n2️⃣ 目標受眾\n3️⃣ 想強調的賣點\n4️⃣ 文案風格（溫馨/專業/活潑）\n\n我會為您量身打造吸引人的推廣文案！'
    
    if any(word in text for word in ['策略', '行銷策略', '制定策略']):
        return '為您制定行銷策略！請提供：\n\n🎯 行銷目標（品牌曝光/銷售/引流）\n💰 預算範圍\n⏰ 推廣時程\n📱 推廣渠道偏好\n\n我會為您規劃完整的行銷藍圖！'
    
    if language == 'en':
        return 'I understand your question! Let me help you with that. Is there anything specific you\'d like to know? 🤔'
    elif language == 'zh-CN':
        return '我明白您的问题！让我为您分析一下～\n\n有什么具体的需求可以告诉我哦！😊'
    else:
        return '我明白您的問題！讓我為您分析一下～\n\n有什麼具體的需求可以告訴我哦！😊'

def update_user_history(user_id, user_message, bot_reply):
    """更新用戶對話歷史"""
    user_id_str = str(user_id)
    if user_id_str not in user_history:
        user_history[user_id_str] = []
    
    user_history[user_id_str].append({
        'user': user_message,
        'bot': bot_reply,
        'timestamp': time.time()
    })
    
    if len(user_history[user_id_str]) > 10:
        user_history[user_id_str] = user_history[user_id_str][-10:]
    
    save_user_history()

def send_message(chat_id, text, reply_markup=None):
    """發送消息到 Telegram"""
    url = f'{TELEGRAM_API}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f'發送消息失敗: {e}', flush=True)
        return None

def send_feedback_request(chat_id, user_message, bot_reply):
    """發送回饋請求（詢問回答是否有用）"""
    # 保存等待反饋的狀態
    pending_feedback[str(chat_id)] = {
        'user_message': user_message,
        'bot_reply': bot_reply,
        'timestamp': time.time()
    }
    
    # 創建內聯鍵盤（👍 有用 / 👎 沒用）
    reply_markup = {
        'inline_keyboard': [[
            {'text': '👍 有用', 'callback_data': 'feedback_useful'},
            {'text': '👎 沒用', 'callback_data': 'feedback_useless'}
        ]]
    }
    
    send_message(
        chat_id,
        '這個回答對您有幫助嗎？',
        reply_markup=reply_markup
    )

def handle_callback_query(callback_query):
    """處理回調查詢（按鈕點擊）"""
    query_id = callback_query['id']
    chat_id = callback_query['message']['chat']['id']
    data = callback_query['data']
    
    # 回應回調（移除按鈕）
    requests.post(
        f'{TELEGRAM_API}/answerCallbackQuery',
        json={'callback_query_id': query_id, 'text': '謝謝您的反饋！'}
    )
    
    # 處理反饋
    if data == 'feedback_useful':
        if str(chat_id) in pending_feedback:
            info = pending_feedback.pop(str(chat_id))
            # 保存到知識庫
            new_id = add_to_knowledge_base(
                info['user_message'],
                info['bot_reply']
            )
            send_message(chat_id, f'✅ 已保存到知識庫！（ID: {new_id}）')
    
    elif data == 'feedback_useless':
        if str(chat_id) in pending_feedback:
            pending_feedback.pop(str(chat_id))
            send_message(chat_id, '👌 沒關係，我會繼續改進！')

@app.route('/')
def index():
    """健康檢查"""
    return jsonify({
        'status': 'running',
        'service': 'AI 虛擬推廣行銷助手 Telegram Bot (升級版)',
        'version': '2026.4',
        'mode': 'webhook',
        'features': ['LLM驅動', '上下文記憶', '知識庫檢索', '多語言', '人性化回覆', '知識自增長']
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """處理 Telegram webhook 更新"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'no data'})
        
        # 處理回調查詢（按鈕）
        if 'callback_query' in data:
            handle_callback_query(data['callback_query'])
            return jsonify({'status': 'ok'})
        
        if 'message' not in data:
            return jsonify({'status': 'not a message'})
        
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        
        if not text:
            return jsonify({'status': 'empty message'})
        
        # 處理 /save 指令（手動保存）
        if text.startswith('/save'):
            if str(chat_id) in pending_feedback:
                info = pending_feedback.pop(str(chat_id))
                new_id = add_to_knowledge_base(info['user_message'], info['bot_reply'])
                send_message(chat_id, f'✅ 已保存到知識庫！（ID: {new_id}）')
            else:
                send_message(chat_id, '目前沒有可保存的回答。請先問一個問題～')
            return jsonify({'status': 'ok'})
        
        # 處理 /start 指令
        if text == '/start':
            text = '你好'
        
        # 移除 @ 提及
        text_clean = text.replace('@ailunora_bot', '').replace('@翔川 Neo｜曜科技 |Ai_bot', '').strip()
        
        print(f'收到消息 [chat_id={chat_id}]: {text}', flush=True)
        
        # 生成回覆
        reply = get_llm_response(chat_id, text_clean)
        print(f'回覆: {reply[:50]}...', flush=True)
        
        # 發送回覆
        send_message(chat_id, reply)
        
        # 更新對話歷史
        update_user_history(chat_id, text_clean, reply)
        
        # 發送反饋請求（詢問是否有用）
        send_feedback_request(chat_id, text_clean, reply)
        
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        print(f'處理 webhook 錯誤: {e}', flush=True)
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    load_user_history()
    load_knowledge_base()
    
    print('=' * 60, flush=True)
    print('AI 虛擬推廣行銷助手 - Telegram Bot (升級版)', flush=True)
    print('=' * 60, flush=True)
    print('功能：LLM驅動、上下文記憶、知識庫檢索、多語言、知識自增長', flush=True)
    print('使用 Webhook 模式啟動 Bot...', flush=True)
    print(f'TELEGRAM_API: {TELEGRAM_API}', flush=True)
    print('Bot 已啟動！請在 Telegram 中搜索 @ailunora_bot 開始對話', flush=True)
    print('=' * 60, flush=True)
    
    app.run(host='0.0.0.0', port=5001, debug=False)
