# -*- coding: utf-8 -*-
"""Print Windows-OCR results side by side so recognition quality can be judged."""
import json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "ocr_all.json")
which = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0, 1]

with io.open(path, encoding="utf-8-sig") as f:
    recs = json.load(f)
if isinstance(recs, dict):
    recs = [recs]
print("records:", len(recs))

for i in which:
    if i >= len(recs):
        continue
    r = recs[i]
    print("\n" + "=" * 78)
    print("PAGE %s   %sx%s" % (r["file"], r["w"], r["h"]))
    for tag, lines in r["ocr"].items():
        print("\n--- %s : %d lines ---" % (tag, len(lines)))
        for ln in lines[:40]:
            print("  |", ln["text"])
        if len(lines) > 40:
            print("  ... (%d more lines)" % (len(lines) - 40))
