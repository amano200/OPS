const CACHE='ops-shell-auto-dedd1210d391';
const CORE=['./','./index.html','./manifest.webmanifest','./icon-192.png','./icon-512.png','./verein.pgn','./ops-auto-tasks.json'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE)).catch(()=>{}))});
self.addEventListener('activate',e=>e.waitUntil((async()=>{for(const k of await caches.keys())if(k.startsWith('ops-shell-')&&k!==CACHE)await caches.delete(k);await self.clients.claim()})()));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;
e.respondWith((async()=>{
 const url=new URL(e.request.url);
 // Local data and program files: fresh online, offline fallback; external engine: existing cache-first behavior.
 const fresh=url.origin===self.location.origin;
 if(fresh){try{const r=await fetch(e.request);if(r&&r.ok){(await caches.open(CACHE)).put(e.request,r.clone());return r}}catch(_){}}
 const hit=await caches.match(e.request);if(hit)return hit;
 try{const r=await fetch(e.request);if(r&&r.ok)(await caches.open(CACHE)).put(e.request,r.clone());return r}
 catch(err){if(e.request.mode==='navigate')return await caches.match('./index.html');throw err}
 })())});
