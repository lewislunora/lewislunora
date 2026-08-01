/* Service Worker: network-first for pages, stale-while-revalidate for assets.
   Prevents users from seeing stale versions after deploys (no manual cache clearing). */
const VERSION = 'v20260801';
const CACHE_NAME = 'lewis-' + VERSION;

self.addEventListener('install', function(e) {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME));
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function(e) {
  var url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // navigation (HTML pages) → network-first, always fresh
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).then(function(res) {
        var copy = res.clone();
        caches.open(CACHE_NAME).then(function(c) { c.put(e.request, copy); });
        return res;
      }).catch(function() {
        return caches.match(e.request).then(function(m) {
          return m || caches.match('/index.html');
        });
      })
    );
    return;
  }

  // assets (css/js/images) → stale-while-revalidate
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      var network = fetch(e.request).then(function(res) {
        if (res && res.status === 200) {
          var copy = res.clone();
          caches.open(CACHE_NAME).then(function(c) { c.put(e.request, copy); });
        }
        return res;
      }).catch(function() { return cached; });
      return cached || network;
    })
  );
});
