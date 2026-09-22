# -*- coding: utf-8 -*-
"""
Local server for the Spanish click-to-read reader.

    python serve.py            # http://127.0.0.1:8765/web/index.html
    python serve.py 9000       # custom port
    python serve.py --open     # also open the browser

Standard library only.  Serves the project root, so the reader can fetch
/data/pages.json, /data/dict.json and the page images under /pages/.

It also exposes a small TTS cache endpoint:

    GET /tts?w=hola        -> audio/mpeg  (fetched once from Google, then)
    GET /tts?w=hola        -> audio/mpeg  (served from cache/tts/, no network)
    GET /tts-stats         -> {"files": N, "bytes": M, "mb": x}

Why a proxy at all: the reader normally points an <audio> element straight at
Google's translate_tts endpoint.  That works, but the browser cannot read those
bytes (no CORS), so nothing can be cached beyond the element's own lifetime.
Proxying through the local server makes the audio same-origin, which lets it be
cached on disk and reused across sessions - and after a word has been heard
once, it plays with no network at all.

Only 127.0.0.1 is bound, and the upstream URL is a fixed template, so this
cannot be used as an open proxy.
"""
import hashlib
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- TTS cache
TTS_DIR = os.path.join(ROOT, "cache", "tts")
TTS_UPSTREAM = "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=es&q="
TTS_MAX_LEN = 120                       # a single word or short phrase, never a page
TTS_TIMEOUT = 12
TTS_MIN_BYTES = 128                     # anything smaller is an error page, not audio
# Only characters that can legitimately appear in Spanish text may be requested.
TTS_ALLOWED = re.compile(r"^[\w\sÁÉÍÓÚÜÑáéíóúüñ¿¡.,;:!?'’\-()]+$", re.UNICODE)

_tts_locks = {}
_tts_locks_guard = threading.Lock()


def _word_lock(word):
    """One lock per word, so different words download in parallel."""
    with _tts_locks_guard:
        lk = _tts_locks.get(word)
        if lk is None:
            lk = _tts_locks[word] = threading.Lock()
        return lk


def tts_cache_path(word):
    key = hashlib.sha1(("es|" + word).encode("utf-8")).hexdigest()[:20]
    return os.path.join(TTS_DIR, key + ".mp3")


def tts_get(word):
    """Return (bytes, from_cache) for a word, downloading at most once."""
    path = tts_cache_path(word)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f.read(), True
        except OSError:
            pass                                  # unreadable -> refetch below

    with _word_lock(word):
        # another thread may have finished it while we waited
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read(), True
            except OSError:
                pass

        req = urllib.request.Request(
            TTS_UPSTREAM + urllib.parse.quote(word),
            headers={
                # Google rejects the default urllib agent
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"),
                "Referer": "https://translate.google.com/",
                "Accept": "audio/mpeg,*/*",
            })
        with urllib.request.urlopen(req, timeout=TTS_TIMEOUT) as r:
            data = r.read()
        if len(data) < TTS_MIN_BYTES:
            raise ValueError("upstream returned %d bytes (not audio?)" % len(data))

        try:
            os.makedirs(TTS_DIR, exist_ok=True)
            tmp = path + ".tmp%d" % os.getpid()
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)                 # atomic: never a half-written mp3
        except OSError:
            pass                                  # cache write failure is not fatal
        return data, False


def tts_stats():
    files = 0
    total = 0
    if os.path.isdir(TTS_DIR):
        for name in os.listdir(TTS_DIR):
            if not name.endswith(".mp3"):
                continue
            try:
                total += os.path.getsize(os.path.join(TTS_DIR, name))
                files += 1
            except OSError:
                pass
    return {"files": files, "bytes": total, "mb": round(total / 1048576.0, 2)}


# ------------------------------------------------------------------ handler
class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = "SpanishReader/1.0"
    protocol_version = "HTTP/1.1"          # keep-alive: noticeably snappier for many small requests

    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({
        ".json": "application/json; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".mp3": "audio/mpeg",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/plain; charset=utf-8",
    })

    def __init__(self, *args, **kwargs):
        self._cc = None
        super().__init__(*args, directory=ROOT, **kwargs)

    # -- routing ---------------------------------------------------------
    def do_GET(self):
        if self.path.startswith("/tts"):
            return self.handle_tts(head_only=False)
        return super().do_GET()

    def do_HEAD(self):
        if self.path.startswith("/tts"):
            return self.handle_tts(head_only=True)
        return super().do_HEAD()

    # -- TTS -------------------------------------------------------------
    def handle_tts(self, head_only):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/tts-stats":
            body = json.dumps(tts_stats(), ensure_ascii=False).encode("utf-8")
            self._cc = "no-store"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return

        params = urllib.parse.parse_qs(parsed.query)
        word = (params.get("w") or [""])[0].strip()
        if not word or len(word) > TTS_MAX_LEN or not TTS_ALLOWED.match(word):
            return self.send_error(400, "bad word")

        # A HEAD must never trigger a download; it only reports cache state.
        if head_only:
            path = tts_cache_path(word)
            if os.path.exists(path):
                size = os.path.getsize(path)
                self._cc = "public, max-age=31536000, immutable"
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(size))
                self.send_header("X-TTS-Cache", "hit")
                self.end_headers()
            else:
                self._cc = "no-store"
                self.send_response(404, "not cached")
                self.send_header("Content-Length", "0")
                self.end_headers()
            return

        try:
            data, cached = tts_get(word)
        except urllib.error.HTTPError as e:
            return self.send_error(502, "tts upstream HTTP %s" % e.code)
        except Exception as e:
            return self.send_error(502, "tts upstream failed: %s" % e)

        # the audio for a given word never changes -> let the browser keep it
        self._cc = "public, max-age=31536000, immutable"
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-TTS-Cache", "hit" if cached else "miss")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass                                   # user clicked another word mid-download

    # -- headers ---------------------------------------------------------
    def end_headers(self):
        if self._cc is None:
            if self.path.startswith("/data/") or self.path.endswith(".json"):
                self._cc = "no-store, must-revalidate"   # regenerated by the pipeline
            else:
                self._cc = "public, max-age=86400"
        self.send_header("Cache-Control", self._cc)
        super().end_headers()

    def log_message(self, fmt, *args):
        # keep the console readable: only report errors and TTS misses
        if self.path.startswith("/tts"):
            if args and str(args[1]).startswith(("4", "5")):
                sys.stderr.write("  tts %s\n" % (fmt % args))
            return
        if args and str(args[1]).startswith(("4", "5")):
            sys.stderr.write("  %s %s\n" % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8765
    url = "http://127.0.0.1:%d/web/index.html" % port
    with Server(("127.0.0.1", port), Handler) as httpd:
        print("=" * 62)
        print("  西班牙语点读工具 已启动")
        print("  %s" % url)
        print("")
        print("  用 Microsoft Edge 打开（Edge 有西班牙语在线自然语音）")
        print("  发音会经 /tts 缓存到 cache/tts/，同一个词只听一次就够")
        print("  按 Ctrl+C 停止")
        print("=" * 62)
        try:
            if "--open" in sys.argv:
                webbrowser.open(url)
            httpd.serve_forever()
        except KeyboardInterrupt:
            st = tts_stats()
            print("\n已停止。TTS 缓存：%d 个音频，共 %.1f MB" % (st["files"], st["mb"]))


if __name__ == "__main__":
    main()
