# -*- coding: utf-8 -*-
"""
Calibrate a book-agnostic word-list page detector.

Ground truth for THIS book (which the detector must not be told about):
    glossary index : pages 294-304
    unit word lists: pages 18, 34, 50, 66, 82, 100, 116, 132,
                            148, 166, 182, 200, 218, 238, 260, 278

The detector may only look at layout/typography, never at page numbers.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KNOWN = set(range(294, 305)) | {18, 34, 50, 66, 82, 100, 116, 132, 148, 166, 182, 200, 218, 238, 260, 278}

POS_TOK = re.compile(
    r"^(m|f|mf|m\.f|tr|intr|prnl|pron|adj|adv|prep|conj|interj|art|num|inf|p\.?p|v|s|pl|loc|cop)\b",
    re.I)
TITLES = [
    ("glosario", re.compile(r"glosario|l[eé]xico|总词汇表|词汇总表", re.I)),
    ("vocabulario", re.compile(r"vocabulari|vocabulary|wortschatz|vocabulaire|词汇表|生词表|单词表|単語|語彙", re.I)),
]


def signals(rec):
    en_lines = rec["ocr"].get("en-GB") or []
    words = [w["t"].strip() for ln in en_lines for w in ln["words"]]
    words = [w for w in words if w]
    if not words:
        return None
    text = " ".join(ln["text"] for ln in en_lines)
    kind = None
    for k, rx in TITLES:
        if rx.search(text):
            kind = k
            break
    pos = sum(1 for w in words if POS_TOK.match(w) and len(w) <= 9)
    # short lines: a word list is mostly one-entry-per-line
    short = sum(1 for ln in en_lines if 0 < len(ln["words"]) <= 4)
    return {
        "words": len(words),
        "pos": pos,
        "density": pos / len(words),
        "short_ratio": short / max(len(en_lines), 1),
        "title": kind,
    }


def main():
    raw = json.load(io.open(os.path.join(ROOT, "data", "ocr_all.json"), encoding="utf-8-sig"))
    rows = []
    for rec in raw:
        pno = int("".join(c for c in rec["file"] if c.isdigit()))
        s = signals(rec)
        if s:
            s["page"] = pno
            s["known"] = pno in KNOWN
            rows.append(s)

    print("=== 按「词性缩写密度」排序的前 45 页 ===")
    print("  %-6s %-7s %-8s %-8s %-9s %s" % ("page", "density", "pos", "words", "short%", "标题"))
    for s in sorted(rows, key=lambda r: -r["density"])[:45]:
        mark = "  <- 已知词表页" if s["known"] else ""
        print("  %-6d %-7.3f %-8d %-8d %-9.2f %s%s" %
              (s["page"], s["density"], s["pos"], s["words"], s["short_ratio"], s["title"] or "-", mark))

    known_d = sorted(s["density"] for s in rows if s["known"])
    other_d = sorted(s["density"] for s in rows if not s["known"])
    print("\n=== 分离度 ===")
    print("  已知词表页 %d 页   密度 最低 %.3f  中位 %.3f  最高 %.3f" %
          (len(known_d), known_d[0], known_d[len(known_d) // 2], known_d[-1]))
    print("  其他页     %d 页   密度 最低 %.3f  中位 %.3f  最高 %.3f" %
          (len(other_d), other_d[0], other_d[len(other_d) // 2], other_d[-1]))

    print("\n=== 不同阈值下的准确率 ===")
    for thr in (0.06, 0.08, 0.10, 0.12, 0.15, 0.20):
        hit = [s for s in rows if s["density"] >= thr and s["words"] >= 30]
        tp = sum(1 for s in hit if s["known"])
        fp = [s["page"] for s in hit if not s["known"]]
        fn = [s["page"] for s in rows if s["known"] and not (s["density"] >= thr and s["words"] >= 30)]
        print("  阈值 %.2f : 命中 %2d/%d  误报 %2d  漏检 %2d  %s" %
              (thr, tp, len(KNOWN), len(fp), len(fn),
               ("误报页 " + str(fp[:8])) if fp else "无误报"))

    print("\n=== 标题线索单独的效果 ===")
    titled = [s for s in rows if s["title"]]
    print("  含词表标题的页: %d 页" % len(titled))
    tp = [s["page"] for s in titled if s["known"]]
    fp = [s["page"] for s in titled if not s["known"]]
    print("    命中 %d/%d   误报 %s" % (len(tp), len(KNOWN), fp if fp else "无"))
    miss = sorted(KNOWN - set(tp))
    print("    标题线索漏掉的页: %s" % (miss if miss else "无"))


if __name__ == "__main__":
    main()
