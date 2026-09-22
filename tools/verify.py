# -*- coding: utf-8 -*-
"""Verify the repaired hotspot data: residual damage patterns + readability samples."""
import json, io, os, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\harness工作区\spanish-reader"

pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))
allw = [w for p in pages for w in p["words"]]
words = [w for w in allw if not w.get("skip")]      # only clickable hotspots
print("pages: %d   hotspots: %d   clickable: %d   skipped(noise/table): %d" %
      (len(pages), len(allw), len(words), len(allw) - len(words)))

PATTERNS = {
    "å/ä/ö/ø (accent misread)": r"[åäöøÅÄÖØ]",
    "digit inside a word": r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]",
    "capital-I misread of l": r"^I[a-záéíóúüñ]",
    "unrepaired 'fi' likely ñ": r"^[a-záéíóúüñ]*fi[a-záéíóúüñ]*$",
    "leading i as ¿/¡": r"^i[,.]?[A-ZÁÉÍÓÚÜÑ]",
    "stray punctuation soup": r"[^\wÁÉÍÓÚÜÑáéíóúüñ .,;:!?¿¡'()\-]",
}
print("\n=== residual damage patterns ===")
for label, pat in PATTERNS.items():
    rx = re.compile(pat)
    hits = [w["t"] for w in words if rx.search(w["t"])]
    c = collections.Counter(hits)
    print("  %-28s %5d hits / %4d types   %s" % (label, len(hits), len(c),
                                                  ", ".join("%s(%d)" % (k, v) for k, v in c.most_common(6))))

with io.open(os.path.join(ROOT, "data", "_verify_samples.txt"), "w", encoding="utf-8") as f:
    for pno in (34, 50, 100, 150, 200, 250, 297, 302):
        p = next((x for x in pages if x["page"] == pno), None)
        if not p:
            continue
        f.write("\n" + "=" * 80 + "\nPAGE %d\n" % pno)
        for ln in p["lines"][:28]:
            f.write("  | %s\n" % ln["t"])
print("\nwrote data/_verify_samples.txt")

# hotspot geometry sanity: are boxes inside the page and non-degenerate?
bad = 0
for w in words:
    if not (0 <= w["x"] <= 1 and 0 <= w["y"] <= 1 and 0 < w["w"] <= 1 and 0 < w["h"] <= 1):
        bad += 1
print("out-of-range boxes: %d" % bad)
