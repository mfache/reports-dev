const CACHE_NAME = 'dt-reports-v3';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Stratégie Network-First très simple : 
    // on essaie de joindre le réseau, sinon on regarde dans le cache (ou on échoue silencieusement)
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
