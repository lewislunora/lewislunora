/* ===== Auth Guard: Google-only login with fallback ===== */
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
.auth-overlay{position:fixed;inset:0;z-index:99999;background:#0a0e27;display:flex;align-items:center;justify-content:center}\
.auth-box{background:#131837;border:1px solid rgba(255,255,255,0.12);border-radius:20px;padding:2.5rem;width:360px;max-width:90vw;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.5)}\
.auth-box .icon{font-size:3rem;margin-bottom:0.5rem}\
.auth-box h2{font-size:1.3rem;margin-bottom:0.3rem}\
.auth-box p{color:rgba(255,255,255,0.5);font-size:0.85rem;margin-bottom:1.5rem}\
#gsi-box{display:flex;justify-content:center;margin:1rem 0}\
.auth-fallback{margin-top:1rem;border-top:1px solid rgba(255,255,255,0.1);padding-top:1rem}\
.auth-fallback input{width:100%;padding:0.6rem 1rem;border-radius:10px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.05);color:#fff;font-size:0.85rem;outline:none;box-sizing:border-box}\
.auth-fallback input:focus{border-color:rgba(0,212,255,0.4)}\
.auth-fallback .btn{width:100%;margin-top:0.5rem;padding:0.6rem;border-radius:10px;border:none;background:linear-gradient(135deg,#00d4ff,#7b68ee);color:#fff;font-weight:600;font-size:0.85rem;cursor:pointer}\
.auth-fallback .btn:hover{opacity:0.9}\
.auth-fallback .hint{font-size:0.7rem;color:rgba(255,255,255,0.25);margin-top:0.5rem}\
';
  document.head.appendChild(style);

  fetch((location.hostname.includes('onrender.com')?'':'https://lewislunora.onrender.com')+'/api/config')
    .then(function(r){return r.json()})
    .then(function(cfg){
      GOOGLE_CLIENT_ID = cfg.google_client_id||'';
      if(GOOGLE_CLIENT_ID && typeof google!=='undefined' && google.accounts){
        google.accounts.id.initialize({client_id:GOOGLE_CLIENT_ID,callback:onGoogle});
        google.accounts.id.renderButton(document.getElementById('gsi-box'),{type:'standard',shape:'pill',theme:'outline',size:'large',text:'signin_with'});
      }
    })
    .catch(function(){});

  function onGoogle(r){
    var p = JSON.parse(atob(r.credential.split('.')[1]));
    var u = {name:p.name,email:p.email,avatar:p.picture,sub:p.sub,provider:'google'};
    localStorage.setItem('chat_user', JSON.stringify(u));
    if (typeof onUserLogin === 'function') onUserLogin(u);
    location.reload();
  }

  function doFallback(){
    var name = document.getElementById('fbName').value.trim();
    if(!name) return;
    var u = {name:name,email:'',avatar:'',sub:'fb_'+Date.now(),provider:'fallback'};
    localStorage.setItem('chat_user', JSON.stringify(u));
    location.reload();
  }

  document.body.innerHTML = '\
<div class="auth-overlay">\
  <div class="auth-box">\
    <div class="icon">&#x1f512;</div>\
    <h2>\u6b61\u8fce\u56de\u4f86</h2>\
    <p>\u8acb\u4f7f\u7528 Google \u5e33\u865f\u767b\u5165</p>\
    <div id="gsi-box"></div>\
    <div class="auth-fallback">\
      <input id="fbName" placeholder="\u8f38\u5165\u540d\u7a31\u5148\u884c\u767b\u5165" onkeydown="if(event.key==\'Enter\')doFallback()">\
      <button class="btn" onclick="doFallback()">\u5148\u767b\u5165</button>\
      <div class="hint">Google \u767b\u5165\u8a2d\u5b9a\u5b8c\u6210\u5f8c\u5373\u53ef\u4f7f\u7528</div>\
    </div>\
  </div>\
</div>';

  window.doFallback = doFallback;
})();
