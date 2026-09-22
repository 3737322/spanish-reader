// Portable-build checks.
//
// Executes dist/index.html's inline scripts for real (data blob + reader) in a
// DOM shim, then asserts the reader boots from the inlined data with NO fetch
// and NO server — and that the speech path behaves as designed.
//
//   node tools/check_portable.js
//
// This is the closest thing to opening the file in a browser that can be done
// without one.  Server-mode behaviour is covered by check_server_mode.js.
const fs = require('fs');
const path = require('path');
const { makeSandbox, runScripts } = require('./dom_shim.js');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist', '西班牙语点读便携版');
const htmlPath = path.join(DIST, 'index.html');

let fail = 0;
function ok(cond, msg) { console.log((cond ? 'OK   ' : 'FAIL ') + msg); if (!cond) fail++; }

if (!fs.existsSync(htmlPath)) {
  console.error('FAIL dist/index.html not found — run tools/build_portable.py');
  process.exit(1);
}
const html = fs.readFileSync(htmlPath, 'utf8');
console.log('index.html: ' + (html.length / 1048576).toFixed(2) + ' MB\n');

// ------------------------------------------------------------ static checks
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const js = scripts.join('\n');
ok(scripts.length >= 2, 'inline <script> blocks present: ' + scripts.length + ' (data blob + reader)');

// Only references that actually LOAD something count.  A bare http:// in the
// page text (the book's copyright page prints www.fltrp.com) is content, not a
// dependency.
const refs = [
  ...[...html.matchAll(/(?:src|href)\s*=\s*["']?(https?:\/\/[^\s"'>)]+)/g)].map(x => x[1]),
  ...[...html.matchAll(/url\(\s*["']?(https?:\/\/[^\s"')]+)/g)].map(x => x[1]),
  ...[...html.matchAll(/@import\s+["'](https?:\/\/[^\s"']+)/g)].map(x => x[1]),
];
const allowed = /translate\.google\.com|spanishdict\.com|127\.0\.0\.1/;
const bad = refs.filter(u => !allowed.test(u));
ok(bad.length === 0, bad.length ? 'disallowed resource refs: ' + [...new Set(bad)].join(', ')
                                : 'no disallowed resource references (' + refs.length + ' loading refs, all allowed)');

// ------------------------------------------------------------ run the code
const { sandbox: g, audioLog, elFor } = makeSandbox({ href: 'file:///dist/index.html' });
const res = runScripts(html, g);
ok(res.errors.length === 0, 'all ' + res.blocks + ' script blocks executed without throwing' +
   (res.errors.length ? ' — ' + res.errors.join('; ') : ''));

// ------------------------------------------------------------ the data blob
const D = g.__DSH_INLINE__;
ok(!!D, 'window.__DSH_INLINE__ is defined');
ok(D && Array.isArray(D.pages) && D.pages.length === 305, 'inlined pages: ' + (D && D.pages ? D.pages.length : 0) + ' (expect 305)');
ok(D && D.dict && Object.keys(D.dict).length > 4000, 'inlined dict entries: ' + (D && D.dict ? Object.keys(D.dict).length : 0));
ok(D && D.lemmas && Object.keys(D.lemmas).length > 40000, 'inlined lemma forms: ' + (D && D.lemmas ? Object.keys(D.lemmas).length : 0));
const p0 = D && D.pages && D.pages[0];
ok(p0 && typeof p0.file === 'string' && Array.isArray(p0.words), 'page record shape is intact');

// every "<" was escaped, so the blob cannot contain a literal </script>
const blobStart = html.indexOf('window.__DSH_INLINE__=');
const blobEnd = html.indexOf('</script>', blobStart);
const blobText = html.slice(blobStart + 'window.__DSH_INLINE__='.length, blobEnd);
ok(blobText.indexOf('<') === -1, 'no literal "<" inside the data blob (so no premature </script>)');
ok(blobEnd > blobStart, 'data blob is terminated by a real </script>');

// ------------------------------------------------------- in-memory loading
(async () => {
  ok(g.PORTABLE === true, 'PORTABLE mode detected');
  ok(g.IMG_BASE === 'pages/', 'image base is relative for file:// (' + g.IMG_BASE + ')');
  ok(g.TTS_PROXY === null, 'no local /tts proxy exists in the portable build');

  const pages = await g.loadPages();
  ok(pages.length === 305, 'loadPages() resolved from memory: ' + pages.length + ' pages');

  const nd = await g.loadDict();
  ok(nd > 4000, 'loadDict() resolved from memory: ' + nd + ' entries');
  ok(g.DICT_STATE === 'ok', 'DICT_STATE = ' + g.DICT_STATE);

  const nl = await g.loadLemmas();
  ok(nl > 40000, 'loadLemmas() resolved from memory: ' + nl + ' forms');

  const r1 = g.lookupDict('tengo');
  ok(r1 && r1.entry && r1.lemma && r1.lemma.inf === 'tener',
     'lookupDict("tengo") -> tener ' + (r1 && r1.lemma ? r1.lemma.t + ' ' + r1.lemma.p : '') +
     ' = ' + (r1 && r1.entry ? r1.entry.zh : '?'));
  const r2 = g.lookupDict('abrigo');
  ok(r2 && r2.entry, 'lookupDict("abrigo") -> ' + (r2 && r2.entry ? r2.entry.zh : 'MISS'));
  const r3 = g.lookupDict('casas');
  ok(r3 && r3.entry, 'lookupDict("casas") resolves via plural -> ' + (r3 && r3.entry ? r3.entry.zh : 'MISS'));

  const missing = [];
  for (const p of pages) if (!fs.existsSync(path.join(DIST, 'pages', p.file))) missing.push(p.file);
  ok(missing.length === 0, 'all 305 referenced page images exist on disk' +
     (missing.length ? ' — missing e.g. ' + missing[0] : ''));

  const extra = fs.readdirSync(path.join(DIST, 'pages')).filter(f => f.endsWith('.jpg')).length;
  ok(extra === 305, 'pages/ contains exactly ' + extra + ' jpgs');
  ok(fs.existsSync(path.join(DIST, '使用说明.txt')), '使用说明.txt present');
  ok(!fs.existsSync(path.join(DIST, 'data')), 'no data/ folder leaked into the portable build');

  // ------------------------------------------------ TTS cache / prefetch
  console.log('\n--- 语音响应速度相关行为 ---');
  audioLog.length = 0;
  g.TTS.engine = 'auto';
  g.updateTtsBadge();
  ok(g.TTS.level === 2, 'no es voice in shim -> level 2 (online audio), level=' + g.TTS.level);

  g.preloadWord('hola');
  ok(audioLog.length === 1, 'preloadWord() created exactly 1 <audio> element');
  const a1 = audioLog[0];
  ok(/translate_tts/.test(a1.src) && /hola/.test(a1.src), 'preloaded the direct upstream URL in portable mode');
  ok(a1.playCount === 0, 'prefetch does NOT start playback');

  g.preloadWord('hola');
  ok(audioLog.length === 1, 'second hover on the same word reuses the cached element (no new request)');

  a1.fire('canplay');
  ok(g.audioCache.get('hola').ready === true, 'element marked ready after buffering');
  ok(g.audioInflight === 0, 'prefetch quota is returned once buffering completes');

  g.speakOnline('hola', {});
  ok(audioLog.length === 1, 'playing a prefetched word creates no new element (cache hit)');
  ok(a1.playCount === 1, 'play() was called on the already-buffered element');

  a1.fire('playing');
  ok(g.TTS.lastMs !== null && g.TTS.lastMs >= 0, 'latency recorded on the "playing" event: ' + g.TTS.lastMs + 'ms');
  ok(/上次 \d+ms/.test(elFor('#ttsBadge').textContent),
     'status bar shows the latency: ' + elFor('#ttsBadge').textContent);

  g.preloadWord('adios');
  ok(audioLog.length === 2, 'a different word gets its own element');
  audioLog[audioLog.length - 1].fire('canplay');

  for (let i = 0; i < 120; i++) {
    g.preloadWord('w' + i);
    const last = audioLog[audioLog.length - 1];
    if (last) last.fire('canplay');
  }
  const size = g.audioCache ? g.audioCache.size : -1;
  ok(size > 0 && size <= 48, 'cache stays bounded: ' + size + ' entries (max 48)');
  ok(g.audioInflight === 0, 'no prefetch quota leaked over 122 prefetches (inflight=' + g.audioInflight + ')');
  ok(g.audioCache.has('hola'), 'the currently-playing element is never evicted');

  audioLog.length = 0;
  g.TTS.engine = 'system';
  g.updateTtsBadge();
  ok(g.TTS.level === 1, 'engine=system switches to the system voice path (level=' + g.TTS.level + ')');
  g.preloadWord('hola');
  ok(audioLog.length === 0, 'no audio prefetch when the system engine is selected');

  console.log('\n' + (fail ? fail + ' CHECK(S) FAILED' : 'ALL CHECKS PASSED'));
  process.exit(fail ? 1 : 0);
})();
