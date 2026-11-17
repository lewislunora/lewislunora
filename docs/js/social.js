/* 翔川 Neo 社交平台共用工具 — 動態牆 / 私訊 / 交友 */
(function (window) {
  'use strict';

  // GitHub Pages 是 /lewislunora/ 子路徑，所有站內連結都要帶前綴，
  // 否則 /social/、/login.html 會指到網域根目錄而 404。
  var IS_GH = window.location.hostname.indexOf('github.io') >= 0;
  var API = IS_GH ? 'https://lewislunora.onrender.com' : '';
  var SITE = IS_GH ? '/lewislunora' : '';
  var me = null;

  function loginUrl() {
    return SITE + '/login.html?next=' + encodeURIComponent(window.location.origin + SITE + '/social/');
  }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    // GitHub Pages 呼叫 Render API 屬跨網域，必須 include 才會帶登入 cookie；
    // 同網域則維持 same-origin。
    opts.credentials = IS_GH ? 'include' : 'same-origin';
    if (opts.body && typeof opts.body !== 'string') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(API + path, opts).then(function (r) {
      if (r.status === 401) { me = null; }
      return r.json().then(function (d) { return { ok: r.ok, data: d }; })
        .catch(function () { return { ok: r.ok, data: {} }; });
    });
  }

  function current() {
    if (me) return Promise.resolve(me);
    return api('/api/auth/me').then(function (r) {
      me = r.ok ? r.data : null;
      return me;
    });
  }

  function requireLogin() {
    return current().then(function (u) {
      if (!u) { window.location.href = loginUrl(); throw new Error('login required'); }
      return u;
    });
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function timeAgo(ts) {
    if (!ts) return '';
    var t = new Date(String(ts).replace(' ', 'T') + (String(ts).includes('Z') ? '' : 'Z'));
    var diff = Date.now() - t.getTime();
    if (diff < 60000) return '剛剛';
    if (diff < 3600000) return Math.floor(diff / 60000) + ' 分鐘前';
    if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小時前';
    if (diff < 604800000) return Math.floor(diff / 86400000) + ' 天前';
    return t.toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' });
  }

  function avatarHtml(u, size) {
    size = size || 40;
    if (u && u.avatar) {
      var av = String(u.avatar);
      // AI 夥伴用 emoji 當頭像（🤖🌱✨🛠️），不是圖片路徑
      if (!/^(https?:|\/|data:|\.\/)/.test(av) && av.indexOf('.') === -1) {
        return '<div class="avatar" style="width:' + size + 'px;height:' + size + 'px;display:flex;align-items:center;justify-content:center;background:#0d1428;font-size:' + Math.round(size * 0.5) + 'px">' + esc(av) + '</div>';
      }
      return '<img class="avatar" style="width:' + size + 'px;height:' + size + 'px" src="' + esc(av) + '" onerror="this.style.display=\'none\'">';
    }
    return '<div class="avatar" style="width:' + size + 'px;height:' + size + 'px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#7b68ee,#00d4ff);color:#fff;font-weight:700">' + esc((u && u.name ? u.name[0] : '?').toUpperCase()) + '</div>';
  }

  var NAV_LINKS = [
    { href: SITE + '/social/', label: '動態', icon: '📰' },
    { href: SITE + '/social/people.html', label: '找人', icon: '🤝' },
    { href: SITE + '/community/', label: '討論版', icon: '🗣️' },
    { href: SITE + '/social/chat.html', label: '私訊', icon: '💬', chat: true },
    { href: SITE + '/social/profile.html?me=1', label: '我的', icon: '👤' },
  ];

  function renderNav(active) {
    var nav = document.getElementById('social-nav');
    if (!nav) return;
    current().then(function (u) {
      var links = NAV_LINKS.map(function (l) {
        var cls = 'sn-item' + (l.href.slice(SITE.length) === active ? ' active' : '');
        var badge = '';
        if (l.chat && u) badge = '<span class="sn-badge" id="sn-unread" style="display:none">0</span>';
        return '<a class="' + cls + '" href="' + l.href + '">' + l.icon + '<span class="sn-label">' + l.label + '</span>' + badge + '</a>';
      }).join('');
      var right = u
        ? '<div class="sn-user"><a class="sn-avatar-link" href="' + SITE + '/social/profile.html?me=1">' + avatarHtml(u, 32) + '</a>' +
          '<button class="sn-btn" onclick="Social.logout()">登出</button></div>'
        : '<a class="sn-btn primary" href="' + loginUrl() + '">登入 / 註冊</a>';
      nav.innerHTML = '<div class="sn-inner"><a class="sn-brand" href="' + SITE + '/social/"><img src="' + SITE + '/favicon.png" alt="">翔川<em>社交</em></a>' +
        '<div class="sn-links">' + links + '</div>' + right + '</div>';
      bindUnread();
    });
  }

  function bindUnread() {
    var el = document.getElementById('sn-unread');
    if (!el) return;
    var tick = function () {
      api('/api/chat/unread').then(function (r) {
        var n = r.ok ? (r.data.unread || 0) : 0;
        if (n > 0) { el.style.display = 'inline-flex'; el.textContent = n > 99 ? '99+' : n; }
        else { el.style.display = 'none'; }
      });
    };
    tick();
    setInterval(tick, 10000);
  }

  function logout() {
    window.location.href = API + '/api/auth/logout?next=' + encodeURIComponent(window.location.origin + SITE + '/social/');
  }

  function notify(text) {
    var el = document.getElementById('sn-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'sn-toast';
      el.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:#111827;border:1px solid #2b3446;color:#e2e8f0;padding:12px 22px;border-radius:999px;font-size:14px;z-index:999;box-shadow:0 8px 30px rgba(0,0,0,.5);transition:opacity .3s';
      document.body.appendChild(el);
    }
    el.textContent = text;
    el.style.opacity = '1';
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.style.opacity = '0'; }, 2200);
  }

  window.Social = { api: api, current: current, requireLogin: requireLogin, esc: esc, timeAgo: timeAgo, avatarHtml: avatarHtml, renderNav: renderNav, logout: logout, notify: notify, loginUrl: loginUrl, site: SITE };
})(window);
