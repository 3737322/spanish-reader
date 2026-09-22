# -*- coding: utf-8 -*-
"""Print pages.json line text for a page range (into a file, for inspection)."""
import json, io, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))

a, b = (int(x) for x in sys.argv[1].split("-"))
out = sys.argv[2]
buf = []
for p in pages:
    if a <= p["page"] <= b:
        buf.append("### PAGE %d  (words=%d lines=%d)" % (p["page"], len(p["words"]), len(p["lines"])))
        for ln in p["lines"]:
            buf.append("   %s" % ln["t"])
io.open(out, "w", encoding="utf-8").write("\n".join(buf))
print("wrote", out, len(buf), "lines")
