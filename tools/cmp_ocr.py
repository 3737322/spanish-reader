# -*- coding: utf-8 -*-
"""Quantitative comparison of OCR runs (resolution / language) + side-by-side text."""
import json, sys, io, re, unicodedata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ACCENT = set("áéíóúüñÁÉÍÓÚÜÑ¿¡")
HAN = re.compile(r"[\u4e00-\u9fff]")


def stats(path, label):
    with io.open(path, encoding="utf-8-sig") as f:
        recs = json.load(f)
    if isinstance(recs, dict):
        recs = [recs]
    out = []
    for r in recs:
        for tag, lines in r["ocr"].items():
            words = [w for ln in lines for w in ln["words"]]
            txt = " ".join(ln["text"] for ln in lines)
            latin = [w for w in words if not HAN.search(w["t"])]
            acc = [w for w in words if any(c in ACCENT for c in w["t"])]
            han = [w for w in words if HAN.search(w["t"])]
            out.append(dict(file=r["file"], lang=tag, lines=len(lines), words=len(words),
                            latin=len(latin), han=len(han), accented=len(acc),
                            chars=len(txt)))
    return out


def table(rows, label):
    print("\n### " + label)
    print("%-16s %-12s %6s %6s %6s %6s %7s %7s" % ("page", "lang", "lines", "words", "latin", "han", "accent", "chars"))
    for r in rows:
        print("%-16s %-12s %6d %6d %6d %6d %7d %7d" % (r["file"], r["lang"], r["lines"], r["words"],
                                                       r["latin"], r["han"], r["accented"], r["chars"]))
    tot = {}
    for r in rows:
        k = r["lang"]
        t = tot.setdefault(k, dict(words=0, acc=0, chars=0, han=0))
        t["words"] += r["words"]; t["acc"] += r["accented"]; t["chars"] += r["chars"]; t["han"] += r["han"]
    print("TOTALS:", json.dumps(tot, ensure_ascii=False))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        table(stats(p, p), p)
