/* Nova-Band service worker — installable PWA with an offline app shell.
   Pages: network first (fresh deploys win), cache as fallback.
   Everything else (CSS, JS, images, fonts): stale-while-revalidate.
   API traffic (Firebase / Google APIs) is never cached. Bump VERSION to
   drop old caches on the next deploy. */
var VERSION = "novaband-v4";
var SHELL = [
  "./", "index.html", "app.html", "manifest.webmanifest",
  "css/style.css",
  "js/main.js", "js/app.js", "js/app-home.js", "js/band-link.js", "js/firebase-init.js",
  "assets/pwa/icon-192.png", "assets/pwa/icon-512.png"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function isApi(url) {
  return /firestore|identitytoolkit|securetoken|firebaseinstallations|googleapis\.com\/(?!css)/.test(url);
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET" || isApi(req.url)) return;
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then(function (res) {
      var copy = res.clone();
      caches.open(VERSION).then(function (c) { c.put(req, copy); });
      return res;
    }).catch(function () {
      return caches.match(req, { ignoreSearch: true }).then(function (r) { return r || caches.match("app.html"); });
    }));
    return;
  }
  e.respondWith(caches.match(req).then(function (cached) {
    var net = fetch(req).then(function (res) {
      if (res && (res.ok || res.type === "opaque")) {
        var copy = res.clone();
        caches.open(VERSION).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () { return cached; });
    return cached || net;
  }));
});
