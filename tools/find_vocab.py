# -*- coding: utf-8 -*-
"""Where do POS abbreviations live? Locate the book's vocabulary / verb-index pages."""
import json, io, os, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\harness工作区\spanish-reader"
pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))

TARGETS = ["prnl", "adj", "tr", "intr", "loc.adv", "m.", "f.", "pron"]
per_page = collections.defaultdict(collections.Counter)
for p in pages:
    for w in p["words"]:
        t = w["t"].lower().strip(".,;:()[]")
        if t in TARGETS:
            per_page[p["page"]][t] += 1

rows = []
for pg, c in per_page.items():
    rows.append((sum(c.values()), pg, c))
rows.sort(reverse=True)
print("=== pages with most POS abbreviations ===")
for tot, pg, c in rows[:30]:
    print("  page %3d  total=%3d  %s" % (pg, tot, dict(c.most_common(8))))

print("\n=== UNIDAD heading pages ===")
unid = [p["page"] for p in pages if any(re.match(r"^UNIDAD", ln["t"].strip(), re.I) for ln in p["lines"])]
print(" ", unid)

# dump the most promising vocabulary page
if rows:
    pg = rows[0][1]
    p = next(x for x in pages if x["page"] == pg)
    print("\n\n===== PAGE %d : latin lines =====" % pg)
    for ln in p["lines"]:
        print("  |", ln["t"])
    print("\n===== PAGE %d : chinese =====" % pg)
    print(" ", p.get("zh", "")[:2000])
