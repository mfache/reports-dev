const CACHE_NAME = 'dt-reports-v3';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // NE PAS intercepter les flux d'authentification OAuth2 ni le callback
    // Cela évite les erreurs 403 CSRF dues à des requêtes concurrentes en tâche de fond.
    if (url.pathname.includes('/oauth2-google/') || url.pathname.includes('callback')) {
        return;
    }

    // Stratégie Network-First très simple : 
    // on essaie de joindre le réseau, sinon on regarde dans le cache (ou on échoue silencieusement)
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
