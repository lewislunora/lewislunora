/* 翔川 Neo 統一流量 beacon：Render 與 GitHub Pages 共用。
 * GitHub Pages 是靜態 mirror，會跨域送回 Render 的 /api/analytics/track。
 * 只記錄 pageview（頁面、來源、時間），不取用任何個資。
 */
(function () {
  try {
    if (!location.protocol || location.protocol.indexOf('http') !== 0) return;
    if (navigator.doNotTrack === '1') return;
    if (/bot|spider|crawl|slurp|baidu|yandex/i.test(navigator.userAgent || '')) return;

    var api = location.hostname.indexOf('github.io') >= 0
      ? 'https://lewislunora.onrender.com/api/analytics/track'
      : '/api/analytics/track';

    // GitHub Pages 掛在 /lewislunora/ 子路徑，去掉前綴才能和 Render 的頁面路徑對齊
    var page = location.pathname + location.search;
    if (location.hostname.indexOf('github.io') >= 0) {
      page = page.replace(/^\/lewislunora/, '') || '/';
    }

    var payload = JSON.stringify({
      event: 'pageview',
      page: page,
      ref: document.referrer || '',
      ts: Date.now()
    });

    if (navigator.sendBeacon) {
      navigator.sendBeacon(api, new Blob([payload], { type: 'application/json' }));
    } else {
      fetch(api, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true
      }).catch(function () {});
    }
  } catch (e) { /* 追蹤失敗不影響使用 */ }
})();
