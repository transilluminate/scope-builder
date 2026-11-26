// Offline copy of the builder, for phones that have added it to the home screen.
// Network first: whenever the site can be reached you get the latest version, and the copy kept here
// is only used when you are offline. Nothing about you or your scope is stored: scope links live in
// the address (after #), which is never sent to the server or kept in this cache.
const CACHE = 'scope-builder-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith(fetch(req).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => caches.match(req, { ignoreSearch: true }).then(hit => hit || Response.error())));
});
