# -*- coding: utf-8 -*-
"""Map the extent of the book's master vocabulary index (总词汇表) and count entries."""
import json, io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = json.load(io.open(os.path.join(ROOT, "data", "ocr_all.json"), encoding="utf-8-sig"))
pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))

POS = re.compile(r"\b(m|f|mf|tr|intr|prnl|adj|adv|pron|prep|conj|interj|art|num|loc\.adv|loc\.adc|p\.p|v\.cop|s)\.?\s*$", re.I)
WORD = re.compile(r"^[a-záéíóúüñ][a-záéíóúüñA-Za-z,()\-' ]*$")

print("=== pages 275-305 : line/entry profile ===")
for p in pages:
    if p["page"] < 275:
        continue
    lines = [ln["t"].strip() for ln in p["lines"]]
    hits = 0
    alpha = 0
    for t in lines:
        if not t:
            continue
        if re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", t):
            alpha += 1
        if POS.search(t) and len(t) < 40:
            hits += 1
    print("  page %3d  lines=%3d  latin=%3d  posish=%3d" % (p["page"], len(lines), alpha, hits))

print("\n=== first / last lines of the index pages ===")
for p in pages:
    if 285 <= p["page"] <= 305:
        ls = [l["t"] for l in p["lines"]]
        if not ls:
            continue
        print("  page %3d  first=%-30s last=%s" % (p["page"], ls[0][:30], ls[-1][:40]))
