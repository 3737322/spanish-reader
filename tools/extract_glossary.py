# -*- coding: utf-8 -*-
"""
Build a canonical Spanish lexicon from the book's GLOSARIO (master word index).

Each glossary line looks like one of:
    abrigarse tr. ;prnl.
    abuelo, la m..f.
    a la derecha loc.adv.
    activo, va ac(j.          <- OCR damage in the POS tag
The headword is everything before the POS tag; this module finds that boundary
fuzzily and then derives the obvious inflected forms (base + feminine/plural).
"""
import json, io, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POS_SET = {"m", "f", "mf", "tr", "intr", "prnl", "adj", "adv", "pron", "prep",
           "conj", "interj", "art", "num", "inf", "pp", "v", "s", "loc",
           "cop", "pl", "vi", "vt"}
VOWELS = set("aeiouáéíóúü")
WORD_OK = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ,()'\-]*$")
ACC = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")


def letters(tok):
    return re.sub(r"[^a-záéíóúüñ]", "", tok.lower())


def edist(a, b):
    if abs(len(a) - len(b)) > 2:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def is_pos_token(tok):
    lf = letters(tok)
    if not lf:
        return True
    if lf.startswith("loc"):
        return True
    if lf in POS_SET:
        return True
    if re.search(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", tok) and len(lf) <= 5:
        for p in POS_SET:
            if len(p) >= 3 and edist(lf, p) <= 1:
                return True
    return False


def plauible(tok):
    if not WORD_OK.match(tok):
        return False
    lf = letters(tok)
    if len(lf) < 2:
        return False
    return any(c in VOWELS for c in lf) or all(c in "y" for c in lf)


def variants(head):
    """From 'abuelo, la' / 'acercar(se)' derive extra surface forms."""
    out = set()
    base = head.strip().strip(",")
    base = re.sub(r"\(.*?\)", "", base).strip()
    if not base:
        return out
    out.add(base)
    out.add(base + "se") if "(se)" in head else None
    parts = [p.strip() for p in head.split(",")]
    if len(parts) == 2 and parts[0] and parts[1]:
        b, sec = parts[0], parts[1]
        if 1 <= len(sec) <= 3:
            if b[-1:].lower() in "aeiouáéíóú":
                if len(sec) == 2:
                    out.add(b[:-2] + sec if len(b) > 2 else b[:-1] + sec)
                out.add(b[:-1] + sec)
            else:
                out.add(b[:-1] + sec)
                out.add(b[:-1] + sec[-1])
                out.add((b[:-1] + sec[-1]).translate(ACC))
    return {v for v in out if plauible(v)}


def parse_line(text):
    toks = text.split()
    head_parts = []
    for t in toks:
        if is_pos_token(t) and head_parts:
            break
        head_parts.append(t)
    head = " ".join(head_parts).strip(" ;:,")
    if not head:
        return None
    # a headword is at most 3 words; drop trailing junk
    words = [w for w in head.split() if plauible(w)]
    if not words:
        return None
    if len(words) > 3:
        words = words[:3]
    return " ".join(words)


def main():
    pages = json.load(io.open(os.path.join(ROOT, "data", "pages_ocr.json"), encoding="utf-8"))
    lo, hi = 294, 304
    lex = {}
    raw_entries = 0
    for p in pages:
        if not (lo <= p["page"] <= hi):
            continue
        for ln in p["lines"]:
            t = ln["t"].strip()
            if not t or t.upper() == "GLOSARIO":
                continue
            head = parse_line(t)
            if not head:
                continue
            raw_entries += 1
            for v in variants(head):
                lex.setdefault(v, {"pos": None, "page": p["page"], "raw": t})

    print("glossary lines parsed:", raw_entries)
    print("distinct surface forms:", len(lex))

    bad = [v for v in lex if not re.match(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]*$", v)]
    print("suspicious entries:", len(bad))
    for v in bad[:25]:
        print("   ?", repr(v), "  <-", lex[v]["raw"])

    print("\nsample:")
    for v in list(sorted(lex))[:15]:
        print("   ", v)
    print("   ...")
    for v in list(sorted(lex))[-15:]:
        print("   ", v)

    dst = os.path.join(ROOT, "data", "lex_glossary.json")
    json.dump(lex, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("\nwrote", dst)


if __name__ == "__main__":
    main()
