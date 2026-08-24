// Bump this version whenever you want to force-refresh cached assets.
const CACHE_NAME = 'stms-v5';
const urlsToCache = [
  '/',
  '/static/css/app.css',
  '/static/js/app.js'
];

self.addEventListener('install', event => {
  // Activate the new service worker immediately (don't wait for old tabs).
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache).catch(() => {}))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(
        names.map(name => (name !== CACHE_NAME ? caches.delete(name) : null))
      ))
      .then(() => self.clients.claim())
  );
});

// Network-first: always try the network so new deploys show right away;
// fall back to cache only when offline.
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  event.respondWith(
    fetch(req)
      .then(res => {
        if (res && res.status === 200) {
          try {
            const url = new URL(req.url);
            if (url.origin === self.location.origin) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then(c => c.put(req, copy)).catch(() => {});
            }
          } catch (e) { /* ignore */ }
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
