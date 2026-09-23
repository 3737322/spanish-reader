# -*- coding: utf-8 -*-
"""校验自动词表页识别：与已知答案对比，并检查是否依赖页码。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vocab_pages

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWN = set(range(294, 305)) | {18, 34, 50, 66, 82, 100, 116, 132,
                                148, 166, 182, 200, 218, 238, 260, 278}

found = vocab_pages.detect_from_file(
    os.path.join(ROOT, "data", "ocr_all.json"), verbose=True)

got = set(found)
tp = got & KNOWN
fp = sorted(got - KNOWN)
fn = sorted(KNOWN - got)

print("")
print("=== 与已知答案对比 ===")
print("  已知词表页 : %d 页" % len(KNOWN))
print("  识别出     : %d 页" % len(got))
print("  正确命中   : %d" % len(tp))
print("  误报       : %d %s" % (len(fp), fp if fp else ""))
print("  漏检       : %d %s" % (len(fn), fn if fn else ""))
prec = len(tp) / len(got) if got else 0
rec = len(tp) / len(KNOWN)
print("  精确率 %.0f%%   召回率 %.0f%%" % (prec * 100, rec * 100))

print("\n=== 换一批页码是否影响结果（页码必须完全无关）===")
import json
raw = json.load(io.open(os.path.join(ROOT, "data", "ocr_all.json"), encoding="utf-8-sig"))
shuffled = list(raw)
shuffled.reverse()
f2 = vocab_pages.detect(shuffled)
same = set(f2) == got
print("  把 OCR 记录顺序整个反转后再检测：%s" % ("结果完全一致" if same else "结果不同！"))
print("  再跑一次是否稳定：%s" % ("一致" if vocab_pages.detect(raw) == f2 or set(vocab_pages.detect(raw)) == got else "不一致"))

ok = (len(fp) == 0 and len(fn) == 0 and same)
print("\n" + ("全部通过" if ok else "存在问题"))
sys.exit(0 if ok else 1)
