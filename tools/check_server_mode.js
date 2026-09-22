// Server-mode checks.
//
// The portable build is covered by check_portable.js; this one loads the
// NON-portable web/index.html, stubs fetch with the real data files, and
// asserts the behaviour that only exists when a local server is present:
//
//   * TTS goes through the local /tts cache proxy instead of straight to Google
//   * if that proxy fails, the reader falls back to the direct upstream URL and
//     stops using the proxy for the rest of the session
//   * the normal data loading path still works
//
//   node tools/check_server_mode.js
const fs = require('fs');
const path = require('path');
const { makeSandbox, runScripts } = require('./dom_shim.js');

const ROOT = path.resolve(__dirname, '..');
let fail = 0;
function ok(cond, msg) { console.log((cond ? 'OK   ' : 'FAIL ') + msg); if (!cond) fail++; }

const html = fs.readFileSync(path.join(ROOT, 'web', 'index.html'), 'utf8');
const data = {
  '/data/pages.json': fs.readFileSync(path.join(ROOT, 'data', 'pages.json'), 'utf8'),
  '/data/dict.json': fs.readFileSync(path.join(ROOT, 'data', 'dict.json'), 'utf8'),
  '/data/lemmas.json': fs.readFileSync(path.join(ROOT, 'data', 'lemmas.json'), 'utf8'),
};

const { sandbox: g, audioLog, elFor } = makeSandbox({
  href: 'http://127.0.0.1:8765/web/index.html', protocol: 'http:',
});

// a realistic fetch: only paths the server actually serves
const fetched = [];
g.fetch = (url) => {
  fetched.push(url);
  const t = data[url];
  if (t === undefined) return Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' });
  return Promise.resolve({
    ok: true, status: 200,
    headers: { get: () => String(t.length) },
    text: () => Promise.resolve(t),
  });
};

const res = runScripts(html, g);
ok(res.errors.length === 0, 'all ' + res.blocks + ' script blocks ran' +
   (res.errors.length ? ' — ' + res.errors.join('; ') : ''));

(async () => {
  console.log('\n--- 服务器模式 ---');
  ok(g.PORTABLE === false, 'PORTABLE is false when there is no inline data');
  ok(g.IMG_BASE === '/pages/', 'image base is absolute in server mode (' + g.IMG_BASE + ')');

  const pages = await g.loadPages();
  ok(pages.length === 305, 'loadPages() via fetch: ' + pages.length + ' pages');
  ok(fetched.includes('/data/pages.json'), 'fetched /data/pages.json');

  // ---- the new proxy behaviour -------------------------------------
  console.log('\n--- TTS 走本地 /tts 缓存代理 ---');
  ok(g.TTS_PROXY === '/tts?w=', 'TTS_PROXY points at the local cache endpoint (' + g.TTS_PROXY + ')');
  const u = g.ttsUrl('hola');
  ok(u === '/tts?w=hola', 'ttsUrl("hola") -> ' + u);

  g.TTS.engine = 'auto';
  g.updateTtsBadge();
  ok(g.TTS.level === 2, 'level 2 (online audio) as expected in the shim');

  audioLog.length = 0;
  g.preloadWord('hola');
  ok(audioLog.length === 1, 'prefetch created one <audio>');
  ok(audioLog[0].src === '/tts?w=hola',
     'prefetch goes through the local cache, not straight to Google: ' + audioLog[0].src);

  g.speakOnline('hola', {});
  ok(audioLog.length === 1, 'clicking reuses the prefetched element');

  // ---- proxy failure -> permanent fallback to the direct URL -------
  console.log('\n--- 代理失败时退回直连 ---');
  const a1 = audioLog[0];
  ok(g.TTS.proxyDown === false, 'proxyDown starts false');
  a1.fire('error');
  ok(g.TTS.proxyDown === true, 'a proxy error sets proxyDown');
  ok(/^https:\/\/translate\.google\.com\/translate_tts/.test(a1.src),
     'the same element retries against the upstream URL: ' + a1.src.slice(0, 58) + '…');
  ok(a1.playCount >= 2, 'playback is retried after the fallback (play calls: ' + a1.playCount + ')');

  audioLog.length = 0;
  g.preloadWord('adios');
  ok(audioLog.length === 1, 'a later word still prefetches');
  ok(/^https:\/\/translate\.google\.com/.test(audioLog[0].src),
     'later words go straight upstream once the proxy is known bad');

  // ---- and the direct URL helper still works -----------------------
  ok(g.ttsUrl('x', true).startsWith('https://translate.google.com/'), 'ttsUrl(text, true) forces the direct URL');

  console.log('\n' + (fail ? fail + ' CHECK(S) FAILED' : 'ALL CHECKS PASSED'));
  process.exit(fail ? 1 : 0);
})();
