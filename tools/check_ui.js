// Verify the reader's inline JS parses, then replay its lookup logic against the
// real data to measure how many clickable words actually resolve offline.
// Usage: node tools/check_ui.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'web', 'index.html'), 'utf8');

// ---- 1. syntax-check the inline script -------------------------------
// Compiled in-process with vm.Script: the sandbox forbids piping a child
// process's stdio, so `node --check` as a subprocess would fail with EPERM.
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('FAIL: no inline <script> found'); process.exit(1); }
const js = m[1];
try {
  new vm.Script(js, { filename: 'index.html:inline' });
  console.log('OK  inline JS parses (' + js.split('\n').length + ' lines)');
} catch (e) {
  console.error('FAIL syntax: ' + e.message);
  process.exit(1);
}

// ---- 2. external references ------------------------------------------
const urls = [...html.matchAll(/https?:\/\/[^\s'"<>)]+/g)].map(x => x[0]);
const allowed = /translate\.google\.com|spanishdict\.com|127\.0\.0\.1/;
const bad = urls.filter(u => !allowed.test(u));
console.log(bad.length ? 'FAIL external refs: ' + bad.join(', ')
                       : 'OK  no disallowed external references (' + urls.length + ' total, all allowed)');

// ---- 3. DOM wiring: every $('#id') the script uses must exist in the HTML --
const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(x => x[1]));
const used = new Set([...js.matchAll(/\$\('#([A-Za-z0-9_-]+)'\)/g)].map(x => x[1]));
const missing = [...used].filter(i => !ids.has(i));
console.log(missing.length
  ? 'FAIL $() selectors with no matching element: ' + missing.join(', ')
  : 'OK  all ' + used.size + ' $() selectors resolve against ' + ids.size + ' defined ids');

// ---- 4. data shape the script relies on ------------------------------
const sample = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'pages.json'), 'utf8'));
const need = ['page', 'file', 'lines', 'words'];
const badPage = sample.find(p => need.some(k => !(k in p)));
console.log(!badPage ? 'OK  every page record has ' + need.join('/')
                     : 'FAIL page ' + badPage.page + ' is missing a required field');
const bw = sample.flatMap(p => p.words).find(w => !(w.x >= 0 && w.x <= 1 && w.w > 0 && w.w <= 1));
console.log(!bw ? 'OK  all word boxes are normalised 0..1'
                : 'FAIL normalisation broken, e.g. ' + JSON.stringify(bw));
const bl = sample.flatMap(p => p.lines).find(l => !(l.x >= 0 && l.x <= 1 && l.w > 0 && l.w <= 1));
console.log(!bl ? 'OK  all line boxes are normalised 0..1'
                : 'FAIL line box not normalised: ' + JSON.stringify(bl));

// ---- 5. replay lookupDict on real data -------------------------------
function fold(s) {
  s = String(s).toLowerCase();
  try { s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, ''); } catch (e) {}
  return s;
}
function cleanWord(raw) { return String(raw).replace(/^[^\w]+|[^\w]+$/gu, ''); }

const DICT = Object.create(null);
const FOLD_KEYS = new Map();
for (const [k, v] of Object.entries(JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'dict.json'), 'utf8')))) {
  DICT[k.toLowerCase()] = v;
  const f = fold(k);
  if (!FOLD_KEYS.has(f)) FOLD_KEYS.set(f, k.toLowerCase());
}
const LEMMAS = Object.create(null);
for (const [k, v] of Object.entries(JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'lemmas.json'), 'utf8')))) {
  LEMMAS[k.toLowerCase()] = v;
}

function lookupDict(raw) {
  const cleaned = cleanWord(raw);
  const key = cleaned.toLowerCase();
  if (!key) return null;
  const tries = [key];
  const f = fold(key);
  if (f && f !== key) tries.push(f);
  if (/es$/.test(key) && key.length > 4) tries.push(key.slice(0, -2));
  if (/s$/.test(key) && key.length > 3) tries.push(key.slice(0, -1));
  if (/se$/.test(key) && key.length > 4) tries.push(key.slice(0, -2));
  if (/ones$/.test(key) && key.length > 5) tries.push(key.slice(0, -4) + 'ón');
  if (/ces$/.test(key) && key.length > 4) tries.push(key.slice(0, -3) + 'z');
  if (/des$/.test(key) && key.length > 4) tries.push(key.slice(0, -2));
  if (/es$/.test(f) && f.length > 4) tries.push(f.slice(0, -2));
  for (const t of tries) if (DICT[t]) return { entry: DICT[t], key: t, how: 'direct' };
  const fk = FOLD_KEYS.get(key) || (f ? FOLD_KEYS.get(f) : null);
  if (fk && DICT[fk]) return { entry: DICT[fk], key: fk, how: 'fold' };
  const lm = LEMMAS[key] || (f ? LEMMAS[f] : null);
  if (lm && lm.inf) {
    const lk = String(lm.inf).toLowerCase();
    const e2 = DICT[lk] || DICT[fold(lk)];
    if (e2) return { entry: e2, key: lk, how: 'lemma', lemma: lm };
  }
  return { entry: null, key, how: 'miss' };
}

const pages = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'pages.json'), 'utf8'));
let tot = 0, hit = 0;
const byHow = { direct: 0, fold: 0, lemma: 0 };
const misses = new Map();
for (const p of pages) {
  for (const w of p.words) {
    if (w.skip) continue;
    const c = cleanWord(w.t);
    if (!c) continue;
    tot++;
    const r = lookupDict(w.t);
    if (r && r.entry) { hit++; byHow[r.how]++; }
    else misses.set(c, (misses.get(c) || 0) + 1);
  }
}
console.log('\nclickable words: ' + tot);
console.log('resolved offline: ' + hit + ' (' + (100 * hit / tot).toFixed(1) + '%)');
console.log('  by direct match : ' + byHow.direct);
console.log('  by accent-fold  : ' + byHow.fold);
console.log('  by verb lemma   : ' + byHow.lemma);

const top = [...misses.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15);
console.log('\ntop unresolved words (these fall through to the online lookup):');
console.log('  ' + top.map(([w, n]) => w + '(' + n + ')').join(', '));
