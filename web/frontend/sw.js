/* Arithmetic Super App — Service Worker
 *
 * Strategies:
 *   - Static assets (HTML, CSS, icons, manifest): cache-first
 *   - API/GraphQL requests: network-first, fall back to cache
 *   - Offline fallback: serve /static/offline.html for navigations
 */
const CACHE = "arith-pwa-v2";
const PRECACHE = [
    "/",
    "/static/manifest.json",
    "/static/offline.html",
    "/static/icon-192.svg",
    "/static/icon-512.svg",
    "/static/css/design.css",
    "/static/css/components.css",
    "/static/js/api.js",
    "/static/js/ui.js",
    "/static/js/theme.js",
    "/static/js/offline.js",
    "/static/js/commands.js",
    "/static/js/app.js",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Only handle GET for caching
    if (req.method !== "GET") return;

    // Same-origin only
    if (url.origin !== self.location.origin) return;

    // Network-first for API + GraphQL
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/graphql")) {
        event.respondWith(
            fetch(req)
                .then((res) => {
                    const copy = res.clone();
                    caches.open(CACHE).then((c) => c.put(req, copy));
                    return res;
                })
                .catch(() => caches.match(req))
        );
        return;
    }

    // Cache-first for static + navigation
    event.respondWith(
        caches.match(req).then((cached) => {
            if (cached) return cached;
            return fetch(req)
                .then((res) => {
                    if (!res || !res.ok || res.type === "opaque") return res;
                    const copy = res.clone();
                    caches.open(CACHE).then((c) => c.put(req, copy));
                    return res;
                })
                .catch(() => {
                    // Navigation fallback
                    if (req.mode === "navigate") {
                        return caches.match("/static/offline.html");
                    }
                });
        })
    );
});

self.addEventListener("message", (event) => {
    if (event.data === "skipWaiting") self.skipWaiting();
});
