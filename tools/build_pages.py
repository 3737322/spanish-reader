# -*- coding: utf-8 -*-
"""
Turn Windows-OCR output into page hotspot data for the click-to-read reader.

Key problems solved here
------------------------
1. The en-GB engine also "reads" Chinese regions and emits Latin garbage
   (e.g. the Chinese instruction line becomes "VIL F&IJ6J f").  Those fake
   words are removed by testing each Latin word box against the boxes of
   Han-character words found by the zh-Hans-CN engine: if a Latin box is
   mostly covered by a Chinese box, it is not Spanish text.
2. Coordinates are normalised to 0..1 against the display image so the overlay
   stays aligned at any zoom level.
3. Words get stable ids (p:line:index) so a later correction pass can rewrite
   text without touching geometry.
"""
import json
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
HAS_LETTER = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")
# single characters that are real Spanish words
ONE_CHAR_OK = set("aeiouyAEIOUY")
PUNCT_ONLY = re.compile(r"^[^\wÁÉÍÓÚÜÑáéíóúüñ]+$")


def norm_box(x, y, w, h, pw, ph):
    return (round(x / pw, 6), round(y / ph, 6), round(w / pw, 6), round(h / ph, 6))


def overlap_ratio(a, b):
    """Fraction of box a's area that intersects box b."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    area = aw * ah
    return (inter / area) if area > 0 else 0.0


def is_noise(token):
    t = token.strip()
    if not t:
        return True
    if PUNCT_ONLY.match(t):
        return True
    if not HAS_LETTER.search(t):
        return True
    letters = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", t)
    if len(letters) == 1 and letters not in ONE_CHAR_OK:
        return True
    return False


def main():
    ocr_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "ocr_all.json")
    out_pages = os.path.join(ROOT, "data", "pages_ocr.json")
    out_corr = os.path.join(ROOT, "data", "ocr_for_correction.json")

    with io.open(ocr_path, encoding="utf-8-sig") as f:
        recs = json.load(f)
    if isinstance(recs, dict):
        recs = [recs]
    print("ocr pages:", len(recs))

    pages = []
    corr_chunks = []
    stats = dict(kept=0, dropped_zh=0, dropped_noise=0, pages=0)

    for rec in recs:
        pw, ph = float(rec["w"]), float(rec["h"])
        langs = rec["ocr"]
        en_lines = langs.get("en-GB", []) or []
        zh_lines = langs.get("zh-Hans-CN", []) or []

        # boxes of real Chinese text -> regions where Latin OCR output is bogus
        han_boxes = []
        zh_han_words = []
        for ln in zh_lines:
            for w in ln["words"]:
                if HAN.search(w["t"]):
                    han_boxes.append((w["x"], w["y"], w["w"], w["h"]))
                    zh_han_words.append(w)

        words = []
        out_lines = []
        for li, ln in enumerate(en_lines):
            line_words = []
            for wi, w in enumerate(ln["words"]):
                raw = w["t"]
                box = (w["x"], w["y"], w["w"], w["h"])
                if is_noise(raw):
                    stats["dropped_noise"] += 1
                    continue
                cov = max((overlap_ratio(box, hb) for hb in han_boxes), default=0.0)
                if cov > 0.45:
                    stats["dropped_zh"] += 1
                    continue
                # A Latin token sandwiched between Chinese boxes on the same line is
                # OCR noise produced by the en-GB engine reading Chinese glyphs
                # (e.g. "(ZI" or "iJ:").  A genuine Spanish word in a vocabulary row
                # only has Chinese on one side, so this test keeps those.
                cy = w["y"] + w["h"] / 2.0
                band = max(w["h"], 18.0) * 1.1
                has_left = has_right = False
                for hb in han_boxes:
                    hy = hb[1] + hb[3] / 2.0
                    if abs(hy - cy) > band:
                        continue
                    if hb[0] + hb[2] <= w["x"] + 3.0:
                        has_left = True
                    elif hb[0] >= w["x"] + w["w"] - 3.0:
                        has_right = True
                    if has_left and has_right:
                        break
                if has_left and has_right:
                    stats["dropped_zh"] += 1
                    continue
                nx, ny, nw, nh = norm_box(w["x"], w["y"], w["w"], w["h"], pw, ph)
                wid = "%d:%d:%d" % (rec["file"] and int(re.findall(r"\d+", rec["file"])[0]), li, len(line_words))
                line_words.append({"id": wid, "t": raw, "x": nx, "y": ny, "w": nw, "h": nh})
                stats["kept"] += 1
            if line_words:
                # line_words are ALREADY normalised; do not divide by the page
                # size again (that produced degenerate ~1e-4 line boxes).
                x0 = min(w["x"] for w in line_words)
                y0 = min(w["y"] for w in line_words)
                x1 = max(w["x"] + w["w"] for w in line_words)
                y1 = max(w["y"] + w["h"] for w in line_words)
                out_lines.append({
                    "t": " ".join(w["t"] for w in line_words),
                    "x": round(x0, 6), "y": round(y0, 6),
                    "w": round(x1 - x0, 6), "h": round(y1 - y0, 6),
                    "first": line_words[0]["id"], "n": len(line_words),
                })
                words.extend(line_words)
                corr_chunks.append({"id": line_words[0]["id"], "t": " ".join(w["t"] for w in line_words),
                                    "ids": [w["id"] for w in line_words]})

        pno = int(re.findall(r"\d+", rec["file"])[0])
        pages.append({
            "page": pno,
            "file": rec["file"],
            "ocr_w": rec["w"], "ocr_h": rec["h"],
            "lines": out_lines,
            "words": words,
            "zh": " ".join(w["t"] for w in zh_han_words),
        })
        stats["pages"] += 1

    pages.sort(key=lambda p: p["page"])
    os.makedirs(os.path.dirname(out_pages), exist_ok=True)
    with io.open(out_pages, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, separators=(",", ":"))
    with io.open(out_corr, "w", encoding="utf-8") as f:
        json.dump(corr_chunks, f, ensure_ascii=False, indent=0)

    print("stats:", stats)
    print("pages_ocr.json -> %.2f MB" % (os.path.getsize(out_pages) / 1048576))
    print("correction lines:", len(corr_chunks))
    tot_tokens = sum(len(c["ids"]) for c in corr_chunks)
    print("total latin tokens:", tot_tokens)

    # quick sanity peek at a content page
    for p in pages:
        if p["page"] == 30:
            print("\n--- page 30 sample lines ---")
            for ln in p["lines"][:12]:
                print("  |", ln["t"])


if __name__ == "__main__":
    main()
