/* ===== User Management ===== */
const USER_KEY = 'chat_user';
let currentUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
let chatOpen = false;
let chatMessages = [];

/* ===== Google Sign-In (optional, needs Client ID) ===== */
let GOOGLE_CLIENT_ID = localStorage.getItem('google_client_id') || '';

// Try fetching from backend config
fetch('/api/config').then(r => r.json()).then(cfg => {
  if (cfg.google_client_id && !GOOGLE_CLIENT_ID) {
    GOOGLE_CLIENT_ID = cfg.google_client_id;
    localStorage.setItem('google_client_id', cfg.google_client_id);
    updateUI();
  }
}).catch(() => {});

function initGoogle() {
  if (!GOOGLE_CLIENT_ID || typeof google === 'undefined') return;
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: r => {
      const p = JSON.parse(atob(r.credential.split('.')[1]));
      setUser({ name: p.name, email: p.email, avatar: p.picture, sub: p.sub, provider: 'google' });
    },
  });
  const btn = document.getElementById('gsi-button');
  if (btn) google.accounts.id.renderButton(btn, { type: 'standard', shape: 'pill', theme: 'outline', size: 'small', text: 'signin_with' });
}

/* ===== Local Login / Register ===== */
function showLocalLogin() {
  const overlay = document.getElementById('loginOverlay');
  if (overlay) overlay.style.display = 'flex';
}

function hideLocalLogin() {
  const overlay = document.getElementById('loginOverlay');
  if (overlay) overlay.style.display = 'none';
}

function doLocalLogin() {
  const name = document.getElementById('localName').value.trim();
  const email = document.getElementById('localEmail').value.trim();
  if (!name) { alert('請輸入名稱'); return; }
  setUser({ name, email: email || '', avatar: '', sub: 'local_' + Date.now(), provider: 'local' });
  hideLocalLogin();
}

function doLocalLoginKey(e) {
  if (e.key === 'Enter') doLocalLogin();
}

/* ===== User State ===== */
function setUser(user) {
  currentUser = user;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  updateUI();
  if (typeof onUserLogin === 'function') onUserLogin(user);
}

function signOut() {
  currentUser = null;
  localStorage.removeItem(USER_KEY);
  chatMessages = [];
  updateUI();
  if (typeof onUserLogout === 'function') onUserLogout();
}

/* ===== UI Update ===== */
function updateUI() {
  // Nav bar user area
  const area = document.getElementById('gsi-user-area');
  if (area) {
    if (currentUser) {
      const avatar = currentUser.avatar
        ? `<img class="gsi-avatar" src="${currentUser.avatar}" alt="" onerror="this.style.display='none'">`
        : '<span style="font-size:1.1rem">👤</span>';
      area.innerHTML = `
        <div class="gsi-user" onclick="showUserMenu()">
          ${avatar}
          <span class="gsi-name">${currentUser.name}</span>
          <span class="gsi-logout" onclick="event.stopPropagation();signOut()" title="登出">✕</span>
        </div>`;
    } else {
      area.innerHTML = `
        <div id="gsi-button" style="display:${GOOGLE_CLIENT_ID ? 'inline-block' : 'none'}"></div>
        <button class="btn-login-local" onclick="showLocalLogin()">🔑 註冊/登入</button>`;
      if (GOOGLE_CLIENT_ID) initGoogle();
    }
  }
  // Chat panel
  renderChat();
}

function showUserMenu() {}

/* ===== Login Overlay HTML (injected once) ===== */
if (!document.getElementById('loginOverlay')) {
  const div = document.createElement('div');
  div.id = 'loginOverlay';
  div.innerHTML = `
    <div class="login-modal">
      <button class="login-close" onclick="hideLocalLogin()">✕</button>
      <h3>🔑 註冊 / 登入</h3>
      <p style="color:rgba(255,255,255,0.5);font-size:0.85rem;margin-bottom:1.2rem">輸入名稱即可開始使用</p>
      <input id="localName" class="login-input" placeholder="你的名稱 *" onkeydown="doLocalLoginKey(event)" autocomplete="name">
      <input id="localEmail" class="login-input" placeholder="Email（選填）" onkeydown="doLocalLoginKey(event)" autocomplete="email" style="margin-top:0.5rem">
      <button class="btn-login-submit" onclick="doLocalLogin()">✅ 開始使用</button>
      <div id="gsi-button-alt" style="margin-top:0.8rem;display:${GOOGLE_CLIENT_ID ? 'flex' : 'none'};justify-content:center"></div>
    </div>`;
  div.style.cssText = 'display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.6);align-items:center;justify-content:center;backdrop-filter:blur(4px)';
  document.body.appendChild(div);
  if (GOOGLE_CLIENT_ID && typeof google !== 'undefined') {
    google.accounts.id.renderButton(document.getElementById('gsi-button-alt'), { type: 'standard', shape: 'pill', theme: 'outline', size: 'large', text: 'signin_with' });
  }
}

/* ===== Knowledge Base ===== */
const KB = [
  { kw: ['方案', '價格', '費用', '多少錢', 'pricing', 'plan', 'price', 'cost'], reply: '我們提供三種方案：\n\n① 入門版（免費）- 50次/天，10條知識庫\n② 專業版（NT$890/月）- 無限次數，500條KB，Groq\n③ 企業版（NT$5,990/月）- 私有部署，無限KB\n\n詳細：https://lewislunora.onrender.com/product/#pricing' },
  { kw: ['ai', '客服', '智能', 'customer service', 'support'], reply: 'AI 智能客服 24/7 自動回應，支援多語言。可串接 Telegram、LINE、Facebook。專業版 NT$890/月起。' },
  { kw: ['功能', 'feature', 'capability'], reply: '主要功能：\n• AI 智能客服（多平台）\n• 知識庫管理（Dashboard 編輯）\n• 內容自動生成（Groq LLM）\n• 多平台排程發布\n• 數據分析\n• 自主訓練 Bot' },
  { kw: ['平台', 'platform', '支援', 'telegram', 'line', 'facebook'], reply: '支援平台：Telegram（@ailunora_bot）、LINE、Facebook、Instagram。行銷自動化排程發布。' },
  { kw: ['開始', '怎麼用', '如何', 'trial', 'start', 'signup'], reply: '點擊「📩 免費諮詢」預約，或直接加 @ailunora_bot 測試 AI 客服。我們會協助你完成設定。' },
  { kw: ['line', '串接', 'connect'], reply: 'LINE 串接需提供 Channel Access Token。專業版以上方案支援。預約諮詢可協助設定。' },
  { kw: ['dashboard', '後台', '管理'], reply: '行銷自動化 Dashboard 包含：內容管理、排程發布、知識庫編輯、AI 生成、數據分析。網址：https://lewislunora.onrender.com/dashboard' },
  { kw: ['隱私', 'privacy', '資料'], reply: '我們重視你的資料安全。詳見隱私政策：https://lewislunora.github.io/lewislunora/privacy.html' },
  { kw: ['hello', 'hi', '嗨', '你好', '早安', '午安', '晚安', '哈囉', 'test', '測試'], reply: '嗨！👋 我是 @ailunora_bot 的 AI 客服。\n\n你可以問我：\n• 方案與價格\n• 功能介紹\n• 平台支援\n• 如何開始\n• 其他行銷相關問題' },
];

function getKBReply(text) {
  const t = text.toLowerCase();
  for (const entry of KB) {
    for (const kw of entry.kw) { if (t.includes(kw)) return entry.reply; }
  }
  return null;
}

async function fetchBackendReply(text) {
  const api = location.hostname.includes('onrender.com') ? '/api/kb/query' : 'https://lewislunora.onrender.com/api/kb/query';
  try {
    const res = await fetch(api, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
    if (!res.ok) return null;
    const j = await res.json();
    return j.reply || null;
  } catch { return null; }
}

/* ===== Chat Widget ===== */
function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chatPanel').classList.toggle('open', chatOpen);
  if (chatOpen) {
    document.querySelector('.chat-bubble')?.classList.remove('has-unread');
    renderChat();
  }
}

function sendChat(text) {
  if (!text || !text.trim() || !currentUser) return;
  addChatMsg('user', text.trim());
  document.getElementById('chatInput').value = '';
  const q = text.trim();
  const local = getKBReply(q);
  if (local) {
    setTimeout(() => addChatMsg('bot', local), 300 + Math.random() * 400);
  } else {
    fetchBackendReply(q).then(r => {
      addChatMsg('bot', r || '抱歉，這個問題我還不太會回答。你可以試試：方案、價格、功能、平台、如何開始');
    });
  }
}

function addChatMsg(role, text) {
  const now = new Date();
  const time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
  chatMessages.push({ role, text, time });
  renderChat();
  const c = document.getElementById('chatMessages');
  if (c) c.scrollTop = c.scrollHeight;
}

function renderChat() {
  const container = document.getElementById('chatMessages');
  const prompt = document.getElementById('chatLoginPrompt');
  const inputArea = document.querySelector('.chat-input-area');
  const suggestions = document.getElementById('chatSuggestions');
  if (!currentUser) {
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
  container.innerHTML = chatMessages.map(m =>
    `<div class="chat-msg ${m.role}">${m.text.replace(/\n/g, '<br>')}<div class="msg-time">${m.time}</div></div>`
  ).join('');
}

function suggestClick(text) { if (currentUser) sendChat(text); }
function chatKeydown(e) { if (e.key === 'Enter') sendChat(document.getElementById('chatInput').value); }
function onUserLogin(user) { if (chatOpen) renderChat(); addChatMsg('bot', '✅ 已登入！有什麼問題想問？'); }
function onUserLogout() { chatMessages = []; if (chatOpen) renderChat(); }

/* ===== Init ===== */
document.addEventListener('DOMContentLoaded', () => { updateUI(); });
