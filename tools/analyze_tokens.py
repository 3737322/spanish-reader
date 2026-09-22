# -*- coding: utf-8 -*-
"""How good is the OCR vocabulary? Measure dictionary coverage and list unknowns."""
import json, io, os, re, sys, unicodedata, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACC = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")


def norm(w):
    w = w.lower().translate(ACC)
    w = re.sub(r"^[^a-z]+|[^a-z]+$", "", w)
    return w


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


pages = load(os.path.join(ROOT, "data", "pages.json"))
d = load(os.path.join(ROOT, "data", "dict_seed.json"))
lex = set()
for k in d:
    lex.add(norm(k))

tokens = []
for p in pages:
    for w in p["words"]:
        t = norm(w["t"])
        if t:
            tokens.append(t)

c = collections.Counter(tokens)
print("total tokens: %d   unique: %d" % (len(tokens), len(c)))
known = sum(v for k, v in c.items() if k in lex)
print("dictionary coverage (tokens): %.1f%%  (%d/%d)" % (100.0 * known / len(tokens), known, len(tokens)))
types_known = sum(1 for k in c if k in lex)
print("dictionary coverage (types):  %.1f%%  (%d/%d)" % (100.0 * types_known / len(c), types_known, len(c)))

print("\n=== top 60 unknown tokens ===")
unk = [(k, v) for k, v in c.most_common() if k not in lex]
for k, v in unk[:60]:
    print("  %-22s %5d" % (k, v))

print("\n=== suspicious characters present in tokens ===")
bad = collections.Counter()
for k, v in c.items():
    for ch in k:
        if ch not in "abcdefghijklmnopqrstuvwxyz":
            bad[ch] += v
print(" ", bad.most_common(30))

print("\n=== tokens containing rare latin-extended letters (likely OCR noise) ===")
odd = [(k, v) for k, v in c.most_common() if re.search(r"[åæøðþßšžčñ]", k)]
for k, v in odd[:40]:
    print("  %-22s %5d" % (k, v))

json.dump({"unknown": unk[:3000]}, io.open(os.path.join(ROOT, "data", "_unknown.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("\nwrote data/_unknown.json")
