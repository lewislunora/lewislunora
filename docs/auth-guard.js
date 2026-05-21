/* ===== Auth Guard: protect content pages ===== */
(function() {
  var user = JSON.parse(localStorage.getItem('chat_user') || 'null');
  if (user) return;

  /* -- load Google GIS if needed -- */
  if (!document.querySelector('script[src*="accounts.google.com/gsi/client"]')) {
    var gs = document.createElement('script');
    gs.src = 'https://accounts.google.com/gsi/client';
    gs.async = true; gs.defer = true;
    document.head.appendChild(gs);
  }
  var GOOGLE_CLIENT_ID = '';

  /* -- users stored in localStorage -- */
  function getUsers() { return JSON.parse(localStorage.getItem('auth_users') || '{}'); }
  function saveUsers(u) { localStorage.setItem('auth_users', JSON.stringify(u)); }

  /* -- css -- */
  var style = document.createElement('style');
  style.textContent = '\
.auth-overlay{position:fixed;inset:0;z-index:99999;background:#0a0e27;display:flex;align-items:center;justify-content:center}\
.auth-box{background:#131837;border:1px solid rgba(255,255,255,0.12);border-radius:20px;padding:2rem;width:380px;max-width:92vw;position:relative;box-shadow:0 20px 60px rgba(0,0,0,0.5)}\
.auth-box h2{font-size:1.2rem;margin-bottom:0.3rem}\
.auth-tabs{display:flex;gap:0;margin:1rem 0;border-bottom:1px solid rgba(255,255,255,0.1)}\
.auth-tab{flex:1;padding:0.6rem 0;text-align:center;font-size:0.85rem;cursor:pointer;color:rgba(255,255,255,0.4);border-bottom:2px solid transparent;transition:all 0.2s}\
.auth-tab.active{color:#00d4ff;border-bottom-color:#00d4ff}\
.auth-tab:hover{color:rgba(255,255,255,0.7)}\
.auth-panel{display:none}\
.auth-panel.active{display:block}\
.auth-input{width:100%;padding:0.7rem 1rem;border-radius:10px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.05);color:#fff;font-size:0.9rem;outline:none;box-sizing:border-box;margin-bottom:0.6rem}\
.auth-input:focus{border-color:rgba(0,212,255,0.4)}\
.auth-input::placeholder{color:rgba(255,255,255,0.3)}\
.btn-primary{width:100%;padding:0.7rem;border-radius:10px;border:none;background:linear-gradient(135deg,#00d4ff,#7b68ee);color:#fff;font-weight:600;font-size:0.95rem;cursor:pointer;transition:all 0.2s}\
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 4px 15px rgba(0,212,255,0.3)}\
.btn-outline-auth{width:100%;padding:0.6rem;border-radius:10px;border:1px solid rgba(255,255,255,0.15);background:transparent;color:#fff;font-size:0.85rem;cursor:pointer;transition:all 0.2s;margin-top:0.4rem}\
.btn-outline-auth:hover{background:rgba(255,255,255,0.05)}\
.auth-divider{text-align:center;color:rgba(255,255,255,0.3);font-size:0.8rem;margin:0.8rem 0;position:relative}\
.auth-divider::before,.auth-divider::after{content:"";position:absolute;top:50%;width:35%;height:1px;background:rgba(255,255,255,0.1)}\
.auth-divider::before{left:0}\
.auth-divider::after{right:0}\
.auth-error{color:#ff6b6b;font-size:0.8rem;margin-bottom:0.5rem;display:none}\
.auth-toggle{text-align:center;font-size:0.8rem;color:rgba(255,255,255,0.4);margin-top:0.8rem;cursor:pointer}\
.auth-toggle:hover{color:#00d4ff}\
.wechat-qr{width:180px;height:180px;margin:1rem auto;display:block;border-radius:8px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);text-align:center;line-height:180px;font-size:0.8rem;color:rgba(255,255,255,0.3)}\
';
  document.head.appendChild(style);

  /* -- fetch google client id -- */
  fetch((location.hostname.includes('onrender.com')?'':'https://lewislunora.onrender.com')+'/api/config').then(function(r){return r.json()}).then(function(cfg){
    GOOGLE_CLIENT_ID = cfg.google_client_id||'';
    if(GOOGLE_CLIENT_ID && typeof google!=='undefined' && google.accounts){
      google.accounts.id.initialize({client_id:GOOGLE_CLIENT_ID,callback:onGoogleCredential});
      var gBtn=document.getElementById('gsi-btn'); if(gBtn) google.accounts.id.renderButton(gBtn,{type:'standard',shape:'pill',theme:'outline',size:'large',text:'signin_with'});
    }
  }).catch(function(){});

  function onGoogleCredential(r){
    var p = JSON.parse(atob(r.credential.split('.')[1]));
    doLogin({name:p.name,email:p.email,avatar:p.picture,sub:p.sub,provider:'google'});
  }

  function doLogin(u){
    localStorage.setItem('chat_user', JSON.stringify(u));
    if (typeof onUserLogin === 'function') onUserLogin(u);
    location.reload();
  }

  /* -- build UI -- */
  document.body.innerHTML = '\
<div class="auth-overlay">\
  <div class="auth-box">\
    <div style="text-align:center;margin-bottom:0.5rem;font-size:2.5rem">&#x1f512;</div>\
    <h2 style="text-align:center">\u8acb\u5148\u767b\u5165</h2>\
    <p style="text-align:center;color:rgba(255,255,255,0.5);font-size:0.85rem;margin-bottom:0.5rem">\u8a3b\u518a\u5e33\u865f\u5373\u53ef\u700f\u89bd\u5b8c\u6574\u5167\u5bb9</p>\
    <div class="auth-tabs" id="authTabs">\
      <div class="auth-tab active" data-tab="account">\u5e33\u865f\u5bc6\u78bc</div>\
      <div class="auth-tab" data-tab="google">Google</div>\
      <div class="auth-tab" data-tab="wechat">\u5fae\u4fe1</div>\
    </div>\
    <!-- Account panel -->\
    <div class="auth-panel active" id="panelAccount">\
      <div class="auth-error" id="authError"></div>\
      <input id="authEmail" class="auth-input" type="email" placeholder="Email" autocomplete="email">\
      <input id="authPass" class="auth-input" type="password" placeholder="\u5bc6\u78bc" autocomplete="current-password">\
      <input id="authPass2" class="auth-input" type="password" placeholder="\u78ba\u8a8d\u5bc6\u78bc" autocomplete="new-password" style="display:none">\
      <button class="btn-primary" id="authSubmitBtn" onclick="window._doAuthAction()">\u767b\u5165</button>\
      <div class="auth-toggle" id="authToggle" onclick="window._toggleAuthMode()">\u6c92\u6709\u5e33\u865f\uff1f\u9ede\u6b64\u8a3b\u518a</div>\
    </div>\
    <!-- Google panel -->\
    <div class="auth-panel" id="panelGoogle">\
      <div id="gsi-btn" style="display:flex;justify-content:center;margin:1rem 0"></div>\
      <p style="text-align:center;font-size:0.8rem;color:rgba(255,255,255,0.3)">\u4f7f\u7528 Google \u5e33\u865f\u5373\u53ef\u767b\u5165</p>\
    </div>\
    <!-- WeChat panel -->\
    <div class="auth-panel" id="panelWeChat">\
      <div class="wechat-qr">\u5fae\u4fe1\u6388\u6b0a\u4e2d...</div>\
      <p style="text-align:center;font-size:0.85rem;color:rgba(255,255,255,0.5)">\u8acb\u4f7f\u7528\u5fae\u4fe1\u6383\u63cf\u4e0a\u65b9 QR Code \u767b\u5165</p>\
      <p style="text-align:center;font-size:0.75rem;color:rgba(255,255,255,0.3);margin-top:0.5rem">\u6682\u6642\u4f7f\u7528\u5e33\u865f\u5bc6\u78bc\u6216 Google \u767b\u5165</p>\
    </div>\
  </div>\
</div>';

  /* -- tab switching -- */
  document.querySelectorAll('.auth-tab').forEach(function(tab){
    tab.addEventListener('click', function(){
      document.querySelectorAll('.auth-tab').forEach(function(t){t.classList.remove('active')});
      this.classList.add('active');
      document.querySelectorAll('.auth-panel').forEach(function(p){p.classList.remove('active')});
      var panel = document.getElementById('panel' + this.dataset.tab.charAt(0).toUpperCase() + this.dataset.tab.slice(1));
      if(panel) panel.classList.add('active');
      if(this.dataset.tab==='google' && GOOGLE_CLIENT_ID && typeof google!=='undefined' && google.accounts){
        var gBtn=document.getElementById('gsi-btn');
        if(gBtn) google.accounts.id.renderButton(gBtn,{type:'standard',shape:'pill',theme:'outline',size:'large',text:'signin_with'});
      }
    });
  });

  var isRegister = false;
  window._toggleAuthMode = function(){
    isRegister = !isRegister;
    document.getElementById('authSubmitBtn').textContent = isRegister ? '\u8a3b\u518a' : '\u767b\u5165';
    document.getElementById('authToggle').textContent = isRegister ? '\u5df2\u6709\u5e33\u865f\uff1f\u9ede\u6b64\u767b\u5165' : '\u6c92\u6709\u5e33\u865f\uff1f\u9ede\u6b64\u8a3b\u518a';
    document.getElementById('authPass2').style.display = isRegister ? 'block' : 'none';
  };

  window._doAuthAction = function(){
    var email = document.getElementById('authEmail').value.trim();
    var pass = document.getElementById('authPass').value;
    var errEl = document.getElementById('authError');
    errEl.style.display = 'none';
    if(!email || !pass){ errEl.textContent='\u8acb\u586b\u5beb Email \u548c\u5bc6\u78bc'; errEl.style.display='block'; return; }
    if(isRegister){
      var pass2 = document.getElementById('authPass2').value;
      if(pass !== pass2){ errEl.textContent='\u5169\u6b21\u5bc6\u78bc\u4e0d\u4e00\u81f4'; errEl.style.display='block'; return; }
      if(pass.length < 4){ errEl.textContent='\u5bc6\u78bc\u81f3\u5c11 4 \u500b\u5b57\u7b26'; errEl.style.display='block'; return; }
      var users = getUsers();
      if(users[email]){ errEl.textContent='\u6b64 Email \u5df2\u7d93\u8a3b\u518a\u904e'; errEl.style.display='block'; return; }
      users[email] = {password:pass,created:Date.now()};
      saveUsers(users);
      doLogin({name:email.split('@')[0],email:email,avatar:'',sub:'local_'+Date.now(),provider:'local'});
    } else {
      var users = getUsers();
      if(!users[email] || users[email].password !== pass){
        errEl.textContent='Email \u6216\u5bc6\u78bc\u932f\u8aa4'; errEl.style.display='block'; return;
      }
      doLogin({name:email.split('@')[0],email:email,avatar:'',sub:'local_'+Date.now(),provider:'local'});
    }
  };

  /* -- enter key -- */
  document.addEventListener('DOMContentLoaded', function(){
    ['authEmail','authPass','authPass2'].forEach(function(id){
      var el = document.getElementById(id);
      if(el) el.addEventListener('keydown', function(e){ if(e.key==='Enter') window._doAuthAction(); });
    });
  });
})();
