# -*- coding: utf-8 -*-
"""
自动识别「词表页」——不依赖任何页码、也不依赖某一本书。

为什么需要它
    早先 extract_dict.py / extract_glossary.py 里写死了 GLOSARIO_PAGES 和
    VOCAB_PAGES 两组页码，那等于这个工具只服务于一本教材。换成任何别的书，
    词表页找不到，词典就从 4700 条掉到 1600 条。

怎么识别（只用版式和标题，不看内容、不看页码）
    线索一 · 标题词
        页面文本里出现 VOCABULARIO / GLOSARIO / 词汇表 / Wortschatz …
        实测：精确度极高（本书 22/22 全中，零误报），但书眉常隔页印刷，
        所以会漏掉相邻页。
    线索二 · 邻居传播
        已识别的页，其左右 ±2 页若版式相近（词性缩写密度接近、短行占比高），
        则一并计入。本书靠这一步补齐了漏掉的 5 个奇数页。
    线索三 · 纯版式兜底
        整本书一个标题词都认不出来时（不认识的语种），退化为按版式判断：
        词性缩写密度高 + 词数够多 + 几乎全是短行。
        本书实测：10 页全中，零误报。精度靠「词数 ≥ 200」这一条保证 ——
        语法变位表虽然密度也高，但每页词数远不到 200。

判断依据全部来自 Windows OCR 的输出（词级坐标 + 文本），
所以对任何扫描版书籍都适用，与具体教材无关。
"""
import json
import os
import re

# 词性缩写：a word list is mostly "word  pos." lines
POS_TOK = re.compile(
    r"^(m|f|mf|m\.f|tr|intr|prnl|pron|adj|adv|prep|conj|interj|art|num|inf"
    r"|p\.?p|v|s|pl|loc|cop)\b",
    re.I)

# 标题词，按「越具体越优先」排列。多语种，加了常见教材用语。
TITLES = [
    ("glosario", re.compile(
        r"glosario|glossary|glossar|l[eé]xico|lexique|lexikon"
        r"|总词汇表|词汇总表|词汇索引|単語帳", re.I)),
    ("vocabulario", re.compile(
        r"vocabulari|vocabulary|vocabulaire|wortschatz|vokabelliste|wortliste"
        r"|词汇表|生词表|单词表|単語|語彙|ボキャブラリー", re.I)),
]


def page_signals(rec):
    """从一页的 OCR 结果里抽出用于判断版式的几个量。"""
    en_lines = rec["ocr"].get("en-GB") or []
    words = [w["t"].strip() for ln in en_lines for w in ln["words"]]
    words = [w for w in words if w]
    if not words:
        return None

    text = " ".join(ln["text"] for ln in en_lines)
    title = None
    for kind, rx in TITLES:
        if rx.search(text):
            title = kind
            break

    pos = sum(1 for w in words if len(w) <= 9 and POS_TOK.match(w))
    short_lines = sum(1 for ln in en_lines if 0 < len(ln["words"]) <= 4)
    return {
        "words": len(words),
        "pos": pos,
        "density": pos / len(words),
        "short_ratio": short_lines / max(len(en_lines), 1),
        "title": title,
    }


def detect(records, verbose=False,
           neighbor_gap=2, neighbor_tol=0.06, neighbor_min_density=0.10,
           neighbor_min_words=40,
           fallback_density=0.18, fallback_min_words=200, fallback_short=0.90):
    """返回 {页号: {"kind": "glosario"|"vocabulario", "via": "title"|"neighbor"|"density"}}。"""
    sig = {}
    for rec in records:
        try:
            pno = int("".join(c for c in rec["file"] if c.isdigit()))
        except (KeyError, ValueError):
            continue
        s = page_signals(rec)
        if s:
            sig[pno] = s

    found = {}

    # 线索一：标题词
    for pno, s in sig.items():
        if s["title"]:
            found[pno] = {"kind": s["title"], "via": "title"}

    # 线索二：邻居传播（书眉常隔页印刷，所以要看左右）
    for pno in sorted(found):
        kind = found[pno]["kind"]
        ref = sig[pno]
        for d in range(1, neighbor_gap + 1):
            for q in (pno - d, pno + d):
                if q in found or q not in sig:
                    continue
                s = sig[q]
                # 词数下限很关键：紧挨词表页的短文页/插图页密度可能碰巧接近，
                # 但整页才十来个词，不可能是一页词表。
                if (s["words"] >= neighbor_min_words
                        and abs(s["density"] - ref["density"]) <= neighbor_tol
                        and s["density"] >= neighbor_min_density
                        and s["short_ratio"] >= 0.80):
                    found[q] = {"kind": kind, "via": "neighbor"}

    # 线索三：一个标题都没认出来时，纯靠版式兜底
    if not found:
        for pno, s in sig.items():
            if (s["density"] >= fallback_density
                    and s["words"] >= fallback_min_words
                    and s["short_ratio"] >= fallback_short):
                found[pno] = {"kind": "glosario", "via": "density"}

    if verbose:
        by_via = {}
        for pno, info in sorted(found.items()):
            by_via.setdefault(info["via"], []).append(pno)
        print("  自动识别到 %d 个词表页（不依赖页码）" % len(found))
        for via, label in (("title", "标题词命中"),
                           ("neighbor", "由相邻页推断"),
                           ("density", "仅凭版式兜底")):
            if via in by_via:
                pages = by_via[via]
                shown = pages if len(pages) <= 24 else pages[:24] + ["..."]
                print("    %-12s %2d 页: %s" % (label, len(pages), shown))
        kinds = {}
        for info in found.values():
            kinds[info["kind"]] = kinds.get(info["kind"], 0) + 1
        print("    类型分布: %s" % kinds)

    return found


def detect_from_file(path, verbose=False):
    with open(path, encoding="utf-8-sig") as f:
        return detect(json.load(f), verbose=verbose)
