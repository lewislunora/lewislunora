/* ===== Google Sign-In ===== */
const GOOGLE_CLIENT_ID = localStorage.getItem('google_client_id') || '';
const USER_KEY = 'chat_user';

let currentUser = null;

function initGoogleSignIn() {
  if (!GOOGLE_CLIENT_ID) return;
  if (typeof google === 'undefined' || !google.accounts) return;
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleCredential,
  });
  const btn = document.getElementById('gsi-button');
  if (btn) google.accounts.id.renderButton(btn, { type: 'standard', shape: 'pill', theme: 'outline', size: 'small', text: 'signin_with' });
}

function handleGoogleCredential(resp) {
  const payload = JSON.parse(atob(resp.credential.split('.')[1]));
  currentUser = {
    name: payload.name,
    email: payload.email,
    avatar: payload.picture,
    sub: payload.sub,
  };
  localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
  updateUserUI();
  if (typeof onUserLogin === 'function') onUserLogin(currentUser);
}

function signOut() {
  currentUser = null;
  localStorage.removeItem(USER_KEY);
  updateUserUI();
  if (typeof onUserLogout === 'function') onUserLogout();
}

function updateUserUI() {
  const container = document.getElementById('gsi-user-area');
  if (!container) return;
  const saved = currentUser || JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  if (saved) {
    container.innerHTML = `
      <div class="gsi-user" onclick="showUserMenu()">
        <img class="gsi-avatar" src="${saved.avatar || ''}" alt="" onerror="this.style.display='none'">
        <span class="gsi-name">${saved.name || saved.email || ''}</span>
        <span class="gsi-logout" onclick="event.stopPropagation();signOut()" title="登出">✕</span>
      </div>`;
  } else {
    container.innerHTML = '<div id="gsi-button"></div>';
    if (GOOGLE_CLIENT_ID && typeof google !== 'undefined') initGoogleSignIn();
    else {
      container.innerHTML = '';
    }
  }
}

function showUserMenu() {
}

/* ===== WebChat Knowledge Base ===== */
const KB = [
  { kw: ['方案', '價格', '費用', '多少錢', 'pricing', 'plan', 'price', 'cost'], reply: '我們提供三種方案：\n\n① 入門版（免費）- 50次/天，10條知識庫\n② 專業版（NT$890/月）- 無限次數，500條KB，Groq\n③ 企業版（NT$5,990/月）- 私有部署，無限KB\n\n詳細：https://lewislunora.onrender.com/product/#pricing' },
  { kw: ['ai', '客服', '智能', 'customer service', 'support'], reply: 'AI 智能客服 24/7 自動回應，支援多語言。可串接 Telegram、LINE、Facebook。專業版 NT$890/月起。' },
  { kw: ['功能', 'feature', 'capability'], reply: '主要功能：\n• AI 智能客服（多平台）\n• 知識庫管理（Dashboard 編輯）\n• 內容自動生成（Groq LLM）\n• 多平台排程發布\n• 數據分析\n• 自主訓練 Bot' },
  { kw: ['平台', 'platform', '支援', 'telegram', 'line', 'facebook'], reply: '支援平台：Telegram（@ailunora_bot）、LINE、Facebook、Instagram。行銷自動化排程發布。' },
  { kw: ['開始', '怎麼用', '如何', 'trial', 'start', 'signup'], reply: '點擊「📩 免費諮詢」預約，或直接加 @ailunora_bot 測試 AI 客服。我們會協助你完成設定。' },
  { kw: ['line', '串接', 'connect'], reply: 'LINE 串接需提供 Channel Access Token。專業版以上方案支援。預約諮詢可協助設定。' },
  { kw: ['dashboard', '後台', '管理'], reply: '行銷自動化 Dashboard 包含：內容管理、排程發布、知識庫編輯、AI 生成、數據分析。網址：https://lewislunora.onrender.com/dashboard' },
  { kw: ['隱私', 'privacy', '資料'], reply: '我們重視你的資料安全。詳見隱私政策：https://lewislunora.github.io/lewislunora/privacy.html' },
  { kw: ['hello', 'hi', '嗨', '你好', '早安', '午安', '晚安', '哈囉'], reply: '嗨！👋 我是 @ailunora_bot 的 AI 客服。\n\n你可以問我：\n• 方案與價格\n• 功能介紹\n• 平台支援\n• 如何開始\n• 其他行銷相關問題' },
];

function getKBReply(text) {
  const t = text.toLowerCase();
  for (const entry of KB) {
    for (const kw of entry.kw) {
      if (t.includes(kw)) return entry.reply;
    }
  }
  return null;
}

async function fetchBackendReply(text) {
  const api = location.hostname.includes('onrender.com') ? '/api/kb/query' : 'https://lewislunora.onrender.com/api/kb/query';
  try {
    const res = await fetch(api, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return null;
    const json = await res.json();
    return json.reply || null;
  } catch { return null; }
}

/* ===== WebChat Widget ===== */
let chatOpen = false;
let chatMessages = [];

function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chatPanel').classList.toggle('open', chatOpen);
  if (chatOpen) {
    document.querySelector('.chat-bubble').classList.remove('has-unread');
    renderChat();
  }
}

function sendChat(text) {
  if (!text || !text.trim()) return;
  const user = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  if (!user) return;

  addChatMsg('user', text.trim());
  document.getElementById('chatInput').value = '';

  const q = text.trim();
  const local = getKBReply(q);
  if (local) {
    setTimeout(() => addChatMsg('bot', local), 300 + Math.random() * 400);
  } else {
    fetchBackendReply(q).then(reply => {
      if (reply) addChatMsg('bot', reply);
      else addChatMsg('bot', '抱歉，這個問題我還不太會回答。你可以試試：方案、價格、功能、平台、如何開始');
    });
  }
}

function addChatMsg(role, text) {
  const now = new Date();
  const time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
  chatMessages.push({ role, text, time });
  renderChat();
  const container = document.getElementById('chatMessages');
  if (container) container.scrollTop = container.scrollHeight;
}

function renderChat() {
  const container = document.getElementById('chatMessages');
  const prompt = document.getElementById('chatLoginPrompt');
  const inputArea = document.querySelector('.chat-input-area');
  const suggestions = document.getElementById('chatSuggestions');
  const user = JSON.parse(localStorage.getItem(USER_KEY) || 'null');

  if (!user) {
    if (container) container.style.display = 'none';
    if (prompt) prompt.style.display = 'flex';
    if (inputArea) inputArea.style.display = 'none';
    if (suggestions) suggestions.style.display = 'none';
    return;
  }

  if (container) container.style.display = 'flex';
  if (prompt) prompt.style.display = 'none';
  if (inputArea) inputArea.style.display = 'flex';
  if (suggestions) suggestions.style.display = 'flex';

  if (!container) return;
  container.innerHTML = chatMessages.map(m => `
    <div class="chat-msg ${m.role}">
      ${m.text.replace(/\n/g, '<br>')}
      <div class="msg-time">${m.time}</div>
    </div>`).join('');
}

function suggestClick(text) {
  const user = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  if (!user) return;
  sendChat(text);
}

function chatKeydown(e) {
  if (e.key === 'Enter') {
    const input = document.getElementById('chatInput');
    sendChat(input.value);
  }
}

function onUserLogin(user) {
  if (chatOpen) renderChat();
  addChatMsg('bot', '✅ 已登入！有什麼問題想問？');
}

function onUserLogout() {
  chatMessages = [];
  if (chatOpen) renderChat();
}

/* ===== Init ===== */
document.addEventListener('DOMContentLoaded', () => {
  updateUserUI();
  const saved = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  if (saved) currentUser = saved;
});
