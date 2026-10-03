// Recipebook service worker.
//
// Caches the app shell (CSS/JS/icons) and previously viewed pages so the app keeps
// working offline. Logging out clears the runtime cache so cached pages are not left
// behind on a shared device.
const VERSION = "v1";
const STATIC_CACHE = `recipebook-static-${VERSION}`;
const RUNTIME_CACHE = `recipebook-runtime-${VERSION}`;
const OFFLINE_URL = "/offline";
const PRECACHE_URLS = [
  "/offline",
  "/static/css/app.css",
  "/static/js/htmx.min.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== STATIC_CACHE && key !== RUNTIME_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Logging out drops cached pages so the next person cannot see them.
  if (url.pathname === "/logout") {
    event.waitUntil(caches.delete(RUNTIME_CACHE));
    return;
  }

  if (
    url.pathname.startsWith("/static/") ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname === "/sw.js"
  ) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }

  if (url.pathname.startsWith("/attachments/")) {
    event.respondWith(cacheFirst(request, RUNTIME_CACHE));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  event.respondWith(networkFirst(request, RUNTIME_CACHE));
});

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    return cached || Response.error();
  }
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function networkFirstNavigation(request) {
  try {
    const response = await fetch(request);
    // Never cache redirects (e.g. to /login) over the requested page.
    if (response && response.ok && !response.redirected) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cache = await caches.open(RUNTIME_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    const offline = await caches.match(OFFLINE_URL);
    return offline || Response.error();
  }
}
