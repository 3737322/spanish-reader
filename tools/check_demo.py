# -*- coding: utf-8 -*-
"""
校验内置演示的完整性。

演示是刚克隆仓库的人看到的第一样东西 —— 它坏了，别人就以为这个项目是坏的。
所以这里检查它自洽：页数对得上、数据能解析、词表确实抽到了释义。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demo")

fails = []


def ok(cond, msg):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def load(rel):
    p = os.path.join(DEMO, rel)
    if not os.path.exists(p):
        return None
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


print("=== 演示文件 ===")
pages_dir = os.path.join(DEMO, "pages")
jpgs = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg")) if os.path.isdir(pages_dir) else []
ok(len(jpgs) >= 3, "demo/pages 有 %d 张页面图" % len(jpgs))

pages = load(os.path.join("data", "pages.json"))
ok(pages is not None and len(pages) > 0, "demo/data/pages.json 可解析")
if pages:
    ok(len(pages) == len(jpgs),
       "页数一致：%d 个数据页 vs %d 张图" % (len(pages), len(jpgs)))
    bad = [p["file"] for p in pages if not os.path.exists(os.path.join(pages_dir, p["file"]))]
    ok(not bad, "所有页面图都在" + ("，缺：" + str(bad) if bad else ""))
    total_words = sum(len(p.get("words", [])) for p in pages)
    ok(total_words > 100, "共 %d 个可点词" % total_words)
    # 热区归一化
    off = [w for p in pages for w in p.get("words", [])
           if not (0 <= w.get("x", -1) <= 1 and 0 < w.get("w", 0) <= 1)]
    ok(not off, "热区坐标都是 0..1 归一化的")

dic = load(os.path.join("data", "dict.json"))
ok(dic is not None and len(dic) > 500, "demo/data/dict.json 有 %d 条" % (len(dic) if dic else 0))

lem = load(os.path.join("data", "lemmas.json"))
ok(lem is not None and len(lem) > 10000, "demo/data/lemmas.json 有 %d 个词形" % (len(lem) if lem else 0))

print("\n=== 演示确实跑过真正的流水线 ===")
if dic:
    # 词表页抽出来的释义会进词典。全用种子词库的话说明词表没被识别。
    book_src = [k for k, v in dic.items() if str(v.get("src", "")).startswith("book:")]
    ok(len(book_src) > 0,
       "词典里有 %d 条来自演示词表页的释义（说明词表页被自动识别到了）" % len(book_src))
if pages and dic:
    # 抽查几个演示页上真实出现的词，确认能查到
    sample = []
    for p in pages:
        for w in p.get("words", []):
            t = w.get("t", "").strip(".,;:!?¿¡").lower()
            if len(t) > 3 and t.isalpha():
                sample.append(t)
    hit = sum(1 for t in set(sample) if t in dic or t.capitalize() in dic)
    total = len(set(sample))
    ok(hit > 0, "演示页上的 %d/%d 个不同实词能在词典里查到" % (hit, total))

print("\n=== 内容来源（必须是公版或自写）===")
src = os.path.join(DEMO, "source", "demo_content.txt")
ok(os.path.exists(src), "demo/source/demo_content.txt 存在")
if os.path.exists(src):
    with io.open(src, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    npages = sum(1 for ln in lines if ln.startswith("PAGE|"))
    ok(npages == len(jpgs), "内容文件里 %d 个 PAGE 行，与 %d 张图一致" % (npages, len(jpgs)))
    text = "\n".join(lines)
    ok("Mancha" in text, "正文含《堂吉诃德》开篇（公版文本）")
    ok(any(ln.startswith("V|") for ln in lines), "含 V| 词表行（供自动识别验证）")
    ok(any(ln.startswith("H|VOCABULARIO") for ln in lines), "含 VOCABULARIO 标题（标题词线索）")

print("\n" + "=" * 60)
if fails:
    print("%d 项失败" % len(fails))
    sys.exit(1)
print("全部通过")
