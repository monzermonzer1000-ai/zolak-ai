"use strict";

const CACHE_NAME = "zolak-ai-assets-v42";
const ASSETS = [
  "/manifest.json",
  "/static/style.css?v=32",
  "/static/mobile-fixes.css?v=1",
  "/static/performance.css?v=2",
  "/static/premium-ui.css?v=1",
  "/static/chat-enhancements.css?v=1",
  "/static/mobile-overrides.css?v=1",
  "/static/soft-slate-theme.css?v=3",
  "/static/app.js?v=34",
  "/static/icon.svg",
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith("zolak-ai-") && key !== CACHE_NAME)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // Never cache authenticated pages, API responses, or user-specific data.
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/admin") ||
    url.pathname.startsWith("/login") ||
    url.pathname.startsWith("/logout")
  ) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => new Response(
        "<!doctype html><html lang=\"ar\" dir=\"rtl\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>زولك AI</title><body style=\"font-family:Arial;text-align:center;padding:40px\"><h2>زولك AI 🇸🇩</h2><p>ما في اتصال بالإنترنت حالياً. اتصل بالشبكة وحاول تاني.</p></body></html>",
        { headers: { "Content-Type": "text/html; charset=utf-8" } }
      ))
    );
    return;
  }

  if (url.pathname.startsWith("/static/") || url.pathname === "/manifest.json") {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        });
      })
    );
  }
});