// ?ㅽ봽?쇱씤 吏?? 媛숈? 異쒖쿂??GET ?붿껌? ?ㅽ듃?뚰겕瑜?癒쇱? ?쒕룄?섍퀬, ?ㅽ뙣?섎㈃ 留덉?留됱쑝濡?諛쏆? ?щ낯???대떎.
// 濡쒖뒪??以??꾪뙆媛 ?쏀빐???깆씠 ?대━怨? ??踰꾩쟾怨?beans/ ?뚯씪? ?⑤씪?몄씪 ??諛붾줈 諛섏쁺?쒕떎.
const CACHE = "roast-note-v15";
const VENDOR = "roast-vendor-v1"; // OCR ?곗씠?곕뒗 ??踰꾩쟾??諛붾뚯뼱??吏?곗? ?딅뒗??const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== VENDOR).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if(req.method !== "GET" || url.origin !== location.origin) return;
  // OCR 援ъ꽦?붿냼(vendor/)???⑸웾??而ㅼ꽌 ??踰?諛쏆? ?ㅼ뿉??罹먯떆瑜?癒쇱? ?대떎.
  if(url.pathname.includes("/vendor/")){
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if(res.ok){ const copy = res.clone(); caches.open(VENDOR).then(c => c.put(req, copy)); }
      return res;
    })));
    return;
  }
  e.respondWith(
    fetch(req).then(res => {
      if(res.ok){ const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req).then(hit => hit || caches.match("index.html")))
  );
});
