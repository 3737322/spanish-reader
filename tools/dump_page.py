# -*- coding: utf-8 -*-
"""Dump one page's raw OCR (both engines, with pixel boxes) into a readable file."""
import json, io, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

raw = json.load(io.open(os.path.join(ROOT, "data", "ocr_all.json"), encoding="utf-8-sig"))
want = [int(x) for x in sys.argv[1].split(",")]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data", "_dump.txt")

lines = []
for rec in raw:
    pno = int("".join(c for c in rec["file"] if c.isdigit()))
    if pno not in want:
        continue
    lines.append("=" * 90)
    lines.append("PAGE %d  (%sx%s)" % (pno, rec["w"], rec["h"]))
    for tag in ("en-GB", "zh-Hans-CN"):
        ls = rec["ocr"].get(tag) or []
        lines.append("\n--- %s : %d lines ---" % (tag, len(ls)))
        for ln in ls:
            ws = ln["words"]
            if not ws:
                continue
            y = min(w["y"] for w in ws)
            x = min(w["x"] for w in ws)
            lines.append("  y=%5d x=%5d | %s" % (y, x, ln["text"]))
    # positional interleave of Chinese words to understand column order
    lines.append("\n--- zh-Hans-CN word boxes (x-sorted) ---")
    zs = [w for ln in (rec["ocr"].get("zh-Hans-CN") or []) for w in ln["words"]]
    zs.sort(key=lambda w: (round(w["y"] / 40), w["x"]))
    for w in zs[:200]:
        lines.append("   x=%5d y=%5d  %s" % (w["x"], w["y"], w["t"]))

io.open(out, "w", encoding="utf-8").write("\n".join(lines))
print("wrote", out, len(lines), "lines")
