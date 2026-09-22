# -*- coding: utf-8 -*-
"""Scan a PDF's raw bytes to decide whether it has real text or is a scan."""
import re, sys, collections

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\harness工作区\spanish-reader\textbook.pdf"

with open(path, "rb") as f:
    data = f.read()

print("size bytes:", len(data))
print("header:", data[:16])

# top-level object count
objs = re.findall(rb"(?m)^\s*(\d+)\s+(\d+)\s+obj\b", data)
print("objects found by scan:", len(objs))
nums = sorted({int(a) for a, b in objs})
if nums:
    print("obj number range:", nums[0], "..", nums[-1])
    missing = [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)]
    print("missing obj numbers:", len(missing), missing[:20])

patterns = {
    b"/Type/Page": "page (nospace)",
    b"/Type /Page": "page (space)",
    b"/Font": "font refs",
    b"/ToUnicode": "tounicode cmap",
    b"/Subtype/Image": "image (nospace)",
    b"/Subtype /Image": "image (space)",
    b"/DCTDecode": "jpeg image",
    b"/JPXDecode": "jpeg2000 image",
    b"/JBIG2Decode": "jbig2 image",
    b"/CCITTFaxDecode": "fax image",
    b"/FlateDecode": "flate stream",
    b"/FontFile2": "embedded truetype",
    b"/FontFile3": "embedded cff",
    b"/FontFile": "embedded type1",
    b"BT": "begin-text op (loose)",
    b"Tj": "show-text op (loose)",
    b"TJ": "show-text-array op (loose)",
    b"/Producer": "producer",
    b"/Creator": "creator",
    b"startxref": "startxref",
    b"/Linearized": "linearized",
    b"/Encrypt": "encrypted",
}
print("\n=== raw byte pattern counts ===")
for pat, label in patterns.items():
    print("%-28s %s" % (label, data.count(pat)))

print("\n=== Producer / Creator ===")
for m in re.finditer(rb"/(Producer|Creator|Title)\s*\(([^)]{0,200})\)", data):
    try:
        print(m.group(1).decode(), "->", m.group(2)[:160].decode("latin-1"))
    except Exception:
        pass
    if m.start() > 3_000_000:
        break

print("\n=== /Count in Pages node (approx page count) ===")
counts = [int(x) for x in re.findall(rb"/Type\s*/Pages.{0,300}?/Count\s+(\d+)", data, re.S)][:10]
print("counts:", counts)

print("\n=== last 400 bytes ===")
print(data[-400:])
