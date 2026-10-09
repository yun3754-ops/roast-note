// 오프라인 지원: 같은 출처의 GET 요청은 네트워크를 먼저 시도하고, 실패하면 마지막으로 받은 사본을 쓴다.
// 로스팅 중 전파가 약해도 앱이 열리고, 새 버전과 beans/ 파일은 온라인일 때 바로 반영된다.
const CACHE = "roast-note-v3";
const VENDOR = "roast-vendor-v1"; // OCR 데이터는 앱 버전이 바뀌어도 지우지 않는다
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== VENDOR).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if(req.method !== "GET" || url.origin !== location.origin) return;
  // OCR 구성요소(vendor/)는 용량이 커서 한 번 받은 뒤에는 캐시를 먼저 쓴다.
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
