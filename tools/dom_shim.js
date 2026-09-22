// Reusable minimal DOM + Web-Audio shim for executing the reader's inline
// script outside a browser.  Used by check_portable.js (portable build) and
// check_server_mode.js (server build).
//
// It is deliberately observable: element lookups are memoised so listeners can
// be fired afterwards, and Audio is a spy that records how many elements were
// created and how often play() was called.
'use strict';

function mkEl(tag) {
  const el = {
    tagName: (tag || 'div').toUpperCase(), style: {}, dataset: {}, children: [],
    textContent: '', innerHTML: '', title: '', value: '', checked: false, hidden: false,
    clientWidth: 1200, clientHeight: 800, offsetWidth: 1200, offsetHeight: 800,
    classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(c) { this.children.push(c); return c; },
    removeChild() {}, setAttribute() {}, getAttribute() { return null; },
    removeAttribute() {}, hasAttribute() { return false; },
    addEventListener(t, fn) { (this._ls = this._ls || {})[t] = (this._ls[t] || []).concat(fn); },
    removeEventListener(t, fn) { const a = (this._ls || {})[t]; if (a) { const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); } },
    dispatchEvent() {}, fire(t, ev) { ((this._ls || {})[t] || []).slice().forEach(fn => fn(ev || {})); },
    focus() {}, blur() {}, click() {}, remove() {},
    querySelector() { return mkEl(); }, querySelectorAll() { return []; },
    getBoundingClientRect() { return { top: 0, left: 0, width: 100, height: 100, right: 100, bottom: 100 }; },
    cloneNode() { return mkEl(tag); }, scrollIntoView() {}, prepend() {},
    setSelectionRange() {}, select() {}, getContext() { return null; },
  };
  return el;
}

function makeSandbox(opts) {
  opts = opts || {};
  const elCache = new Map();
  const audioLog = [];
  const store = new Map();

  function elFor(key, tag) {
    if (!elCache.has(key)) elCache.set(key, mkEl(tag || key));
    return elCache.get(key);
  }

  function SpyAudio() {
    const el = mkEl('audio');
    el.preload = ''; el.src = ''; el.currentTime = 0;
    el.loadCount = 0; el.playCount = 0; el.pauseCount = 0; el.paused = true;
    el._ls = {};
    el.addEventListener = function (t, fn) { el._ls[t] = (el._ls[t] || []).concat(fn); };
    el.removeEventListener = function (t, fn) { const a = el._ls[t]; if (a) { const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); } };
    el.fire = function (t, ev) { (el._ls[t] || []).slice().forEach(fn => fn(ev || {})); };
    el.play = function () { el.playCount++; return Promise.resolve(); };
    el.pause = function () { el.pauseCount++; el.paused = true; };
    el.load = function () { el.loadCount++; };
    el.removeAttribute = function (a) { if (a === 'src') el.src = ''; };
    audioLog.push(el);
    return el;
  }

  const doc = {
    readyState: 'complete',
    documentElement: mkEl('html'), body: mkEl('body'), head: mkEl('head'),
    createElement: mkEl,
    createDocumentFragment: () => mkEl('fragment'),
    createTextNode: (t) => ({ nodeValue: t, textContent: t }),
    querySelector: (sel) => elFor(sel),
    querySelectorAll: () => [],
    getElementById: (id) => elFor('#' + id),
    addEventListener() {}, removeEventListener() {}, title: 'test',
  };

  const sandbox = {
    console, document: doc, window: null,
    navigator: { userAgent: 'node-check', language: 'zh-CN', clipboard: { writeText: () => Promise.resolve() } },
    location: { href: opts.href || 'file:///dist/index.html', protocol: opts.protocol || 'file:', search: '', hash: '', reload() {} },
    localStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
    },
    addEventListener() {}, removeEventListener() {}, dispatchEvent() {},
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    open: () => null,
    setTimeout, clearTimeout, setInterval, clearInterval,
    getComputedStyle: () => ({ paddingLeft: '0px', paddingRight: '0px', getPropertyValue: () => '' }),
    requestAnimationFrame: (cb) => setTimeout(cb, 0),
    IntersectionObserver: function () { this.observe = () => {}; this.disconnect = () => {}; this.unobserve = () => {}; },
    Image: function () { this.src = ''; this.onload = null; this.onerror = null; },
    Audio: SpyAudio,
    Blob: function () { this.text = () => Promise.resolve(''); },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} },
    speechSynthesis: { getVoices: () => [], speak() {}, cancel() {}, addEventListener() {} },
    SpeechSynthesisUtterance: function () {},
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.self = sandbox;

  // no fetch by default: the portable build must not need it
  sandbox.fetch = () => { throw new Error('fetch() was called but was not expected here'); };
  sandbox.XMLHttpRequest = function () { throw new Error('XHR used'); };

  // contextify last, so everything above is visible to the script
  require('vm').createContext(sandbox);

  return { sandbox, audioLog, elFor, doc };
}

/** Execute every inline <script> block of an HTML document in the sandbox. */
function runScripts(html, sandbox) {
  const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  let ran = 0;
  const errors = [];
  blocks.forEach((code, i) => {
    try {
      new (require('vm').Script)(code, { filename: 'inline-block-' + i })
        .runInContext(sandbox, { timeout: 60000 });
      ran++;
    } catch (e) {
      errors.push('block ' + i + ': ' + e.message);
    }
  });
  return { blocks: blocks.length, ran, errors };
}

module.exports = { mkEl, makeSandbox, runScripts };
