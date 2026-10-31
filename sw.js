const CACHE_NAME = 'stubai-pwa-v1';
const TILE_CACHE = 'stubai-tiles-v1';

const APP_SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './export.gpx',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.9.0/proj4.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME && key !== TILE_CACHE) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Map Tiles (OpenTopoMap) -> Cache First, fallback to Network
  if (url.hostname.includes('tile.opentopomap.org')) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const canonicalUrl = `https://a.tile.opentopomap.org${url.pathname}`;
        const cachedResponse = (await cache.match(event.request)) || (await cache.match(canonicalUrl));
        if (cachedResponse) {
          return cachedResponse;
        }
        try {
          const networkResponse = await fetch(event.request);
          if (networkResponse && networkResponse.status === 200) {
            cache.put(event.request, networkResponse.clone());
            cache.put(canonicalUrl, networkResponse.clone());
          }
          return networkResponse;
        } catch (err) {
          return cachedResponse || new Response('', { status: 408, statusText: 'Offline Tile Unavailable' });
        }
      })
    );
    return;
  }

  // App Shell & Assets -> Cache First with Network Fallback
  event.respondWith(
    caches.match(event.request).then(async (response) => {
      if (response) {
        // Return from cache, revalidate in background if online
        fetch(event.request).then((netRes) => {
          if (netRes && netRes.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, netRes));
          }
        }).catch(() => {});
        return response;
      }
      return fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return networkResponse;
      });
    }).catch(() => {
      // Offline fallback
      return caches.match('./index.html');
    })
  );
});
