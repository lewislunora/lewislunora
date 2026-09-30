/* ===== Auth Guard (soft): 永不擋內容，登入改用浮動按鈕 + 彈窗 ===== */
(function() {
  var user = JSON.parse(localStorage.getItem('chat_user') || 'null');
  if (user && user.sub) return;

  if (!document.querySelector('script[src*="accounts.google.com/gsi/client"]')) {
    var gs = document.createElement('script');
    gs.src = 'https://accounts.google.com/gsi/client';
    gs.async = true; gs.defer = true;
    document.head.appendChild(gs);
  }
  var GOOGLE_CLIENT_ID = '';

  var style = document.createElement('style');
  style.textContent = '\
.auth-float{position:fixed;right:18px;bottom:18px;z-index:9998;display:inline-flex;align-items:center;gap:.45rem;padding:.55rem 1rem;border-radius:999px;border:1px solid rgba(0,212,255,.35);background:linear-gradient(135deg,rgba(0,212,255,.18),rgba(123,104,238,.18));backdrop-filter:blur(14px);color:#eaf6ff;font-size:13px;font-weight:600;letter-spacing:.3px;cursor:pointer;box-shadow:0 8px 28px rgba(0,0,0,.35);transition:transform .2s}\
.auth-float:hover{transform:translateY(-2px);border-color:rgba(0,212,255,.6)}\
.auth-overlay{position:fixed;inset:0;z-index:99999;background:rgba(5,8,24,.72);backdrop-filter:blur(6px);display:none;align-items:center;justify-content:center}\
.auth-overlay.show{display:flex}\
.auth-box{background:#131837;border:1px solid rgba(255,255,255,0.12);border-radius:20px;padding:2.2rem;width:360px;max-width:90vw;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.5)}\
.auth-box .icon{font-size:3rem;margin-bottom:0.5rem}\
.auth-box h2{font-size:1.3rem;margin-bottom:0.3rem;color:#f0f6ff}\
.auth-box p{color:rgba(255,255,255,0.5);font-size:0.85rem;margin-bottom:1.5rem}\
#gsi-box{display:flex;justify-content:center;margin:1rem 0}\
.auth-fallback{margin-top:1rem;border-top:1px solid rgba(255,255,255,0.1);padding-top:1rem}\
.auth-fallback input{width:100%;padding:0.6rem 1rem;border-radius:10px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.05);color:#fff;font-size:0.85rem;outline:none;box-sizing:border-box}\
.auth-fallback input:focus{border-color:rgba(0,212,255,0.4)}\
.auth-fallback .btn{width:100%;margin-top:0.5rem;padding:0.6rem;border-radius:10px;border:none;background:linear-gradient(135deg,#00d4ff,#7b68ee);color:#fff;font-weight:600;font-size:0.85rem;cursor:pointer}\
.auth-fallback .btn:hover{opacity:0.9}\
.auth-close{position:absolute;top:14px;right:18px;color:rgba(255,255,255,.55);font-size:22px;cursor:pointer;line-height:1}\
@media(prefers-color-scheme:light){.auth-float{color:#0b2545;box-shadow:0 8px 24px rgba(0,0,0,.14)}.auth-box{background:#ffffff;border-color:rgba(0,0,0,.08)}.auth-box h2{color:#111827}.auth-box p{color:rgba(0,0,0,.5)}.auth-fallback{border-top-color:rgba(0,0,0,.08)}.auth-fallback input{color:#111827;background:rgba(0,0,0,.04);border-color:rgba(0,0,0,.1)}.auth-fallback input::placeholder{color:rgba(0,0,0,.35)}.auth-box .icon{filter:none}.auth-close{color:rgba(0,0,0,.5)}}';
  document.head.appendChild(style);

  /* 浮動登入鈕 — 不遮內容 */
  function init(){
  var floatBtn = document.createElement('button');
  floatBtn.className = 'auth-float';
  floatBtn.innerHTML = '\u{1f511} \u767b\u5165\u5f8c\u4f7f\u7528\u6703\u54e1\u529f\u80fd';
  floatBtn.type = 'button';
  floatBtn.addEventListener('click', showModal);
  document.body.appendChild(floatBtn);

  /* 彈窗 */
  var overlay = document.createElement('div');
  overlay.className = 'auth-overlay';
  var box = document.createElement('div');
  box.className = 'auth-box';
  box.style.position = 'relative';
  box.innerHTML = '\
<div class="auth-close">&times;</div>\
<div class="icon">&#x1f512;</div>\
<h2>\u6b61\u8fce\u56de\u4f86</h2>\
<p>\u767b\u5165\u5f8c\u53ef\u4ee5\u7559\u8a00\u3001\u53c3\u8207AI\u914d\u5c0d\u4e0e\u5b58\u4e0b\u7d50\u679c</p>\
<div id="gsi-box"></div>\
<div class="auth-fallback">\
  <input id="fbName" placeholder="\u4e0d\u7528 Google \u4e5f\u884c\uff0c\u8f38\u5165\u540d\u7a31\u5373\u53ef" onkeydown="if(event.key==\'Enter\')doFallback()">\
  <button class="btn" onclick="doFallback()">\u5148\u767b\u5165</button>\
</div>';
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  overlay.querySelector('.auth-close').addEventListener('click', hideModal);
  overlay.addEventListener('click', function(e){ if (e.target === overlay) hideModal(); });

  function showModal(){ overlay.classList.add('show'); maybeRenderGoogle(); }
  function hideModal(){ overlay.classList.remove('show'); }

  function maybeRenderGoogle(){
    if (GOOGLE_CLIENT_ID && typeof google !== 'undefined' && google.accounts
        && !document.querySelector('#gsi-box iframe, #gsi-box div[class*=credential]')) {
      try {
        google.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: onGoogle });
        google.accounts.id.renderButton(document.getElementById('gsi-box'),
          { type:'standard', shape:'pill', theme:'outline', size:'large', text:'signin_with' });
      } catch(e) {}
    }
  }

  fetch((location.hostname.includes('onrender.com')?'':'https://lewislunora.onrender.com')+'/api/config')
    .then(function(r){ return r.json(); })
    .then(function(cfg){ GOOGLE_CLIENT_ID = cfg.google_client_id || ''; })
    .catch(function(){});

  function onGoogle(r){
    var p = JSON.parse(atob(r.credential.split('.')[1]));
    var u = { name:p.name, email:p.email, avatar:p.picture, sub:p.sub, provider:'google' };
    localStorage.setItem('chat_user', JSON.stringify(u));
    if (typeof onUserLogin === 'function') onUserLogin(u);
    location.reload();
  }

  window.doFallback = doFallback;
  function doFallback(){
    var name = (document.getElementById('fbName') || {}).value;
    if (!name) return;
    var u = { name:name, email:'', avatar:'', sub:'fb_'+Date.now(), provider:'fallback' };
    localStorage.setItem('chat_user', JSON.stringify(u));
    if (typeof onUserLogin === 'function') onUserLogin(u);
    location.reload();
  }

  /* 全站所有使用者按鈕都能叫出登入窗 */
  document.addEventListener('click', function(e){
    var cl = e.target.closest ? e.target.closest('[data-require-login], [data-login]') : null;
    if (cl && !localStorage.getItem('chat_user')) { e.preventDefault(); e.stopPropagation(); showModal(); }
  }, true);
  } /* init */

  if (document.body) {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();