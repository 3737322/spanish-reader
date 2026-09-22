# -*- coding: utf-8 -*-
"""Explore: rare-character contexts (to derive repair rules) + locate vocabulary-list pages."""
import json, io, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\harness工作区\spanish-reader"

def load(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)

pages = load(os.path.join(ROOT, "data", "pages.json"))

# ---------- 1. contexts for rare characters ----------
print("=== sample tokens per rare character ===")
for ch in "åäö6ßæøþðžšç":
    hits = []
    for p in pages:
        for w in p["words"]:
            if ch in w["t"]:
                hits.append((w["t"], p["page"]))
    if not hits:
        continue
    c = collections.Counter(t for t, _ in hits)
    print("\n'%s'  total=%d  types=%d" % (ch, len(hits), len(c)))
    print("   ", ", ".join("%s(%d)" % (t, n) for t, n in c.most_common(18)))

# ---------- 2. find vocabulary-list pages ----------
POS_ABBR = {"m", "f", "tr", "intr", "prnl", "adj", "adv", "pron", "prep", "conj",
            "interj", "art", "num", "mf", "m.", "f.", "tr.", "loc.adv", "loc"}
print("\n\n=== candidate vocabulary-list pages (POS-abbreviation density) ===")
scored = []
for p in pages:
    toks = [re.sub(r"[^A-Za-z.]", "", w["t"]).lower() for w in p["words"]]
    toks = [t for t in toks if t]
    if len(toks) < 30:
        continue
    npos = sum(1 for t in toks if t in POS_ABBR)
    ratio = npos / len(toks)
    if npos >= 12 and ratio > 0.10:
        scored.append((ratio, npos, len(toks), p["page"]))
scored.sort(reverse=True)
for ratio, npos, ntot, pg in scored[:40]:
    print("  page %3d   pos=%3d / %3d  ratio=%.2f" % (pg, npos, ntot, ratio))
print("total candidate pages:", len(scored))

# ---------- 3. dump one vocabulary page ----------
if scored:
    pg = scored[0][3]
    p = next(x for x in pages if x["page"] == pg)
    print("\n\n=== page %d : latin lines ===" % pg)
    for ln in p["lines"]:
        print("  |", ln["t"])
    print("\n=== page %d : chinese text ===" % pg)
    print(" ", p.get("zh", "")[:1500])
