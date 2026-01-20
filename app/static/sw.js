/* PWA-lite service worker (network-first navigations, cache-first assets) */

const CACHE_VERSION = 'v1';
const CACHE_NAME = `mfhs-pwa-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline';

const PRECACHE_URLS = [
  OFFLINE_URL,
  '/static/css/main.css',
  '/static/images/placeholder.svg',
  '/static/images/pwa-icon.svg',
  '/static/images/pwa-maskable.svg',
  '/static/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await cache.addAll(PRECACHE_URLS);
      await self.skipWaiting();
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => (key === CACHE_NAME ? Promise.resolve() : caches.delete(key))));
      await self.clients.claim();
    })()
  );
});

function isSameOrigin(requestUrl) {
  try {
    return new URL(requestUrl).origin === self.location.origin;
  } catch (_) {
    return false;
  }
}

self.addEventListener('fetch', (event) => {
  const req = event.request;

  if (req.method !== 'GET') return;

  // Navigation requests: try network first, fall back to offline page.
  if (req.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          return await fetch(req);
        } catch (_) {
          const cache = await caches.open(CACHE_NAME);
          const cachedOffline = await cache.match(OFFLINE_URL);
          return cachedOffline || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
        }
      })()
    );
    return;
  }

  // Static assets (same-origin): cache-first with background refresh.
  if (isSameOrigin(req.url) && req.destination && ['style', 'script', 'image', 'font'].includes(req.destination)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE_NAME);
        const cached = await cache.match(req);
        const fetchPromise = fetch(req)
          .then((resp) => {
            // Only cache successful, basic responses.
            if (resp && resp.ok) {
              cache.put(req, resp.clone());
            }
            return resp;
          })
          .catch(() => null);

        return cached || (await fetchPromise) || new Response('', { status: 504 });
      })()
    );
  }
});
