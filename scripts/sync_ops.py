#!/usr/bin/env python3
"""Synchronise the gzip-embedded OPS 3b.20 PGN and install task import without replacing user data."""
import base64
import gzip
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
PGN = ROOT / 'verein.pgn'
SW = ROOT / 'service-worker.js'

HOOK = '''
// OPS automatic training imports: merge without resetting old training progress.
async function importPreparedClubTasks(){
 try{
  const r=await fetch('./ops-auto-tasks.json',{cache:'no-cache'});
  if(!r.ok)return 0;
  const data=await r.json();
  if(data.schema!=='ops-auto-1'||!Array.isArray(data.puzzles))return 0;
  const bank=getBank(),existing=new Set(bank.map(x=>x.id));let count=0;
  for(const p of data.puzzles){
   if(!p||typeof p.id!=='string'||!p.id.startsWith('club-')||typeof p.fen!=='string'||existing.has(p.id))continue;
   bank.push(p);existing.add(p.id);count++;
  }
  if(count)setBank(bank);
  const done=new Set(getDone());let changed=false;
  for(const id of (data.processedClubIds||[])){
   if(typeof id==='string'&&/^club-[0-9]+$/.test(id)&&!done.has(id)){done.add(id);changed=true;}
  }
  if(changed)setDone([...done]);
  if(count&&$('dataStatus'))$('dataStatus').textContent='✓ '+count+' automatisch analysierte Vereinsaufgaben ergänzt · bisheriger Fortschritt erhalten.';
  return count;
 }catch(e){console.warn('OPS automatische Aufgaben:',e);return 0;}
}
'''

SW_SRC = '''const CACHE='ops-shell-auto-20261109-v1';
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
'''


APP_VERSION = '3b.21'

def main():
    html = INDEX.read_text(encoding='utf-8')
    strings = re.findall(r"await gun\('([A-Za-z0-9+/=]+)'\)", html)
    # First is UI, second the embedded game file, third JavaScript.
    if len(strings) != 3:
        raise RuntimeError(f'OPS-Struktur unerwartet: {len(strings)} gzip-Blöcke')
    raw = [gzip.decompress(base64.b64decode(s)).decode('utf-8') for s in strings]
    pgn = PGN.read_text(encoding='utf-8')
    raw[1] = pgn
    js = raw[2]
    if 'async function importPreparedClubTasks(){' not in js:
        marker = 'async function bootOps320(){'
        if marker not in js: raise RuntimeError('OPS-Startfunktion nicht gefunden')
        js = js.replace(marker, HOOK + '\n' + marker, 1)
    if 'await importPreparedClubTasks();' not in js:
        marker = 'const lowValueHiddenCount=refreshPracticalFilter();'
        if marker not in js: raise RuntimeError('OPS-Boot-Marker nicht gefunden')
        js = js.replace(marker, 'await importPreparedClubTasks();\n' + marker, 1)
    js = js.replace('42 Vereinspartien eingebaut', f'{pgn.count("[Event ")} Vereinspartien eingebaut')
    js = js.replace("version:'3b.20'", f"version:'{APP_VERSION}'")
    raw[2] = js
    raw[0] = re.sub(r'Die [0-9]+ Vereinspartien sind fest enthalten',
                    f'Die {pgn.count("[Event ")} Vereinspartien sind fest enthalten', raw[0])
    raw[0] = raw[0].replace('Stufe 3b.20', f'Stufe {APP_VERSION}')
    html = html.replace('OPS 3b.20 wird geladen', f'OPS {APP_VERSION} wird geladen')
    # Replace each original base64 block exactly once.
    for old, plaintext in zip(strings, raw):
        packed = base64.b64encode(gzip.compress(plaintext.encode('utf-8'), mtime=0)).decode('ascii')
        html = html.replace("await gun('"+old+"')", "await gun('"+packed+"')", 1)
    INDEX.write_text(html, encoding='utf-8')
    # Data response freshness is controlled by the SW; increment cache name when contents change.
    sw = SW_SRC.replace('auto-20261109-v1', 'auto-' + __import__('hashlib').sha256((APP_VERSION + pgn + (ROOT/'ops-auto-tasks.json').read_text(encoding='utf-8')).encode()).hexdigest()[:12])
    SW.write_text(sw, encoding='utf-8')
    print(f'OPS synchronisiert: {pgn.count("[Event ")} Vereinspartien, Auto-Aufgaben-Import aktiv.')

if __name__ == '__main__': main()