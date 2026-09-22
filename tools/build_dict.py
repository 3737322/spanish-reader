# -*- coding: utf-8 -*-
"""
Merge every dictionary source into the files the reader loads.

Priority for an entry's Chinese gloss:
   1. the book's GLOSARIO       (official for this textbook, ~880 entries)
   2. the unit VOCABULARIO lists
   3. the hand-written seed dictionary (clean, 1569 common words - fills gaps
      and covers words the OCR of the book's own glosses damaged)
An entry whose gloss looks like OCR junk is rejected in favour of a lower tier.

Outputs
  data/dict.json    { "hola": { "zh": "...", "pos": "...", "src": "..." } }
  data/lemmas.json  { "tengo": { "inf": "tener", "t": "pres.", "p": "1s" } }
  data/dict_stats.json
"""
import json, io, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\harness工作区\spanish-reader"
JUNK_ZH = re.compile(r"[丿丆乁丨丶亅乀亠冫冖凵卩阝厶廴廾弋彐彡忄扌氵灬纟艹衤讠饣丬犭疒癶\u2e80-\u2fdf]")
HAN = re.compile(r"[\u3400-\u9fff]")
SHORT_TAIL = re.compile(r"^[a-záéíóúüñ]{1,3}$")


def zh_quality(s):
    """Junk filter only.  Tier precedence is handled by TIER_Q, not by length:
    an OCR-damaged book gloss is often LONGER than the clean seed gloss
    ("de" -> "五突兀冒失" vs "的；从；关于"), so length must not win."""
    if not s:
        return 0
    if JUNK_ZH.search(s):
        return 0
    if not HAN.search(s):
        return 0
    return 1


ONE_LETTER = {"a", "e", "o", "u", "y"}


def keys_for(es):
    """Surface forms a reader might click that this headword should answer."""
    es = es.strip()
    if not es:
        return []
    toks = es.split()
    out = []
    first = toks[0]
    out.append(first)
    # "acercar(se)" must also answer the bare infinitive "acercar"
    bare = re.sub(r"\(.*?\)", "", first).strip()
    if bare and bare != first:
        out.append(bare)
        out.append(bare + "se")
    if len(toks) > 1:
        out.append(es)                      # locución / phrase entry
        tail = toks[1].lower()
        if SHORT_TAIL.match(tail):
            if first.endswith(("o", "os")):
                out.append(first[:-1] + tail[-1] if len(first) > 1 else first)
            elif len(first) > 2:
                out.append(first[:-1] + tail)
    base = bare or first
    if base.endswith("se") and len(base) > 4:
        out.append(base[:-2])
    for k in list(out):
        if k.endswith(("o", "a", "e", "í", "ú")):
            out.append(k + "s")
        else:
            out.append(k + "es")
    # single-letter Spanish words (a, y, o, e, u) are real and extremely frequent
    return [k for k in dict.fromkeys(out) if k and (len(k) > 1 or k.lower() in ONE_LETTER)]


# tier precedence: the hand-written seed beats the OCR'd book glosses
TIER_Q = {"extra": 5, "seed": 4, "book:glosario": 3, "book:vocabulario": 2}


def main():
    vocab = json.load(io.open(os.path.join(ROOT, "data", "vocab_raw.json"), encoding="utf-8"))
    seed = json.load(io.open(os.path.join(ROOT, "data", "dict_seed.json"), encoding="utf-8"))
    vpath = os.path.join(ROOT, "data", "lex_verbs.json")
    verbs = json.load(io.open(vpath, encoding="utf-8")) if os.path.exists(vpath) else {}

    dict_out = {}
    stats = collections.Counter()

    def offer(keys, zh, pos, src):
        q = zh_quality(zh)
        if q == 0:
            return
        rank = TIER_Q.get(src, 1)
        for k in keys:
            cur = dict_out.get(k)
            if cur is None or rank > cur["_q"]:
                dict_out[k] = {"zh": zh, "pos": pos or "", "src": src, "_q": rank}

    # tier 0: a tiny curated supplement for words neither source covers
    # (contractions like "al"/"del" are not listed in the book's word lists)
    xpath = os.path.join(ROOT, "data", "dict_extra.json")
    if os.path.exists(xpath):
        extra = json.load(io.open(xpath, encoding="utf-8"))
        for k, v in extra.items():
            offer(keys_for(k), v.get("zh", ""), v.get("pos", ""), "extra")
        stats["extra"] = len(extra)

    # tier 1: the hand-written seed dictionary wins wherever it overlaps
    for k, v in seed.items():
        offer(keys_for(k), v.get("zh", ""), v.get("pos", ""), "seed")
    stats["seed"] = len(seed)
    seed_keys = set(dict_out)

    # tier 2 + 3: the book's own word lists fill everything the seed lacks
    for src, label in (("book:glosario", "glosario"), ("book:vocabulario", "vocabulario")):
        n = 0
        for blk in vocab.get(label, []):
            for e in blk["entries"]:
                if not e["es"]:
                    continue
                offer(keys_for(e["es"]), e["zh"], e["pos"], src)
                n += 1
        stats[src] = n

    for v in dict_out.values():
        v.pop("_q", None)

    dst = os.path.join(ROOT, "data", "dict.json")
    json.dump(dict_out, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("dict.json entries: %d   (%.1f MB)" % (len(dict_out), os.path.getsize(dst) / 1048576))
    print("  keys covered by the seed dictionary: %d" % len(seed_keys))
    print("  by source:", dict(collections.Counter(v["src"] for v in dict_out.values())))

    lpath = os.path.join(ROOT, "data", "lemmas.json")
    json.dump(verbs, io.open(lpath, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("lemmas.json forms: %d   (%.1f MB)" % (len(verbs), os.path.getsize(lpath) / 1048576))

    # how much of the book's running text can the reader actually gloss?
    pages = json.load(io.open(os.path.join(ROOT, "data", "pages.json"), encoding="utf-8"))
    tot = hit = 0
    for p in pages:
        for w in p["words"]:
            if w.get("skip"):
                continue
            core = re.sub(r"^[^\w]+|[^\w]+$", "", w["t"], flags=re.UNICODE)
            if not core:
                continue
            tot += 1
            if core in dict_out or core.lower() in dict_out or core.capitalize() in dict_out:
                hit += 1
                continue
            base = verbs.get(core.lower()) or verbs.get(core)
            if base and base.get("inf") in dict_out:
                hit += 1
    print("\nclickable words: %d   resolvable offline: %d (%.1f%%)" % (tot, hit, 100.0 * hit / max(tot, 1)))

    json.dump({"entries": len(dict_out), "lemmas": len(verbs),
               "coverage": round(100.0 * hit / max(tot, 1), 1), "clickable": tot,
               "by_source": dict(collections.Counter(v["src"] for v in dict_out.values()))},
              io.open(os.path.join(ROOT, "data", "dict_stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
