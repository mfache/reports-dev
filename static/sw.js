const CACHE_NAME = 'dt-reports-v4';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // NE PAS intercepter :
    // - les chargements de page : ils passent par les redirections oauth2-proxy / Azure,
    //   et un échec du fetch ici affichait une erreur au lieu de la page (2026-10-28) ;
    // - les flux d'authentification OAuth2 et le callback (erreurs 403 CSRF) ;
    // - tout ce qui n'est pas un GET.
    if (event.request.mode === 'navigate' || event.request.method !== 'GET') {
        return;
    }
    if (url.pathname.includes('/oauth2/') || url.pathname.includes('callback')) {
        return;
    }

    // Stratégie Network-First très simple :
    // on essaie de joindre le réseau, sinon on regarde dans le cache (ou on échoue silencieusement)
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
