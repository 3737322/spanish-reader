# -*- coding: utf-8 -*-
"""
Build the book's official dictionary from its printed word lists.

Two layouts exist in this textbook and both are row-shaped
    [ spanish word ] [ POS ] [ chinese meaning ]  ( [ lesson no. ] )
so one row-clustering extractor handles both:

  * GLOSARIO   pages 294-304 - the master index: ~970 words, each with its
                 Chinese gloss, alphabetically ordered.  This is the best
                 dictionary source in the book.
  * VOCABULARIO 16 unit pages - the per-unit new-word tables.

The pages are two-column; boxes are therefore split by the page midpoint
BEFORE clustering by baseline, otherwise the left and right tables chain into
one bogus row ("estar cop. Victor").
"""
import json, io, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\harness工作区\spanish-reader"
HAN = re.compile(r"[\u3400-\u9fff]")
CJK_KEEP = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")
LAT = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ.,()'\- ]*$")
POS_TOK = re.compile(
    r"^(m|f|mf|m\.f|tr|intr|prnl|pron|adj|adv|prep|conj|interj|art|num|inf|p\.p|v|s|pl|loc|cop)\b",
    re.I)
GLOSARIO_PAGES = range(294, 305)
VOCAB_PAGES = [18, 34, 50, 66, 82, 100, 116, 132, 148, 166, 182, 200, 218, 238, 260, 278]


CJK_JUNK = set(chr(c) for c in range(0x2E80, 0x2FE0)) | set(
    "丿丆乁丨丶亅乀亠冫冖凵卩阝厶廴廾弋彐彡忄扌氵灬纟艹衤讠饣丬犭疒癶丩丬乛乚")


def clean_zh(parts):
    s = "".join(parts)
    s = "".join(ch for ch in s if CJK_KEEP.match(ch))
    s = "".join(ch for ch in s if ch not in CJK_JUNK)
    s = re.sub(r"^[；，、。：]+|[；，、：]+$", "", s)
    return s


# Latin tokens the OCR sprinkles into word rows; observed, not guessed.
JUNK_TOKENS = {"hifi", "jl", "j)", "ac(j", "cull", "ad)", "till", "ios", "fifi",
               "loc.ado", "loc.coqj", "loc.aclc", "loc.aclv", "loc.adt", "pml",
               "ac!j", "aclj", "ac(j.", "aclj.", "ac(j", "i)"}
SHORT_TAIL = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{1,3}$")
KEEP_SINGLE = set("aeiouyáéíóúAEIOUY")


def find_chinese_column(han_boxes, half_lo, half_hi, bin_w=50.0):
    """The Chinese meanings live in one dense column per half; scattered junk
    boxes sit to its left.  Return the column's starting x (or None)."""
    inside = [w for w in han_boxes if half_lo <= w["x"] < half_hi]
    if len(inside) < 6:
        return None
    hist = collections.Counter(int(w["x"] // bin_w) for w in inside)
    thr = max(5, int(0.10 * len(inside)))
    for b in sorted(hist):
        if hist[b] >= thr:
            return b * bin_w
    return None


def cluster_rows(items, tol_ratio=0.5):
    items = sorted(items, key=lambda w: w["y"] + w["h"] / 2.0)
    rows, cur, cur_y = [], [], None
    for w in items:
        y = w["y"] + w["h"] / 2.0
        tol = min(max(w["h"], 16.0), 44.0) * tol_ratio
        if cur_y is None or abs(y - cur_y) <= tol:
            cur.append(w)
            cur_y = y if cur_y is None else (cur_y + y) / 2.0
        else:
            rows.append(cur)
            cur, cur_y = [w], y
    if cur:
        rows.append(cur)
    return rows


def extract_page(rec):
    pw = float(rec["w"])
    en = [w for ln in (rec["ocr"].get("en-GB") or []) for w in ln["words"]]
    zh = [w for ln in (rec["ocr"].get("zh-Hans-CN") or []) for w in ln["words"]]

    head_y = 0.0
    for w in en:
        if w["t"].strip().lower().startswith(("vocabulario", "glosario")):
            head_y = max(head_y, w["y"] + w["h"])

    latin = [w for w in en if w["y"] > head_y and LAT.match(w["t"].strip())
             and (len(w["t"].strip()) > 1 or w["t"].strip() in KEEP_SINGLE)]
    han = [w for w in zh if w["y"] > head_y and HAN.search(w["t"])]

    out = []
    for half in (0, 1):
        lo, hi = (0.0, pw / 2.0) if half == 0 else (pw / 2.0, pw)
        col = find_chinese_column(han, lo, hi)
        side_lat = [w for w in latin if lo <= w["x"] + w["w"] / 2.0 < hi]
        side_han = [w for w in han if lo <= w["x"] < hi and (col is None or w["x"] >= col - 60)]
        for row in cluster_rows(sorted(side_lat + side_han, key=lambda w: w["y"] + w["h"] / 2.0)):
            row.sort(key=lambda w: w["x"])
            es, pos, zhp = [], [], []
            for w in row:
                t = w["t"].strip()
                if HAN.search(t):
                    zhp.append(t)
                else:
                    t2 = t.strip().strip(",")
                    if not t2:
                        continue
                    if POS_TOK.match(t2) and len(t2) <= 9:
                        pos.append(t2.rstrip("."))
                    else:
                        es.append(t2)
            if es:
                es = repair_head([es[0]]) + [t for t in es[1:] if keep_tail(t)]
            if not es and not zhp:
                continue
            out.append({
                "es": re.sub(r",\s+", ", ", " ".join(es)).strip(),
                "pos": ",".join(pos),
                "zh": clean_zh(zhp),
                "half": half,
                "y": round(row[0]["y"], 1),
            })
    out.sort(key=lambda e: (e["half"], e["y"]))
    return out


LEX = set()
RP = None
TIERS = None
ACCIDX = None


def repair_head(tokens):
    """Run headword tokens through the OCR repair engine so the dictionary key
    is the canonical spelling ("afiadir" -> "añadir", "direcciön" -> "dirección")."""
    if RP is None:
        return tokens
    out = []
    for t in tokens:
        if any(c in t for c in "()"):
            out.append(t)
            continue
        fixed, how = RP.repair_token(t, TIERS, ACCIDX)
        if how == "skip":
            continue
        out.append(fixed)
    return out or tokens


def keep_tail(t):
    """Decide whether a token after the headword belongs to it.

    Real tails are the gender ending ("ocupado, da"), the rest of a phrase
    ("agua mineral") or a proper noun ("America Latina").  OCR junk that lands
    in the same row looks like "Hifi", "ac(j." or "cull'.".
    """
    if t.lower() in JUNK_TOKENS:
        return False
    if SHORT_TAIL.match(t):
        return True
    if t in LEX or t.lower() in LEX or t.capitalize() in LEX:
        return True
    return False


def merge_split(entries):
    """'ocupado,' + 'da' on consecutive rows belong to one headword."""
    out = []
    for e in entries:
        prev = out[-1] if out else None
        if (prev and prev["half"] == e["half"] and e["zh"] and prev["zh"] == e["zh"]
                and abs(e["y"] - prev["y"]) < 70 and len(e["es"]) <= 4 and e["es"]):
            prev["es"] = (prev["es"] + " " + e["es"]).strip()
            if e["pos"] and not prev["pos"]:
                prev["pos"] = e["pos"]
            continue
        out.append(dict(e))
    return out


def main():
    global LEX, RP, TIERS, ACCIDX
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import repair as RP_
        RP = RP_
        seed, glossary, verbs = RP.load_tiers()
        high, mid, vset, low, lex, _ = RP.build_lexicon(seed, glossary, verbs, {})
        LEX = lex
        TIERS = {"high": high, "mid": mid, "verb": vset, "low": low}
        ACCIDX = collections.defaultdict(set)
        for w in lex:
            ACCIDX[RP.strip_acc(w).lower()].add(w)
        print("validation lexicon:", len(LEX), "forms")
    except Exception as e:
        print("!! lexicon unavailable, headwords left unrepaired:", e)

    raw = json.load(io.open(os.path.join(ROOT, "data", "ocr_all.json"), encoding="utf-8-sig"))
    by_page = {int("".join(c for c in r["file"] if c.isdigit())): r for r in raw}

    result = {"glosario": [], "vocabulario": []}
    for label, pages in (("glosario", list(GLOSARIO_PAGES)), ("vocabulario", VOCAB_PAGES)):
        for pno in pages:
            rec = by_page.get(pno)
            if not rec:
                continue
            es = merge_split(extract_page(rec))
            es = [e for e in es if e["es"]]
            result[label].append({"page": pno, "entries": es})

    for label in result:
        rows = [e for blk in result[label] for e in blk["entries"]]
        withzh = [e for e in rows if e["zh"]]
        print("%-12s pages=%2d  entries=%4d  with chinese=%4d" %
              (label, len(result[label]), len(rows), len(withzh)))

    dst = os.path.join(ROOT, "data", "vocab_raw.json")
    json.dump(result, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", dst)

    with io.open(os.path.join(ROOT, "data", "_vocab_sample.txt"), "w", encoding="utf-8") as f:
        for label in ("glosario", "vocabulario"):
            for blk in result[label][:2]:
                f.write("### %s page %d\n" % (label, blk["page"]))
                for e in blk["entries"]:
                    f.write("   %-32s %-10s | %s\n" % (e["es"], e["pos"], e["zh"]))


if __name__ == "__main__":
    main()
