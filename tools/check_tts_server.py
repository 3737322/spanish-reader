# -*- coding: utf-8 -*-
"""
Verify the /tts cache endpoint.

    python tools/check_tts_server.py        (serve.py 必须在跑)

两类检查：

  * 确定性检查 —— 输入校验、HEAD 语义、响应头、静态资源不受影响。永远会跑。
  * 实拉检查   —— 真的向 Google 拉一个词，确认拿到的是有效 MP3、确认它落盘、
                  再确认第二次请求由磁盘命中且字节完全一致。

上游不可达时实拉部分会「跳过」而不是「失败」，所以离线也能用。
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = "http://127.0.0.1:8765"
TTS_DIR = os.path.join(ROOT, "cache", "tts")
TEST_WORD = "prueba"

fails = []
skipped = []


def ok(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def skip(msg):
    print("SKIP " + msg)
    skipped.append(msg)


def req(path, method="GET"):
    """Return (status, headers_with_lowercase_keys, body)."""
    r = urllib.request.Request(BASE + path, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def cache_path(word):
    return os.path.join(TTS_DIR,
                        hashlib.sha1(("es|" + word).encode("utf-8")).hexdigest()[:20] + ".mp3")


def is_mp3(data):
    """MPEG 音频帧同步：前 11 位全为 1。"""
    return len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


# --------------------------------------------------------------- 确定性检查
print("=== 输入校验 ===")
st, h, b = req("/tts")
ok(st == 400, "缺少 ?w= -> 400（实际 %s）" % st)

st, h, b = req("/tts?w=" + "a" * 200)
ok(st == 400, "超过 120 字符 -> 400（实际 %s）" % st)

st, h, b = req("/tts?w=" + urllib.parse.quote("../../etc/passwd"))
ok(st == 400, "路径穿越 -> 400（实际 %s）" % st)

st, h, b = req("/tts?w=" + urllib.parse.quote("<script>alert(1)</script>"))
ok(st == 400, "HTML 注入 -> 400（实际 %s）" % st)

print("\n=== HEAD 不触发下载 ===")
rare = "zzq" + hashlib.sha1(b"never-cached-probe").hexdigest()[:10]
st, h, b = req("/tts?w=" + rare, method="HEAD")
ok(st == 404, "HEAD 未缓存词 -> 404，不触发下载（实际 %s）" % st)
ok(len(b) == 0, "HEAD 返回空 body")

# ------------------------------------------------------------------ 实拉检查
print("\n=== 真实拉取 + 缓存往返 ===")
st, h, b = req("/tts?w=" + TEST_WORD)

if st == 502:
    skip("上游不可达（无网络），跳过实拉检查 —— 其余检查仍然有效")
else:
    ok(st == 200, "GET 一个词 -> 200（实际 %s）" % st)
    ok(is_mp3(b), "返回的是真实 MP3 音频（前两字节 %s）" % b[:2].hex())
    ok(len(b) > 1000, "音频大小合理：%d 字节" % len(b))

    first = b
    cp = cache_path(TEST_WORD)
    ok(os.path.exists(cp), "音频已落盘：cache/tts/%s" % os.path.basename(cp))
    if os.path.exists(cp):
        with open(cp, "rb") as f:
            ok(f.read() == first, "磁盘文件与响应字节完全一致")

    st2, h2, b2 = req("/tts?w=" + TEST_WORD)
    ok(st2 == 200, "第二次 GET -> 200（实际 %s）" % st2)
    ok(h2.get("x-tts-cache") == "hit",
       "第二次走缓存：X-TTS-Cache=%s" % h2.get("x-tts-cache"))
    ok(b2 == first, "两次返回字节完全一致（缓存没有损坏）")

    st3, h3, b3 = req("/tts?w=" + TEST_WORD, method="HEAD")
    ok(st3 == 200 and h3.get("x-tts-cache") == "hit", "HEAD 已缓存词 -> 200 hit")

    print("\n=== 长缓存响应头（否则浏览器会反复回源）===")
    ok(h.get("content-type") == "audio/mpeg", "Content-Type: %s" % h.get("content-type"))
    ok(h.get("cache-control") == "public, max-age=31536000, immutable",
       "Cache-Control: %s" % h.get("cache-control"))

    print("\n=== 不同词互不干扰 ===")
    st4, h4, b4 = req("/tts?w=gracias")
    if st4 == 200:
        ok(b4 != first, "另一个词拿到的是不同的音频")
        ok(cache_path("gracias") != cp, "两个词对应不同缓存文件")
    else:
        skip("第二个词拉取失败（%s），跳过" % st4)

print("\n=== /tts-stats ===")
st, h, b = req("/tts-stats")
ok(st == 200, "/tts-stats -> 200（实际 %s）" % st)
try:
    data = json.loads(b.decode("utf-8"))
except Exception as e:
    data = None
    ok(False, "stats 是合法 JSON：%s" % e)
if data:
    ok(data.get("files", 0) >= 1, "stats 统计到文件数：%s" % data.get("files"))
    ok(data.get("bytes", 0) > 1000, "stats 统计到字节数：%s" % data.get("bytes"))
    print("     %s" % json.dumps(data, ensure_ascii=False))

print("\n=== 静态资源不受 /tts 影响 ===")
for p, ct in (("/data/dict.json", "application/json"),
              ("/data/pages.json", "application/json"),
              ("/pages/page_0034.jpg", "image/jpeg"),
              ("/web/index.html", "text/html")):
    st, h, b = req(p)
    ok(st == 200 and ct in (h.get("content-type") or ""),
       "%s -> %s %s" % (p, st, h.get("content-type")))

print("\n" + "=" * 60)
if skipped:
    print("跳过 %d 项：%s" % (len(skipped), "; ".join(skipped)))
if fails:
    print("%d 项失败" % len(fails))
    sys.exit(1)
print("全部通过")
