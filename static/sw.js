const CACHE_NAME = 'sonora-v1';
const SHELL_FILES = ['/', '/static/manifest.json'];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_FILES))
    );
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);

    // Never cache API calls or audio streams
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/downloads/')) {
        return;
    }

    // Cache-first for shell, network-first for everything else
    e.respondWith(
        caches.match(e.request).then(cached => cached || fetch(e.request))
    );
});
