# -*- coding: utf-8 -*-
"""
Spanish verb morphology, for two purposes:
  1. recognition  - every inflected form joins the repair lexicon
  2. lemmatisation - clicking "tengo" should resolve to the entry for "tener"

Regular endings are generated here; stem changes (e->ie, o->ue, e->i, o->u) and
spelling adjustments (-car/-gar/-zar, -ger/-gir, -guir) are handled too.  Truly
irregular verbs are merged in from data/lex_irregular.json when present.
"""
import json, io, os, sys

ROOT = r"C:\harness工作区\spanish-reader"

AR = {
    "pres.": ["o", "as", "a", "amos", "áis", "an"],
    "pret.": ["é", "aste", "ó", "amos", "asteis", "aron"],
    "imp.": ["aba", "abas", "aba", "ábamos", "abais", "aban"],
    "fut.": ["é", "ás", "á", "emos", "éis", "án"],
    "cond.": ["ía", "ías", "ía", "íamos", "íais", "ían"],
    "subj.": ["e", "es", "e", "emos", "éis", "en"],
}
ER = {
    "pres.": ["o", "es", "e", "emos", "éis", "en"],
    "pret.": ["í", "iste", "ió", "imos", "isteis", "ieron"],
    "imp.": ["ía", "ías", "ía", "íamos", "íais", "ían"],
    "fut.": ["é", "ás", "á", "emos", "éis", "án"],
    "cond.": ["ía", "ías", "ía", "íamos", "íais", "ían"],
    "subj.": ["a", "as", "a", "amos", "áis", "an"],
}
IR = {
    "pres.": ["o", "es", "e", "imos", "ís", "en"],
    "pret.": ["í", "iste", "ió", "imos", "isteis", "ieron"],
    "imp.": ["ía", "ías", "ía", "íamos", "íais", "ían"],
    # NOTE: the future endings are the same for -ar/-er/-ir (vivir -> viviremos).
    # They used to be written as imos/ís/en here, which silently meant that no
    # -ir future form was ever generated.
    "fut.": ["é", "ás", "á", "emos", "éis", "án"],
    "cond.": ["ía", "ías", "ía", "íamos", "íais", "ían"],
    "subj.": ["a", "as", "a", "amos", "áis", "an"],
}
PERSONS = ["1s", "2s", "3s", "1p", "2p", "3p"]
# boot forms (stem change applies): 1s,2s,3s,3p  -> indices 0,1,2,5
BOOT = [0, 1, 2, 5]


def stem_change(stem, kind):
    """Apply the last-vowel stem change of an infinitive stem."""
    for i in range(len(stem) - 1, -1, -1):
        c = stem[i]
        if c in "eé":
            if kind == "e:ie":
                return stem[:i] + "ie" + stem[i + 1:]
            if kind == "e:i":
                return stem[:i] + "i" + stem[i + 1:]
        if c in "oó":
            if kind == "o:ue":
                return stem[:i] + "ue" + stem[i + 1:]
            if kind == "o:u":
                return stem[:i] + "u" + stem[i + 1:]
        if c in "u":
            if kind == "u:ue":
                return stem[:i] + "ue" + stem[i + 1:]
    return stem


def spelling(stem, end, form_kind):
    """Orthographic adjustments required by Spanish spelling rules."""
    last = stem[-1:] if stem else ""
    if form_kind in ("pret1s", "subj_all"):
        if last == "c" and end[:1] in "eé":
            return stem[:-1] + "qu"
        if last == "g" and end[:1] in "eé":
            return stem[:-1] + "gu"
        if last == "z" and end[:1] in "eé":
            return stem[:-1] + "c"
    if form_kind in ("pres_subj", "pres_1s") and last == "g" and end[:1] in "oa":
        return stem[:-1] + "j"
    if last == "g" and end[:1] in "oa" and stem.endswith("gu"):
        return stem[:-1] + "j" if stem.endswith("gir") else stem
    return stem


def gerund(inf, kind):
    stem, tail = inf[:-2], inf[-2:]
    if tail == "ar":
        return stem + "ando"
    # -ir stem changers use the weak stem here too: dormir -> durmiendo
    gk = {"e:ie": "e:i", "o:ue": "o:u"}.get(kind, kind) if tail == "ir" else kind
    if gk in ("e:i", "o:u"):
        return stem_change(stem, gk) + "iendo"
    return stem + "iendo"


def participle(inf, kind):
    stem, tail = inf[:-2], inf[-2:]
    return stem + ("ado" if tail == "ar" else "ido")


def conjugate(inf, kind=None, reflexive=False):
    """Yield (form, tense, person) for every generated form of an infinitive.

    Two families need rules beyond the regular endings:
      * -uir inserts a y (incluir -> incluyo / incluyó / incluyendo / incluya)
      * -cer/-cir after a vowel insert z in the 1s and the whole subjunctive
        (padecer -> padezco / padezca); vencer -> venzo is NOT one of these
        because its c follows a consonant.
    The subjunctive is derived from the 1s present form, which makes the -zco
    family fall out automatically.
    """
    if not inf.endswith(("ar", "er", "ir")) or len(inf) < 3:
        return
    tail = inf[-2:]
    stem = inf[:-2]
    table = AR if tail == "ar" else ER if tail == "er" else IR
    is_uir = inf in UIR
    is_zco = inf in ZCO
    is_eer = inf in EER
    out = {}

    def yfix(end):
        """-uir words write y before endings that begin with a/e/o."""
        if is_uir and end[:1] in "aeoáéó":
            return "y" + end
        return end

    # ---- present ----
    pres = {}
    for i, end in enumerate(table["pres."]):
        base = stem_change(stem, kind) if (kind and i in BOOT) else stem
        pres[PERSONS[i]] = base + yfix(end)
    # ---- present 1s (also the base of the whole subjunctive) ----
    base1s = stem_change(stem, kind) if kind else stem
    if inf in GUIR:                 # seguir -> sigo   (the u is dropped)
        pres["1s"] = base1s[:-1] + "o"
    elif inf in GERGIR:             # coger -> cojo, elegir -> elijo
        pres["1s"] = base1s[:-1] + "jo"
    elif inf in CER_CONS:           # vencer -> venzo  (c after a consonant)
        pres["1s"] = base1s[:-1] + "zo"
    elif is_zco:                    # padecer -> padezco (c after a vowel)
        pres["1s"] = base1s[:-1] + "zco"
    elif is_uir:                    # incluir -> incluyo
        pres["1s"] = base1s + "yo"
    for p, f in pres.items():
        out[f] = ("pres.", p)

    # ---- subjunctive (from the 1s present for -er/-ir) ----
    for i, end in enumerate(table["subj."]):
        if tail == "ar":
            base = stem_change(stem, kind) if (kind and i not in (3, 4)) else stem
            base = spelling(base, end, "subj_all")      # buscar -> busque
        else:
            # The 1s form already carries any j/g/z spelling (cojo, sigo,
            # padezco, venzo), so deriving from it needs no further adjustment.
            first = pres["1s"]
            base = first[:-1] if first.endswith("o") else first
        out.setdefault(base + end, ("subj.", PERSONS[i]))

    # ---- preterite ----
    EER_PRET = {"iste": "íste", "imos": "ímos", "isteis": "ísteis"}
    for i, end in enumerate(table["pret."]):
        base, e = stem, end
        if is_uir and i in (2, 5):          # incluyó / incluyeron
            e = "yó" if i == 2 else "yeron"
        if is_eer:                          # poseí / poseíste / poseyó / poseímos
            e = {"ió": "yó", "ieron": "yeron"}.get(end, EER_PRET.get(end, end))
        base = spelling(base, e, "pret1s" if i == 0 else "")
        out.setdefault(base + e, ("pret.", PERSONS[i]))
    if tail == "ir" and kind:
        # preterite 3s/3p of -ir stem changers: dormir -> durmió (o:ue becomes
        # o:u here), sentir -> sintió (e:ie becomes e:i)
        pk = {"e:ie": "e:i", "o:ue": "o:u"}.get(kind, kind)
        if pk in ("e:i", "o:u"):
            for i in (2, 5):
                out.setdefault(stem_change(stem, pk) + table["pret."][i], ("pret.", PERSONS[i]))

    # ---- imperfect ----
    for i, end in enumerate(table["imp."]):
        out.setdefault(stem + end, ("imp.", PERSONS[i]))

    # ---- future / conditional attach to the whole infinitive ----
    for tense in ("fut.", "cond."):
        for i, end in enumerate(table[tense]):
            out.setdefault(inf + end, (tense, PERSONS[i]))

    # ---- imperative (setdefault: identical 3s present forms must win) ----
    if tail == "ar":
        out.setdefault(stem + "a", ("imper.", "2s"))
        out.setdefault(stem + "ad", ("imper.", "2p"))
        for i, end in ((2, "e"), (5, "en")):
            base = stem_change(stem, kind) if kind else stem
            base = spelling(base, end, "subj_all")      # busque / llegue (usted)
            out.setdefault(base + end, ("imper.", PERSONS[i]))
    else:
        out.setdefault(stem + yfix("e"), ("imper.", "2s"))
        out.setdefault(stem + ("ed" if tail == "er" else "id"), ("imper.", "2p"))
        for i, end in ((2, "a"), (5, "an")):
            first = pres["1s"]
            base = first[:-1] if first.endswith("o") else first
            out.setdefault(base + end, ("imper.", PERSONS[i]))

    # ---- non-finite ----
    if is_uir or is_eer:
        out.setdefault(stem + "yendo", ("ger.", "-"))       # incluyendo / poseyendo
    else:
        out.setdefault(gerund(inf, kind), ("ger.", "-"))
    if is_eer:
        out.setdefault(stem + "ído", ("part.", "-"))        # poseído (accented)
    else:
        out.setdefault(participle(inf, kind), ("part.", "-"))

    # reflexive / pronominal forms
    forms = dict(out)
    for f, (t, p) in out.items():
        if t in ("ger.", "part."):
            continue
        for suf in ("me", "te", "se", "nos", "os", "se"):
            forms.setdefault(f + suf, (t, p))
    for f, (t, p) in forms.items():
        yield f, t, p


STEM_CHANGE = {
    # e -> ie
    "pensar": "e:ie", "empezar": "e:ie", "comenzar": "e:ie", "cerrar": "e:ie",
    "entender": "e:ie", "perder": "e:ie", "querer": "e:ie", "sentir": "e:ie",
    "preferir": "e:ie", "mentir": "e:ie", "venir": "e:ie", "tener": "e:ie",
    "convertir": "e:ie", "despertar": "e:ie", "despertarse": "e:ie", "sentarse": "e:ie",
    "acertar": "e:ie", "encerrar": "e:ie", "helar": "e:ie", "negar": "e:ie",
    "recomendar": "e:ie", "regar": "e:ie", "sentar": "e:ie", "temblar": "e:ie",
    "tentar": "e:ie", "verter": "e:ie", "defender": "e:ie", "encender": "e:ie",
    "atender": "e:ie", "extender": "e:ie", "ascender": "e:ie", "confesar": "e:ie",
    "manifestar": "e:ie", "gobernar": "e:ie", "adquirir": "e:ie", "divertir": "e:ie",
    "advertir": "e:ie", "invertir": "e:ie", "hervir": "e:ie", "requerir": "e:ie",
    "sugerir": "e:ie", "digerir": "e:ie", "consentir": "e:ie", "arrepentirse": "e:ie",
    "encerrar ": "e:ie", "despertarse ": "e:ie",
    # o -> ue
    "contar": "o:ue", "encontrar": "o:ue", "recordar": "o:ue", "mostrar": "o:ue",
    "probar": "o:ue", "soñar": "o:ue", "volar": "o:ue", "volver": "o:ue",
    "devolver": "o:ue", "resolver": "o:ue", "mover": "o:ue", "llover": "o:ue",
    "dormir": "o:ue", "morir": "o:ue", "poder": "o:ue", "colgar": "o:ue",
    "rogar": "o:ue", "sonar": "o:ue", "sonreír": "o:ue", "acordar": "o:ue",
    "acordarse": "o:ue", "acostar": "o:ue", "acostarse": "o:ue", "almorzar": "o:ue",
    "aprobar": "o:ue", "costar": "o:ue", "demostrar": "o:ue", "envolver": "o:ue",
    "tropezar": "o:ue", "doler": "o:ue", "soler": "o:ue", "oler": "o:ue",
    # e -> i (mostly -ir)
    "pedir": "e:i", "repetir": "e:i", "servir": "e:i", "vestir": "e:i",
    "medir": "e:i", "seguir": "e:i", "conseguir": "e:i", "elegir": "e:i",
    "corregir": "e:i", "regir": "e:i", "decir": "e:i", "reír": "e:i",
    "freír": "e:i", "impedir": "e:i", "despedir": "e:i", "gemir": "e:i",
    "rendir": "e:i", "competir": "e:i", "repetir ": "e:i", "servir ": "e:i",
    # u -> ue
    "jugar": "u:ue",
}

# -uir verbs take an inserted y: incluir -> incluyo / incluyó / incluyendo.
# (-guir and -quir are excluded: seguir -> sigo, delinquir -> delinco.)
UIR = set("""incluir construir destruir huir sustituir contribuir distribuir
instituir constituir atribuir retribuir disminuir fluir influir recluir
obstruir excluir incluirse""".split())

# -cer / -cir after a vowel insert z: padecer -> padezco, lucir -> luzco.
# (vencer -> venzo and mecer -> mezo keep c: the c follows a consonant.)
ZCO = set("""padecer conocer parecer agradecer crecer nacer ofrecer aparecer
permanecer pertenecer conducir producir traducir lucir esparcir
enriquecer oscurecer obedecer desobedecer complacer renacer""".split())

# -eer verbs write y in the 3rd persons and the gerund, and accent the participle:
# poseer -> poseyó / poseyeron / poseyendo / poseído
EER = set("""poseer proveer sobreseer releer desposeer""".split())

# Spelling-changing families.  All three only affect the 1s present form, and
# because the subjunctive is derived from it, they fall out automatically.
GUIR = set("""seguir conseguir perseguir proseguir distinguir extinguir""".split())
GERGIR = set("""coger recoger escoger proteger elegir corregir regir dirigir
exigir surgir urgir fingir sumergir emergir""".split())
CER_CONS = set("""vencer mecer esparcir zurcir fruncir torcer retorcer cocer escocer""".split())


def infinitives_from(seed, glossary):
    infs = {}
    for k, v in seed.items():
        pos = (v.get("pos") or "").lower()
        if pos.startswith(("v", "vr")) and k.endswith(("ar", "er", "ir")):
            infs[k] = True
    for k, meta in glossary.items():
        raw = (meta.get("raw") or "").lower()
        if not k.endswith(("ar", "er", "ir")) or len(k) < 4:
            continue
        if any(m in raw for m in (" tr.", " intr.", " prnl.", " inf.", ":prnl", ":tr")) or raw.startswith(k + " "):
            infs[k] = True
    return sorted(infs)


def main():
    seed = json.load(io.open(os.path.join(ROOT, "data", "dict_seed.json"), encoding="utf-8"))
    glossary = json.load(io.open(os.path.join(ROOT, "data", "lex_glossary.json"), encoding="utf-8"))
    infs = infinitives_from(seed, glossary)
    print("infinitives found:", len(infs))

    # Curated irregulars first: their forms are authoritative, and generating
    # *regular* forms for those verbs would inject wrong entries ("teno",
    # "tenes") into the repair lexicon.
    irr_path = os.path.join(ROOT, "data", "lex_irregular.json")
    irr = {}
    if os.path.exists(irr_path):
        try:
            irr = json.load(io.open(irr_path, encoding="utf-8"))
        except Exception as e:
            print("!! lex_irregular.json unreadable, skipped:", e)
    curated_verbs = {v.get("inf") for v in irr.values() if v.get("inf")}

    forms = {}
    skipped_curated = 0
    for inf in infs:
        kind = STEM_CHANGE.get(inf)
        base = inf[:-2] if inf.endswith("se") and len(inf) > 4 else inf
        if base in curated_verbs or inf in curated_verbs:
            skipped_curated += 1
            continue
        if base.endswith(("ar", "er", "ir")):
            for f, t, p in conjugate(base, kind or STEM_CHANGE.get(base)):
                forms.setdefault(f, {"inf": base, "t": t, "p": p})
        for f, t, p in conjugate(inf, kind):
            forms.setdefault(f, {"inf": inf, "t": t, "p": p})
    print("regular forms generated: %d   (verbs left to the curated table: %d)"
          % (len(forms), skipped_curated))

    n_irr = 0
    for k, v in irr.items():
        forms[k] = {"inf": v.get("inf"), "t": v.get("t"), "p": v.get("p"), "irr": 1}
        n_irr += 1
    print("irregular forms merged:", n_irr)

    dst = os.path.join(ROOT, "data", "lex_verbs.json")
    json.dump(forms, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("wrote", dst, "(%d forms)" % len(forms))

    for w in ("tengo", "voy", "dice", "puedo", "quiero", "lleva", "está", "están", "hablando", "comido"):
        print("   %-10s -> %s" % (w, forms.get(w, "(absent)")))


if __name__ == "__main__":
    main()
