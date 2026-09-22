# -*- coding: utf-8 -*-
"""Dump the raw dictionary of interesting objects to understand this PDF's layout."""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_pages import index_objects, parse_dict

pdf = os.path.join(ROOT, "textbook.pdf")
with open(pdf, "rb") as f:
    data = f.read()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

objs = index_objects(data)

page_nums = [n for n in sorted(objs)
             if re.search(rb"/Type\s*/Page\b", data[objs[n].start: objs[n].start + objs[n].raw_len])]
print("page objects:", len(page_nums), "first:", page_nums[:5], "last:", page_nums[-3:])

for n in page_nums[:2]:
    o = objs[n]
    d = parse_dict(data, objs, o)
    print("\n=== object %d (page) raw_len=%d ===" % (n, o.raw_len))
    print(d[:800] if d else None)

# objects that look like images
img_like = []
for n in sorted(objs):
    o = objs[n]
    seg = data[o.start: o.start + o.raw_len]
    if b"DCTDecode" in seg:
        img_like.append(n)
print("\nobjects containing /DCTDecode:", len(img_like), img_like[:6])
for n in img_like[:2]:
    o = objs[n]
    d = parse_dict(data, objs, o)
    print("\n=== image object %d ===" % n)
    print(d[:500] if d else None)
    print("stream_start=%s stream_len=%s" % (o.stream_start, o.stream_len))
    if o.stream_start:
        blob = data[o.stream_start: o.stream_start + 4]
        print("first stream bytes:", blob)
        print("ends with FFD9?", data[o.stream_start + o.stream_len - 2: o.stream_start + o.stream_len])

# how many objects reference images
print("\n=== sample tail objects (cat/page tree candidates) ===")
for n in list(sorted(objs))[-8:]:
    o = objs[n]
    d = parse_dict(data, objs, o)
    print("\n--- obj %d ---" % n)
    print((d[:400] if d else b"(no dict)").decode("latin-1"))
