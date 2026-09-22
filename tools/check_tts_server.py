# -*- coding: utf-8 -*-
"""
Verify the /tts cache endpoint.

The sandbox this was developed in has no internet, so the upstream path cannot
be exercised end to end here.  Instead this checks everything that does not
need Google:

  * input validation (missing / oversized / illegal characters -> 400)
  * a cache HIT served straight from disk, with the long-cache headers
  * /tts-stats reflecting the cache contents
  * HEAD must never trigger a download
  * the cold path fails cleanly as 502 rather than hanging or crashing

and it seeds the cache directly, which is exactly what a real fetch would leave
behind.
"""
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:8765"
TTS_DIR = os.path.join(ROOT, "cache", "tts")

fails = []


def ok(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def req(path, method="GET"):
    """Return (status, headers_with_lowercase_keys, body).

    Header keys must be lowercased: SimpleHTTPRequestHandler emits
    "Content-type" for static files but "Content-Type" for the ones we set
    ourselves, and a plain dict lookup is case-sensitive.
    """
    r = urllib.request.Request(BASE + path, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def seed(word, size):
    """Write a fake mp3 into the cache the same way serve.py would."""
    os.makedirs(TTS_DIR, exist_ok=True)
    key = hashlib.sha1(("es|" + word).encode("utf-8")).hexdigest()[:20]
    path = os.path.join(TTS_DIR, key + ".mp3")
    with open(path, "wb") as f:
        f.write(b"\xff\xfb\x90\x00" + os.urandom(size - 4))
    return path


print("=== 输入校验 ===")
st, h, b = req("/tts")
ok(st == 400, "missing ?w= -> 400 (got %s)" % st)

st, h, b = req("/tts?w=" + "a" * 200)
ok(st == 400, "word longer than 120 chars -> 400 (got %s)" % st)

st, h, b = req("/tts?w=" + urllib.parse.quote("../../etc/passwd"))
ok(st == 400, "path-traversal-ish input -> 400 (got %s)" % st)

st, h, b = req("/tts?w=" + urllib.parse.quote("<script>alert(1)</script>"))
ok(st == 400, "HTML/script input -> 400 (got %s)" % st)

print("\n=== HEAD 不触发下载 ===")
st, h, b = req("/tts?w=nuncacheado", method="HEAD")
ok(st == 404, "HEAD on an uncached word -> 404, no download attempted (got %s)" % st)
ok(len(b) == 0, "HEAD returns an empty body")

print("\n=== 缓存命中 ===")
word = "hola"
path = seed(word, 4096)
ok(os.path.exists(path), "seeded cache file: %s" % os.path.basename(path))

st, h, b = req("/tts?w=" + word)
ok(st == 200, "GET cached word -> 200 (got %s)" % st)
ok(h.get("content-type") == "audio/mpeg", "Content-Type: %s" % h.get("content-type"))
ok(h.get("x-tts-cache") == "hit", "X-TTS-Cache: %s" % h.get("x-tts-cache"))
ok(h.get("cache-control") == "public, max-age=31536000, immutable",
   "long-lived Cache-Control: %s" % h.get("cache-control"))
ok(len(b) == 4096, "body length matches the cached file (%d bytes)" % len(b))

st, h, b = req("/tts?w=" + word, method="HEAD")
ok(st == 200 and h.get("x-tts-cache") == "hit", "HEAD on a cached word -> 200 hit")

print("\n=== 一个词一个文件，不互相干扰 ===")
seed("adios", 2048)
st1, h1, b1 = req("/tts?w=hola")
st2, h2, b2 = req("/tts?w=adios")
ok(len(b1) == 4096 and len(b2) == 2048, "two words keep separate cache entries")

print("\n=== /tts-stats ===")
st, h, b = req("/tts-stats")
ok(st == 200, "/tts-stats -> 200 (got %s)" % st)
try:
    data = json.loads(b.decode("utf-8"))
except Exception as e:
    data = None
    ok(False, "stats is valid JSON: %s" % e)
if data:
    ok(data.get("files", 0) >= 2, "stats files >= 2: %s" % data.get("files"))
    ok(data.get("bytes", 0) >= 6144, "stats bytes >= 6144: %s" % data.get("bytes"))
    print("     %s" % json.dumps(data, ensure_ascii=False))

print("\n=== 上游不可达时的失败路径（本沙箱无网络，正好验证）===")
st, h, b = req("/tts?w=palabraquenuncasehapisado")
ok(st == 502, "uncached word with no internet -> 502, not a hang or a crash (got %s)" % st)
st, h, b = req("/web/index.html")
ok(st == 200, "the reader itself still serves fine after a TTS failure (got %s)" % st)

print("\n=== 静态资源没被 /tts 影响 ===")
for p, ct in (("/data/dict.json", "application/json"),
              ("/pages/page_0034.jpg", "image/jpeg")):
    st, h, b = req(p)
    ok(st == 200 and ct in (h.get("content-type") or ""), "%s -> %s %s" % (p, st, h.get("content-type")))

print("\n" + ("%d CHECK(S) FAILED" % len(fails) if fails else "ALL CHECKS PASSED"))
sys.exit(1 if fails else 0)
