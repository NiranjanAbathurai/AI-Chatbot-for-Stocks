/**
 * Service Worker for Stock Debate Chat PWA
 * Cache-first for static assets, network-first for API calls.
 */

const CACHE_NAME = "stockchat-v1";
const STATIC_ASSETS = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/manifest.json",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
    "https://cdn.jsdelivr.net/npm/marked/marked.min.js"
];

// Install — cache static assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log("[SW] Caching static assets");
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// Fetch — cache-first for static, network-first for API
self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // Skip non-GET requests
    if (event.request.method !== "GET") return;

    // API calls — network first, no cache
    if (url.pathname.startsWith("/api/")) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response(
                    JSON.stringify({ error: "You are offline. Please check your connection." }),
                    { status: 503, headers: { "Content-Type": "application/json" } }
                );
            })
        );
        return;
    }

    // Static assets — cache first, network fallback
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return fetch(event.request).then((response) => {
                // Cache successful responses for static assets
                if (response.ok && (url.pathname.startsWith("/static/") || url.pathname === "/" || url.pathname === "/manifest.json")) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => {
                // Offline fallback for HTML
                if (event.request.headers.get("accept")?.includes("text/html")) {
                    return caches.match("/");
                }
                return new Response("Offline", { status: 503 });
            });
        })
    );
});
