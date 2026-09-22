# -*- coding: utf-8 -*-
"""
Repair Windows-OCR text damage in the extracted hotspots.

The OCR engine's Spanish errors are systematic, not random:

    å -> á      (mås, estån, gramåtica)        ~890 occurrences
    ö -> ó      (dönde, estaciön)              ~320
    6 -> ó      (d6nde, grabaci6n)             ~340
    fi -> ñ     (espafiol, afios, mafiana)
    I -> l      (Ios, Ilas, Ilevar)
    0/1 digits  (Man010 -> Manolo)
    i,X -> ¿X   (i,C6mo -> ¿Cómo)
    dropped accents (dias -> días, mas -> más)

Repair is scored against a trust-ranked lexicon.  Two rules matter a lot:

  * A candidate containing characters that cannot occur in Spanish (å, ö, a
    digit inside a word) is penalised so heavily that any legal alternative
    wins.  Without this, the corpus tier "validates" its own garbage and
    "estå" survives because it is frequent.
  * A candidate is accepted when the candidate *or its singular* is known, so
    "afios" resolves to "años" via the known singular "año".

Tiers: high = hand-written seed dictionary, mid = book GLOSARIO,
verbs = generated conjugations (+ curated irregulars), low = corpus-frequent.
"""
import json, io, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPANISH = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+$")
ACC = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")

CHAR_FIX = {"å": "á", "ä": "á", "ö": "ó", "ø": "ó", "è": "é", "ì": "í",
            "ò": "ó", "ù": "ú", "ç": "c", "’": "'", "´": "'",
            # the same misreads in capitals: GRAMÅTICA / ÅNGELA etc.
            "Å": "Á", "Ä": "Á", "Ö": "Ó", "Ø": "Ó", "È": "É", "Ì": "Í",
            "Ò": "Ó", "Ù": "Ú", "Ç": "C"}
DIGIT_FIX = {"0": "o", "1": "l", "5": "s", "6": "ó", "3": "e", "4": "a", "8": "o"}
DIGIT_FIX_UP = {"0": "O", "1": "L", "5": "S", "6": "Ó", "3": "E", "4": "A", "8": "O"}
INNER_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜÑáéíóúüñ")

NON_WORDS = set("""adj adv tr intr prnl pron prep conj interj art num inf pp cop mf loc
unidad unidades sociocultural glosario vocabulario leccion lecciones
m f tr. intr. prnl. adj. adv. pron. prep. conj. art. num.
loc.adv loc.adj loc.conj loc.prep loc.ado loc.aclc loc.aclv loc.adt loc.coqj loc.couj
p.p v.cop""".split())

ILLEGAL = -1000
SCORE = {"high": 400, "mid": 300, "verb": 280, "accent": 250, "low": 120, "raw": 50}


def strip_punct(w):
    """Strip surrounding punctuation only.

    Must be \\w-based (Unicode-aware): the OCR-produced letters å/ä/ö/ø are real
    letters, and treating them as punctuation silently truncates "estå" to
    "est", which then looks like a perfectly valid corpus word.
    """
    return re.sub(r"^[^\w]+|[^\w]+$", "", w, flags=re.UNICODE)


def punct_fix(w):
    """The engine renders the inverted marks ¿ / ¡ as i, G', o', o: and friends.

    The apostrophe/colon is required: without it "GRAMATICA" would match the
    G rule and become "¿RAMATICA".
    """
    m = re.match(r"^i[,.]?([A-ZÁÉÍÓÚÜÑ].*)$", w)
    if m:
        return "¿" + m.group(1)
    m = re.match(r"^[Gg]['’´]([A-ZÁÉÍÓÚÜÑ].*)$", w)
    if m:
        return "¿" + m.group(1)
    m = re.match(r"^[oO0][•:.,'’]([A-ZÁÉÍÓÚÜÑ].*)$", w)
    if m:
        return "¿" + m.group(1)
    return w


def char_fix(w):
    return "".join(CHAR_FIX.get(c, c) for c in w)


def digit_fix(w):
    # all-caps words need capital replacements: GRABACI6N -> GRABACIÓN
    table = DIGIT_FIX_UP if (w.isupper() and any(c.isalpha() for c in w)) else DIGIT_FIX
    out = []
    for i, c in enumerate(w):
        if c in table and 0 < i < len(w) - 1 and w[i - 1] in INNER_OK and w[i + 1] in INNER_OK:
            out.append(table[c])
        else:
            out.append(c)
    return "".join(out)


def cap_fix(w):
    if w.startswith("Il") and len(w) > 2 and w[2:3].islower():
        return "ll" + w[2:]
    if w.startswith("I") and len(w) > 1 and w[1:2].islower():
        return "l" + w[1:]
    return w


VOWELS = set("aeiouáéíóúüAEIOUÁÉÍÓÚÜ")


def fi_variants(w):
    """Yield w with a 'fi' replaced by 'ñ'.

    Only vowel+fi+vowel is rewritten: that is the shape the engine always
    mis-reads (espafiol, mafiana, afios, acompafiar), while it leaves genuine
    'fi' words alone (oficina, fiesta, dificil, suficiente, infinitivos).
    """
    out, start = [], 0
    while True:
        i = w.find("fi", start)
        if i < 0:
            break
        if i > 0 and w[i - 1] in VOWELS and i + 2 < len(w) and w[i + 2] in VOWELS:
            out.append(w[:i] + "ñ" + w[i + 2:])
        start = i + 1
    return out


def all_candidates(w):
    """Return (text, trusted) pairs in preference order.

    trusted=True means this rewrite is unambiguous for this OCR engine, so it
    may outrank the untouched token at equal lexicon evidence.
    """
    out, seen = [], set()

    def add(t, trusted):
        if t and t not in seen:
            seen.add(t)
            out.append((t, trusted))

    add(w, False)
    cf = char_fix(w)
    if cf != w:
        add(cf, True)
    for base in (w, cf):
        df = digit_fix(base)
        if df != base:
            add(df, True)
        um = base.replace("ü", "ú")
        if um != base:
            add(um, False)
        for v in fi_variants(base):
            add(v, True)
        cx = cap_fix(base)
        if cx != base:
            add(cx, False)      # trusted only when the result is a known word
    return out


def singulars(w):
    out = []
    low = w.lower()
    if low.endswith("es") and len(w) > 3:
        out.append(w[:-2])
    if low.endswith("s") and len(w) > 2:
        out.append(w[:-1])
    return out


def plurals(w):
    out = [w + "s", w + "es"]
    if w.lower().endswith("z"):
        out.append(w[:-1] + "ces")
    return out


def gender_forms(w):
    """llegado -> llegada, ocupados -> ocupadas: the book is full of them."""
    out = []
    low = w.lower()
    if low.endswith("o"):
        out.append(w[:-1] + "a")
    elif low.endswith("os"):
        out.append(w[:-2] + "as")
    return out


def strip_acc(w):
    return w.translate(ACC)


def build_lexicon(seed, glossary, verbs, corpus_counter, min_freq=3):
    high = set()
    for k in seed:
        k = k.strip()
        if k and SPANISH.match(k):
            high |= {k, k.lower(), k.capitalize()}
    mid = set()
    for k in glossary:
        if k and SPANISH.match(k):
            mid |= {k, k.lower(), k.capitalize()}
    vset = set(verbs)

    def repair_against(w, lex):
        for c, _trusted in all_candidates(w):
            if c in lex:
                return c
            for s in singulars(c):
                if s in lex:
                    return c
        return None

    strong = high | mid | vset
    low, fixed_low = {}, 0
    for tok, n in corpus_counter.items():
        # length >= 3: two-letter tokens ("ZI", "IA") are diagram noise, and a
        # self-referential corpus tier would otherwise "validate" them.
        if n < min_freq or len(tok) < 3 or not SPANISH.match(tok):
            continue
        r = repair_against(tok, strong)
        if r and r != tok:
            fixed_low += 1
        low[r or tok] = n

    base = high | mid | vset | set(low)
    expanded = set(base)
    for w in base:
        expanded |= set(plurals(w))
        expanded |= set(gender_forms(w))
    return high, mid, vset, low, expanded, dict(fixed_low=fixed_low)


def repair_token(tok, tiers, accent_index):
    core = strip_punct(tok)
    if not core:
        return tok, "punct"
    if core.lower() in NON_WORDS or (len(core) == 1 and core.lower() in "iill"):
        return tok, "skip"
    prefix = ""
    fixed_core = punct_fix(core)
    if fixed_core[:1] in "¿¡":       # keep repairing the text after the mark
        prefix, core = fixed_core[0], fixed_core[1:]
    if not core:
        return tok.replace(strip_punct(tok), fixed_core), "punct"
    best, how, best_key = None, "raw", None
    for rank, (cand, trusted) in enumerate(all_candidates(core)):
        if cand in tiers["high"]:
            base, how2 = SCORE["high"], "high"
        elif cand in tiers["mid"]:
            base, how2 = SCORE["mid"], "mid"
        elif cand in tiers["verb"]:
            base, how2 = SCORE["verb"], "verb"
        elif cand in tiers["low"]:
            base, how2 = SCORE["low"], "low"
        else:
            # Accent restoration only makes sense for a candidate that has no
            # accents yet; otherwise "están" would be "restored" to "estan".
            if strip_acc(cand) == cand:
                acc = accent_index.get(cand.lower())
            else:
                acc = None
            if acc and len(acc) == 1:
                cand = next(iter(acc))
                base, how2 = SCORE["accent"], "accent"
                if cand in tiers["high"] or cand in tiers["mid"] or cand in tiers["verb"]:
                    base, how2 = SCORE["mid"], "mid"
            else:
                base, how2 = SCORE["raw"], "raw"
        if not SPANISH.match(cand):
            base += ILLEGAL
        if not trusted and cand != core:
            # a shape-only rewrite (e.g. capital I -> l) is only believable
            # when the result is actually a word of the language
            trusted = cand in tiers["high"] or cand in tiers["mid"] or cand in tiers["verb"]
        key = (base, 1 if trusted else 0, -rank)
        if best_key is None or key > best_key:
            best, how, best_key = cand, how2, key
    if best is None:
        return tok, "raw"
    out = tok.replace(strip_punct(tok), prefix + best)
    # very short tokens that no tier recognises are diagram/table noise ("ZI", "A")
    if how == "raw" and len(best) <= 2:
        return out, "skip"
    return out, how


JUNK_CHARS = set("$&*+@#%{}\\|<>~^=_")


def looks_like_diagram_noise(tok):
    """Long symbol-laden strings come from the conjugation tables, not from prose."""
    core = strip_punct(tok)
    # no Spanish word contains a digit next to letters ("4stiáJJd", "Valk2nte")
    if re.search(r"[0-9]", core) and re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}", core):
        return True
    if len(core) < 6:
        return False
    if JUNK_CHARS & set(core):
        return True
    letters = sum(1 for c in core if c.isalpha())
    return letters / max(len(core), 1) < 0.7


def load_tiers():
    seed = json.load(io.open(os.path.join(ROOT, "data", "dict_seed.json"), encoding="utf-8"))
    glossary = json.load(io.open(os.path.join(ROOT, "data", "lex_glossary.json"), encoding="utf-8"))
    vpath = os.path.join(ROOT, "data", "lex_verbs.json")
    verbs = json.load(io.open(vpath, encoding="utf-8")) if os.path.exists(vpath) else {}
    return seed, glossary, verbs


def main():
    seed, glossary, verbs = load_tiers()
    pages = json.load(io.open(os.path.join(ROOT, "data", "pages_ocr.json"), encoding="utf-8"))

    counter = collections.Counter()
    for p in pages:
        for w in p["words"]:
            c = strip_punct(w["t"])
            if c:
                counter[c] += 1

    high, mid, vset, low, lex, stats = build_lexicon(seed, glossary, verbs, counter)
    print("lexicon: high=%d mid=%d verbs=%d low=%d expanded=%d" %
          (len(high), len(mid), len(vset), len(low), len(lex)))
    print("corpus forms already resolved by a stronger tier: %d" % stats["fixed_low"])

    tiers = {"high": high, "mid": mid, "verb": vset, "low": low}
    accent_index = collections.defaultdict(set)
    for w in lex:
        accent_index[strip_acc(w).lower()].add(w)

    how_counter = collections.Counter()
    changed = collections.Counter()
    skipped = 0
    for p in pages:
        for w in p["words"]:
            if looks_like_diagram_noise(w["t"]):
                w["skip"] = 1
                skipped += 1
                how_counter["skip"] += 1
                continue
            new, how = repair_token(w["t"], tiers, accent_index)
            if how == "skip":
                w["skip"] = 1
                skipped += 1
            if new != w["t"]:
                changed[(w["t"], new)] += 1
                w["t"] = new
            how_counter[how] += 1
        for ln in p["lines"]:
            pno, li = ln["first"].split(":")[0], ln["first"].split(":")[1]
            ws = [w for w in p["words"] if w["id"].startswith("%s:%s:" % (pno, li)) and not w.get("skip")]
            if ws:
                ln["t"] = " ".join(w["t"] for w in ws)

    tot = sum(how_counter.values())
    print("repair source:", dict(how_counter))
    print("non-word markers skipped: %d" % skipped)
    print("tokens rewritten: %d (%.1f%%)" % (sum(changed.values()), 100.0 * sum(changed.values()) / max(tot, 1)))
    print("weighted confidence: %.1f%%" %
          (100.0 * (how_counter["high"] + how_counter["mid"] + how_counter["verb"] +
                    how_counter["accent"] + how_counter["low"]) / max(tot, 1)))

    dst = os.path.join(ROOT, "data", "pages.json")
    json.dump(pages, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("wrote", dst, "(%.2f MB)" % (os.path.getsize(dst) / 1048576))

    with io.open(os.path.join(ROOT, "data", "_repair_pairs.txt"), "w", encoding="utf-8") as f:
        for (a, b), n in changed.most_common(400):
            f.write("%-30s -> %-30s %d\n" % (a, b, n))
    print("distinct repair pairs:", len(changed))


if __name__ == "__main__":
    main()
