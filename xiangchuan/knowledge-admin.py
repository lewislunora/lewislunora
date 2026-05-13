#!/usr/bin/env python3
"""
知识库管理 Web 后台
功能：查看、添加、编辑、删除知识库条目
"""
import os
import json
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

KNOWLEDGE_BASE_FILE = '/data/knowledge_base.json'

def load_knowledge_base():
    try:
        with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_knowledge_base(data):
    with open(KNOWLEDGE_BASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知識庫管理後台 - aingel_bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-primary { background: #007bff; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-success { background: #28a745; color: white; }
        table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal.show { display: flex; align-items: center; justify-content: center; }
        .modal-content { background: white; padding: 20px; border-radius: 8px; width: 90%; max-width: 600px; max-height: 80vh; overflow-y: auto; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 600; }
        input, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        textarea { min-height: 100px; }
        .keywords { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
        .keyword-tag { background: #e9ecef; padding: 2px 8px; border-radius: 12px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 知識庫管理後台</h1>
        <button class="btn btn-success" onclick="openModal()">+ 新增條目</button>
        <table style="margin-top: 20px;">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>問題</th>
                    <th>關鍵詞</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                {% for item in items %}
                <tr>
                    <td>{{ item.id }}</td>
                    <td>{{ item.question }}</td>
                    <td>
                        <div class="keywords">
                            {% for kw in item.keywords %}
                            <span class="keyword-tag">{{ kw }}</span>
                            {% endfor %}
                        </div>
                    </td>
                    <td>
                        <button class="btn btn-primary" onclick="editItem({{ item.id }})">編輯</button>
                        <button class="btn btn-danger" onclick="deleteItem({{ item.id }})">刪除</button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div id="modal" class="modal">
        <div class="modal-content">
            <h2 id="modal-title">新增條目</h2>
            <form id="item-form" onsubmit="saveItem(event)">
                <input type="hidden" id="item-id">
                <div class="form-group">
                    <label>問題：</label>
                    <input type="text" id="item-question" required>
                </div>
                <div class="form-group">
                    <label>關鍵詞（用逗號分隔）：</label>
                    <input type="text" id="item-keywords" placeholder="充值,儲值,recharge">
                </div>
                <div class="form-group">
                    <label>回答：</label>
                    <textarea id="item-answer" required></textarea>
                </div>
                <div style="text-align: right; margin-top: 20px;">
                    <button type="button" class="btn" onclick="closeModal()">取消</button>
                    <button type="submit" class="btn btn-success">保存</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        const items = {{ items|tojson }};

        function openModal(id = null) {
            document.getElementById('modal').classList.add('show');
            if (id) {
                document.getElementById('modal-title').textContent = '編輯條目';
                const item = items.find(i => i.id === id);
                document.getElementById('item-id').value = item.id;
                document.getElementById('item-question').value = item.question;
                document.getElementById('item-keywords').value = item.keywords.join(', ');
                document.getElementById('item-answer').value = item.answer;
            } else {
                document.getElementById('modal-title').textContent = '新增條目';
                document.getElementById('item-form').reset();
            }
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('show');
        }

        function editItem(id) {
            openModal(id);
        }

        function deleteItem(id) {
            if (confirm('確定要刪除這個條目嗎？')) {
                fetch('/api/delete/' + id, { method: 'POST' })
                    .then(() => location.reload());
            }
        }

        function saveItem(event) {
            event.preventDefault();
            const id = document.getElementById('item-id').value;
            const data = {
                id: id ? parseInt(id) : Date.now(),
                question: document.getElementById('item-question').value,
                keywords: document.getElementById('item-keywords').value.split(',').map(k => k.trim()).filter(k => k),
                answer: document.getElementById('item-answer').value
            };

            fetch('/api/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(() => {
                location.reload();
            });
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    items = load_knowledge_base()
    return render_template_string(HTML_TEMPLATE, items=items)

@app.route('/api/save', methods=['POST'])
def save_item():
    data = request.json
    items = load_knowledge_base()
    
    existing = next((i for i in items if i['id'] == data['id']), None)
    if existing:
        existing.update(data)
    else:
        items.append(data)
    
    save_knowledge_base(items)
    return jsonify({'success': True})

@app.route('/api/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    items = load_knowledge_base()
    items = [i for i in items if i['id'] != item_id]
    save_knowledge_base(items)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
