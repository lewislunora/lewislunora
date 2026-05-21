/* ===== Auth Guard: protect content pages ===== */
(function() {
  const user = JSON.parse(localStorage.getItem('chat_user') || 'null');
  if (user) return;

  const style = document.createElement('style');
  style.textContent = `
    .auth-overlay {
      position: fixed; inset: 0; z-index: 99999;
      background: #0a0e27; display: flex;
      align-items: center; justify-content: center;
    }
    .auth-box { text-align: center; padding: 2rem; }
    .auth-box h2 { font-size: 1.8rem; margin-bottom: 0.5rem; }
    .auth-box p { color: rgba(255,255,255,0.5); margin-bottom: 1.5rem; }
    .auth-box .btn-primary {
      display: inline-block; padding: 0.8rem 2rem; border-radius: 12px;
      background: linear-gradient(135deg, #00d4ff, #7b68ee);
      color: #fff; font-weight: 600; text-decoration: none; cursor: pointer; border: none; font-size: 1rem;
      transition: transform 0.2s;
    }
    .auth-box .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,212,255,0.3); }
    .auth-input {
      display: block; width: 280px; margin: 0.5rem auto; padding: 0.7rem 1rem;
      border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.05); color: #fff; font-size: 0.9rem; outline: none;
    }
    .auth-input:focus { border-color: rgba(0,212,255,0.4); }
  `;
  document.head.appendChild(style);

  var html = '<div class="auth-overlay"><div class="auth-box">';
  html += '<div style="font-size:3rem;margin-bottom:1rem">&#x1f512;</div>';
  html += '<h2>\u8acb\u5148\u8a3b\u518a/\u767b\u5165</h2>';
  html += '<p>\u8a3b\u518c\u5f8c\u5373\u53ef\u700f\u89bd\u5b8c\u6574\u5167\u5bb9</p>';
  html += '<input id="authName" class="auth-input" placeholder="\u8f38\u5165\u4f60\u7684\u540d\u7a31" autocomplete="name">';
  html += '<input id="authEmail" class="auth-input" placeholder="Email\uff08\u9078\u586b\uff09" autocomplete="email" style="margin-top:0.5rem">';
  html += '<button class="btn-primary" onclick="window.doAuthLogin()" style="margin-top:1rem">&#x2705; \u958b\u59cb\u4f7f\u7528</button>';
  html += '<p style="margin-top:1rem;font-size:0.8rem;color:rgba(255,255,255,0.3)">\u5df2\u6709\u5e33\u865f\uff1f\u53ef\u76f4\u63a5\u767b\u5165</p>';
  html += '</div></div>';
  document.body.innerHTML = html;

  window.doAuthLogin = function() {
    var name = document.getElementById('authName').value.trim();
    if (!name) { alert('\u8acb\u8f38\u5165\u540d\u7a31'); return; }
    var user = { name: name, email: document.getElementById('authEmail').value.trim(), avatar: '', sub: 'local_' + Date.now(), provider: 'local' };
    localStorage.setItem('chat_user', JSON.stringify(user));
    location.reload();
  };
  document.addEventListener('DOMContentLoaded', function() {
    var el = document.getElementById('authName');
    if (el) el.addEventListener('keydown', function(e) { if (e.key === 'Enter') window.doAuthLogin(); });
    var el2 = document.getElementById('authEmail');
    if (el2) el2.addEventListener('keydown', function(e) { if (e.key === 'Enter') window.doAuthLogin(); });
  });
})();
