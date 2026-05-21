/* ===== User Management ===== */
const USER_KEY = 'chat_user';
let currentUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
let chatOpen = false;
let chatMessages = [];

/* ===== Google Sign-In ===== */
let GOOGLE_CLIENT_ID = localStorage.getItem('google_client_id') || '';

fetch('/api/config').then(r => r.json()).then(cfg => {
  if (cfg.google_client_id && !GOOGLE_CLIENT_ID) {
    GOOGLE_CLIENT_ID = cfg.google_client_id;
    localStorage.setItem('google_client_id', cfg.google_client_id);
    updateUI();
  }
}).catch(() => {});

function initGoogle(containerId) {
  if (!GOOGLE_CLIENT_ID || typeof google === 'undefined') return;
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: r => {
      const p = JSON.parse(atob(r.credential.split('.')[1]));
      setUser({ name: p.name, email: p.email, avatar: p.picture, sub: p.sub, provider: 'google' }, true);
    },
  });
  const btn = document.getElementById(containerId || 'gsi-button');
  if (btn) google.accounts.id.renderButton(btn, { type: 'standard', shape: 'pill', theme: 'outline', size: containerId === 'gsi-button-alt' ? 'large' : 'small', text: 'signin_with' });
}

/* ===== Local Login (stored in localStorage) ===== */
function getUsers() { return JSON.parse(localStorage.getItem('auth_users') || '{}'); }
function saveUsers(u) { localStorage.setItem('auth_users', JSON.stringify(u)); }

let _loginIsRegister = false;

function showLocalLogin() {
  const overlay = document.getElementById('loginOverlay');
  if (overlay) overlay.style.display = 'flex';
  _loginIsRegister = false;
  updateLoginModal();
}

function hideLocalLogin() {
  const overlay = document.getElementById('loginOverlay');
  if (overlay) overlay.style.display = 'none';
}

function switchTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`.auth-tab[data-tab="${tab}"]`)?.classList.add('active');
  document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
  const panel = document.getElementById('panel' + tab.charAt(0).toUpperCase() + tab.slice(1));
  if (panel) panel.classList.add('active');
  if (tab === 'google' && GOOGLE_CLIENT_ID && typeof google !== 'undefined') {
    const gBtn = document.getElementById('gsi-btn-modal');
    if (gBtn) google.accounts.id.renderButton(gBtn, { type: 'standard', shape: 'pill', theme: 'outline', size: 'large', text: 'signin_with' });
  }
}

function toggleAuthMode() {
  _loginIsRegister = !_loginIsRegister;
  updateLoginModal();
}

function updateLoginModal() {
  const btn = document.getElementById('authSubmitBtn');
  const toggle = document.getElementById('authToggle');
  const pass2 = document.getElementById('authPass2');
  if (btn) btn.textContent = _loginIsRegister ? '註冊' : '登入';
  if (toggle) toggle.textContent = _loginIsRegister ? '已有帳號？點此登入' : '沒有帳號？點此註冊';
  if (pass2) pass2.style.display = _loginIsRegister ? 'block' : 'none';
  const err = document.getElementById('authError');
  if (err) err.style.display = 'none';
}

function doAuthAction() {
  const email = document.getElementById('authEmail').value.trim();
  const pass = document.getElementById('authPass').value;
  const errEl = document.getElementById('authError');
  errEl.style.display = 'none';
  if (!email || !pass) { errEl.textContent = '請填寫 Email 和密碼'; errEl.style.display = 'block'; return; }
  if (_loginIsRegister) {
    const pass2 = document.getElementById('authPass2').value;
    if (pass !== pass2) { errEl.textContent = '兩次密碼不一致'; errEl.style.display = 'block'; return; }
    if (pass.length < 4) { errEl.textContent = '密碼至少 4 個字元'; errEl.style.display = 'block'; return; }
    const users = getUsers();
    if (users[email]) { errEl.textContent = '此 Email 已經註冊過'; errEl.style.display = 'block'; return; }
    users[email] = { password: pass, created: Date.now() };
    saveUsers(users);
    setUser({ name: email.split('@')[0], email, avatar: '', sub: 'local_' + Date.now(), provider: 'local' }, true);
  } else {
    const users = getUsers();
    if (!users[email] || users[email].password !== pass) {
      errEl.textContent = 'Email 或密碼錯誤'; errEl.style.display = 'block'; return;
    }
    setUser({ name: email.split('@')[0], email, avatar: '', sub: 'local_' + Date.now(), provider: 'local' }, true);
  }
}

/* ===== User State ===== */
function setUser(user, closeModal) {
  currentUser = user;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  updateUI();
  if (typeof onUserLogin === 'function') onUserLogin(user);
  if (closeModal) hideLocalLogin();
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
      if (GOOGLE_CLIENT_ID) initGoogle('gsi-button');
    }
  }
  renderChat();
}

function showUserMenu() {}

/* ===== Login Overlay HTML ===== */
if (!document.getElementById('loginOverlay')) {
  const div = document.createElement('div');
  div.id = 'loginOverlay';
  div.innerHTML = `
    <div class="login-modal" style="width:380px">
      <button class="login-close" onclick="hideLocalLogin()">✕</button>
      <h3>🔑 註冊 / 登入</h3>
      <div class="auth-tabs" style="display:flex;gap:0;margin:1rem 0;border-bottom:1px solid rgba(255,255,255,0.1)">
        <div class="auth-tab active" data-tab="account" onclick="switchTab('account')" style="flex:1;padding:0.6rem 0;text-align:center;font-size:0.85rem;cursor:pointer;color:rgba(255,255,255,0.4);border-bottom:2px solid transparent">帳號密碼</div>
        <div class="auth-tab" data-tab="google" onclick="switchTab('google')" style="flex:1;padding:0.6rem 0;text-align:center;font-size:0.85rem;cursor:pointer;color:rgba(255,255,255,0.4);border-bottom:2px solid transparent">Google</div>
        <div class="auth-tab" data-tab="wechat" onclick="switchTab('wechat')" style="flex:1;padding:0.6rem 0;text-align:center;font-size:0.85rem;cursor:pointer;color:rgba(255,255,255,0.4);border-bottom:2px solid transparent">微信</div>
      </div>
      <div class="auth-panel active" id="panelAccount">
        <div class="auth-error" id="authError" style="color:#ff6b6b;font-size:0.8rem;margin-bottom:0.5rem;display:none"></div>
        <input id="authEmail" class="login-input" type="email" placeholder="Email" autocomplete="email" onkeydown="if(event.key==='Enter')doAuthAction()">
        <input id="authPass" class="login-input" type="password" placeholder="密碼" autocomplete="current-password" style="margin-top:0.5rem" onkeydown="if(event.key==='Enter')doAuthAction()">
        <input id="authPass2" class="login-input" type="password" placeholder="確認密碼" autocomplete="new-password" style="margin-top:0.5rem;display:none" onkeydown="if(event.key==='Enter')doAuthAction()">
        <button class="btn-login-submit" id="authSubmitBtn" onclick="doAuthAction()">登入</button>
        <div class="auth-toggle" id="authToggle" onclick="toggleAuthMode()" style="text-align:center;font-size:0.8rem;color:rgba(255,255,255,0.4);margin-top:0.8rem;cursor:pointer">沒有帳號？點此註冊</div>
      </div>
      <div class="auth-panel" id="panelGoogle">
        <div id="gsi-btn-modal" style="display:flex;justify-content:center;margin:1rem 0"></div>
        <p style="text-align:center;font-size:0.8rem;color:rgba(255,255,255,0.3)">使用 Google 帳戶即可登入</p>
      </div>
      <div class="auth-panel" id="panelWeChat">
        <div style="width:180px;height:180px;margin:1rem auto;border-radius:8px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);text-align:center;line-height:180px;font-size:0.8rem;color:rgba(255,255,255,0.3)">微信授權中...</div>
        <p style="text-align:center;font-size:0.85rem;color:rgba(255,255,255,0.5)">請使用微信掃描上方 QR Code 登入</p>
        <p style="text-align:center;font-size:0.75rem;color:rgba(255,255,255,0.3);margin-top:0.5rem">暫時使用帳號密碼或 Google 登入</p>
      </div>
    </div>`;
  div.style.cssText = 'display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.6);align-items:center;justify-content:center;backdrop-filter:blur(4px)';
  document.body.appendChild(div);
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
