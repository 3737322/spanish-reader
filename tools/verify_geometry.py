# -*- coding: utf-8 -*-
"""
Geometry / alignment verification.

Hotspots are stored normalised against the OCR source image (pages_raw, full
resolution).  The browser scales them by the *display* image (pages/, 1600px).
That only lines up if both share an aspect ratio, so check it for every page,
and sanity-check that boxes land inside the text area and form real lines.
"""
import json, io, os, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\harness工作区\spanish-reader"

pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))
sizes = {s["file"]: s for s in json.load(io.open(os.path.join(ROOT, "pages", "_sizes.json"), encoding="utf-8-sig"))}

bad_ratio = []
missing = []
for p in pages:
    s = sizes.get(p["file"])
    if not s:
        missing.append(p["file"])
        continue
    a_ocr = p["ocr_w"] / p["ocr_h"]
    a_img = s["w"] / s["h"]
    if abs(a_ocr - a_img) > 0.002:
        bad_ratio.append((p["file"], round(a_ocr, 5), round(a_img, 5)))

print("pages: %d   display images matched: %d   missing: %d" %
      (len(pages), len(pages) - len(missing), len(missing)))
if missing:
    print("  MISSING display images:", missing[:10])
print("aspect-ratio mismatches (>0.2%%): %d" % len(bad_ratio))
for f, a, b in bad_ratio[:10]:
    print("   %s  ocr=%.5f  display=%.5f" % (f, a, b))

# box plausibility
out_of_frame = 0
tiny = 0
heights = []
for p in pages:
    for w in p["words"]:
        if w["x"] < 0 or w["y"] < 0 or w["x"] + w["w"] > 1.001 or w["y"] + w["h"] > 1.001:
            out_of_frame += 1
        if w["w"] * w["h"] < 1e-7:
            tiny += 1
        heights.append(w["h"])
heights.sort()
print("\nword boxes: %d" % len(heights))
print("  outside the page frame: %d" % out_of_frame)
print("  degenerate (near-zero area): %d" % tiny)
print("  height median=%.5f  p05=%.5f  p95=%.5f" %
      (heights[len(heights) // 2], heights[int(len(heights) * .05)], heights[int(len(heights) * .95)]))

# lines: do the words of a line share a baseline, and does the line box contain them?
by_id = {}
for p in pages:
    for w in p["words"]:
        by_id[w["id"]] = w
inside = outside = 0
widths = []
for p in pages:
    for ln in p["lines"]:
        pno, li = ln["first"].split(":")[:2]
        ws = [w for k, w in by_id.items() if k.startswith("%s:%s:" % (pno, li))]
        if not ws:
            continue
        widths.append(ln["w"])
        for w in ws:
            if (ln["x"] - 1e-6 <= w["x"] and w["x"] + w["w"] <= ln["x"] + ln["w"] + 1e-6 and
                    ln["y"] - 1e-6 <= w["y"] and w["y"] + w["h"] <= ln["y"] + ln["h"] + 1e-6):
                inside += 1
            else:
                outside += 1
print("\nline boxes: %d   words inside their line box: %d   outside: %d" %
      (len(widths), inside, outside))

# a concrete page, to eyeball reading order and text quality
for pno in (34, 100):
    p = next(x for x in pages if x["page"] == pno)
    print("\n=== page %d (%s, %dx%d OCR) ===" % (pno, p["file"], p["ocr_w"], p["ocr_h"]))
    for ln in p["lines"][:10]:
        print("   y=%.3f x=%.3f | %s" % (ln["y"], ln["x"], ln["t"]))
