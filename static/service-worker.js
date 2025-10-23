const CACHE_NAME = "depenses-cache-v1";
const urlsToCache = [
  "/depenses/",
  "/depenses/static/css/style.css",
  "/depenses/static/icons/novoprint_icon_192.png",
  "/depenses/static/icons/novoprint_icon_512.png"
];

// Install SW
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
});

// Fetch from cache
self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});