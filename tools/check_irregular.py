# -*- coding: utf-8 -*-
"""
Cross-validate the curated irregular table against this project's own regular
conjugation engine.  Two independent implementations: where they disagree on a
NON-irregular verb, one of them is wrong and it is worth a look.

Disagreements on genuinely irregular verbs (ser, ir, tener, stem-changers, ...)
are expected and reported separately, not as errors.
"""
import json, io, os, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conjugate as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
irr = json.load(io.open(os.path.join(ROOT, "data", "lex_irregular.json"), encoding="utf-8"))

by_verb = collections.defaultdict(set)
for form, v in irr.items():
    by_verb[v["inf"]].add(form)

# verbs our engine handles purely by rule (no stem change entry, no irregular entry)
CURATED_ONLY = set()
regular_mismatch = collections.Counter()
irregular_verb = set()
checked = 0
examples = []

for inf, forms in sorted(by_verb.items()):
    base = inf
    if base.endswith("se") and len(base) > 4:
        base = base[:-2]
    if not base.endswith(("ar", "er", "ir")):
        continue
    kind = C.STEM_CHANGE.get(base) or C.STEM_CHANGE.get(inf)
    mine = set()
    try:
        for f, t, p in C.conjugate(base, kind):
            mine.add(f)
    except Exception as e:
        continue
    if not mine:
        continue
    checked += 1
    only_theirs = forms - mine
    only_mine = mine - forms
    # ignore reflexive/pronoun suffixed forms, which our engine adds liberally
    only_theirs = {f for f in only_theirs if not f.endswith(("me", "te", "se", "nos", "os"))}
    only_mine = {f for f in only_mine if not f.endswith(("me", "te", "se", "nos", "os"))}
    if kind or base in ("ser", "estar", "ir", "haber", "tener", "hacer", "decir", "poder",
                        "querer", "venir", "saber", "dar", "ver", "poner", "traer", "salir",
                        "oír", "caer", "valer", "caber", "andar", "jugar", "oler", "conocer",
                        "parecer", "producir", "traducir", "conducir", "pedir", "dormir",
                        "sentir", "seguir", "conseguir", "elegir", "volver", "mover", "leer",
                        "creer", "reír", "construir", "huir", "agradecer", "crecer", "nacer",
                        "ofrecer", "permanecer", "pertenecer", "aparecer", "satisfacer",
                        "bendecir", "maldecir", "escribir", "describir", "abrir", "cubrir",
                        "romper", "imprimir", "resolver", "devolver", "envolver", "enviar",
                        "confiar", "esquiar", "actuar", "continuar", "graduar", "situar",
                        "averiguar", "avergonzar", "coger", "recoger", "corregir", "regir",
                        "dirigir", "exigir", "surgir", "urgir", "esparcir", "lucir", "vencer",
                        "mecer", "cazar", "almorzar", "tropezar", "cruzar", "realizar",
                        "analizar", "utilizar", "actualizar", "autorizar", "armonizar",
                        "arrancar", "tocar", "buscar", "sacar", "explicar", "practicar",
                        "aplicar", "dedicar", "indicar", "comunicar", "educar", "pescar",
                        "aparcar", "acercar", "justificar", "identificar", "clasificar",
                        "simplificar", "verificar", "certificar", "empezar", "comenzar",
                        "cerrar", "pensar", "entender", "perder", "preferir", "mentir",
                        "convertir", "sentar", "negar", "regar", "despertar", "contar",
                        "encontrar", "recordar", "mostrar", "probar", "soñar", "volar",
                        "llover", "colgar", "rogar", "sonar", "acordar", "acostar", "aprobar",
                        "costar", "demostrar", "repetir", "servir", "vestir", "medir",
                        "despedir", "impedir", "gemir", "rendir", "competir", "freír"):
        irregular_verb.add(inf)
        continue
    if only_theirs or only_mine:
        regular_mismatch[inf] += 1
        examples.append((inf, sorted(only_theirs)[:6], sorted(only_mine)[:6]))

print("verbs compared against the regular engine: %d" % checked)
print("  skipped as known-irregular/stem-changing: %d" % len(irregular_verb))
print("  purely regular verbs that still disagree: %d" % len(regular_mismatch))
for inf, theirs, mine in examples[:20]:
    print("   %-14s theirs-only=%s   mine-only=%s" % (inf, theirs, mine))

# Spot-check accents on the classic traps
print("\n=== accent traps (must match exactly) ===")
TRAPS = {"dio": "dar pret. 3s (no accent)", "vio": "ver pret. 3s (no accent)",
         "fue": "ir/ser pret. 3s (no accent)", "dé": "dar subj. 1s (accent)",
         "sé": "saber pres. 1s (accent)", "hizo": "hacer pret. 3s (no accent)",
         "dijo": "decir pret. 3s (no accent)", "está": "estar pres. 3s (accent)",
         "están": "estar pres. 3p (accent)", "más": None}
for form, note in TRAPS.items():
    if note is None:
        continue
    e = irr.get(form)
    print("   %-8s %-16s %s" % (form, (e["inf"] + " " + e["t"] + " " + e["p"]) if e else "-- ABSENT --", note))
