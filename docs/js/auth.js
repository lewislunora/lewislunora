/* 翔川 Neo 登入狀態工具 — 與後端 /api/auth/* 配合 */
(function (window) {
  'use strict';

  function apiOrigin() {
    if (/\.github\.io/i.test(window.location.hostname)) return 'https://lewislunora.onrender.com';
    return window.location.origin;
  }
  function siteBase() {
    if (/\.github\.io/i.test(window.location.hostname)) {
      var m = window.location.pathname.match(/^\/([^/]+)/);
      return m ? '/' + m[1] + '/' : '/';
    }
    return '/';
  }

  var AUTH_API = apiOrigin() + '/api/auth';
  var currentUser = null;

  function api(path, opts) {
    return fetch(AUTH_API + path, Object.assign({ credentials: 'include' }, opts || {}));
  }

  async function me() {
    try {
      var res = await api('/me');
      if (!res.ok) return null;
      currentUser = await res.json();
      return currentUser;
    } catch (e) {
      return null;
    }
  }

  async function providers() {
    try {
      var res = await api('/providers');
      if (!res.ok) return [];
      var data = await res.json();
      return data.providers || [];
    } catch (e) {
      return [];
    }
  }

  function logout() {
    window.location.href = AUTH_API + '/logout?next=' + encodeURIComponent(window.location.origin + window.location.pathname);
  }

  function updateAuthUI() {
    var loggedIn = document.querySelector('[data-auth="in"]');
    var loggedOut = document.querySelector('[data-auth="out"]');
    if (!loggedIn && !loggedOut) return;
    me().then(function (u) {
      if (u) {
        if (loggedIn) {
          loggedIn.hidden = false;
          var nameEl = loggedIn.querySelector('[data-user-name]');
          var avatarEl = loggedIn.querySelector('[data-user-avatar]');
          if (nameEl) nameEl.textContent = u.name || u.email || '使用者';
          if (avatarEl && u.avatar) avatarEl.src = u.avatar;
          var logoutBtn = loggedIn.querySelector('[data-action="logout"]');
          if (logoutBtn) logoutBtn.addEventListener('click', logout);
        }
        if (loggedOut) loggedOut.hidden = true;
      } else {
        if (loggedIn) loggedIn.hidden = true;
        if (loggedOut) loggedOut.hidden = false;
      }
    });
  }

  window.Auth = {
    API_ORIGIN: apiOrigin(),
    SITE_BASE: siteBase(),
    me: me,
    providers: providers,
    logout: logout,
    updateAuthUI: updateAuthUI,
    get user() { return currentUser; }
  };
})(window);
