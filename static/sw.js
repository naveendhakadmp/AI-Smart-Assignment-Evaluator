const CACHE_NAME = "gradepilot-shell-v1";
const APP_SHELL = [
  "/offline",
  "/manifest.webmanifest",
  "/static/style.css",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/icon.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key.startsWith("gradepilot-shell-") && key !== CACHE_NAME)
        .map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(async () =>
      (await caches.match("/offline")) || Response.error()
    ));
    return;
  }

  if (request.url.includes("/static/") || request.url.endsWith("/manifest.webmanifest")) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
  }
});
