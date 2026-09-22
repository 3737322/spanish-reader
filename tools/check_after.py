# -*- coding: utf-8 -*-
"""After repair: what is still unknown? Real Spanish, or junk from non-Spanish regions?"""
import json, io, os, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r"[\u3400-\u9fff]")
SPANISH = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+$")
ACC = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")

seed = json.load(io.open(os.path.join(ROOT, "data", "dict_seed.json"), encoding="utf-8"))
gloss = json.load(io.open(os.path.join(ROOT, "data", "lex_glossary.json"), encoding="utf-8"))
pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))

lex = set()
for k in seed:
    lex.add(k); lex.add(k.lower()); lex.add(k.capitalize())
for k in gloss:
    lex.add(k); lex.add(k.lower()); lex.add(k.capitalize())

cnt = collections.Counter()
first_seen = {}
for p in pages:
    for w in p["words"]:
        t = re.sub(r"^[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+$", "", w["t"])
        if not t:
            continue
        cnt[t] += 1
        first_seen.setdefault(t, (p["page"], w["t"]))

unknown = [(t, n) for t, n in cnt.most_common() if t not in lex and t.lower() not in lex and t.capitalize() not in lex]
print("distinct tokens: %d   unknown distinct: %d" % (len(cnt), len(unknown)))
tot = sum(cnt.values())
unk_tok = sum(n for _, n in unknown)
print("tokens: %d   unknown tokens: %d (%.1f%%)" % (tot, unk_tok, 100.0 * unk_tok / tot))

clean = [(t, n) for t, n in unknown if SPANISH.match(t)]
dirty = [(t, n) for t, n in unknown if not SPANISH.match(t)]
print("  of which pure-letter (plausible Spanish): %d types / %d tokens" % (len(clean), sum(n for _, n in clean)))
print("  non-letter junk: %d types / %d tokens" % (len(dirty), sum(n for _, n in dirty)))

out = []
out.append("=== top 300 unknown PURE-LETTER tokens (plausible Spanish, need attention) ===")
for t, n in clean[:300]:
    pg, raw = first_seen[t]
    out.append("  %-26s %5d   first p.%d  raw=%s" % (t, n, pg, raw))
out.append("")
out.append("=== top 80 unknown NON-LETTER tokens (junk from tables/diagrams) ===")
for t, n in dirty[:80]:
    out.append("  %-40s %5d   p.%d" % (t, n, first_seen[t][0]))

io.open(os.path.join(ROOT, "data", "_unknown_after.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\nwrote data/_unknown_after.txt")
