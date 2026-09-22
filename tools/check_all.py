# -*- coding: utf-8 -*-
"""
Run every check in one go.

    python tools/check_all.py

Covers the data pipeline output, the hotspot geometry, both reader builds, the
verb table, and the /tts cache endpoint.  The two reader checks need Node; the
TTS endpoint check needs the server to be running (it is skipped otherwise).
"""
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = "http://127.0.0.1:8765"

failures = []


def server_up():
    try:
        urllib.request.urlopen(BASE + "/web/index.html", timeout=5)
        return True
    except Exception:
        return False


def run(label, argv, need=None):
    if need and not need():
        print("\n" + "=" * 78)
        print("### SKIP %s (requirement not met)" % label)
        return
    print("\n" + "=" * 78)
    print("### %s" % label)
    print("=" * 78)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(argv, env=env, cwd=ROOT)
    if r.returncode != 0:
        failures.append(label)


run("字典与分词覆盖率", [sys.executable, os.path.join(HERE, "check_after.py")])
run("热区几何对齐", [sys.executable, os.path.join(HERE, "verify_geometry.py")])
run("残留 OCR 错误统计", [sys.executable, os.path.join(HERE, "verify.py")])
run("变位表交叉验证", [sys.executable, os.path.join(HERE, "check_irregular.py")])
run("前端静态检查 + 查词回放", ["node", os.path.join(HERE, "check_ui.js")])
run("服务器版阅读器行为", ["node", os.path.join(HERE, "check_server_mode.js")])
run("便携版阅读器行为", ["node", os.path.join(HERE, "check_portable.js")])
run("/tts 缓存端点", [sys.executable, os.path.join(HERE, "check_tts_server.py")], need=server_up)

print("\n" + "=" * 78)
if failures:
    print("FAILED: " + ", ".join(failures))
    sys.exit(1)
print("全部自检通过。")
