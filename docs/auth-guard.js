/* ===== Auth Guard: Google-only login ===== */
(function() {
  var user = JSON.parse(localStorage.getItem('chat_user') || 'null');
  if (user) return;

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

  document.body.innerHTML = '\
<div class="auth-overlay">\
  <div class="auth-box">\
    <div class="icon">&#x1f512;</div>\
    <h2>\u6b61\u8fce\u56de\u4f86</h2>\
    <p>\u8acb\u4f7f\u7528 Google \u5e33\u865f\u767b\u5165</p>\
    <div id="gsi-box"></div>\
  </div>\
</div>';
})();
