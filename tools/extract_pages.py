# -*- coding: utf-8 -*-
"""
Minimal, dependency-free PDF parser tailored to scanned PDFs.

It is not a general PDF library. It handles the common structure produced by
scanners (uncompressed indirect objects, /DCTDecode image streams, plain xref)
and is intentionally tolerant: objects are located by byte scanning rather than
by trusting the cross-reference table, so slightly damaged files still parse.

Outputs:
  * <outdir>/page_0001.jpg ...   raw JPEG bytes, one per page, in reading order
  * <outdir>/pages_raw.json      page geometry + image object numbers
"""
import json
import os
import re
import sys

OBJ_RE = re.compile(rb"(?<![0-9])(\d{1,7})\s+(\d{1,5})\s+obj\b")
WS = b"\x00\t\n\x0c\r "


class Obj:
    __slots__ = ("num", "gen", "start", "dict_bytes", "stream_start", "stream_len", "raw_len")

    def __init__(self, num, gen, start):
        self.num, self.gen, self.start = num, gen, start
        self.dict_bytes = b""
        self.stream_start = None
        self.stream_len = None
        self.raw_len = 0


def index_objects(data):
    """Byte-scan for 'N G obj' headers and record each object's byte span."""
    objs = {}
    for m in OBJ_RE.finditer(data):
        num = int(m.group(1))
        gen = int(m.group(2))
        # a later definition of the same number wins (incremental updates)
        objs[num] = Obj(num, gen, m.start())
    ordered = [objs[k] for k in sorted(objs)]
    for i, o in enumerate(ordered):
        o.raw_len = (ordered[i + 1].start if i + 1 < len(ordered) else len(data)) - o.start
    return objs


def parse_dict(data, objs, o):
    """Parse the << ... >> dictionary of an object, honouring nesting and strings."""
    body = data[o.start: o.start + o.raw_len]
    i = body.find(b"<<")
    if i < 0:
        return None
    depth = 0
    j = i
    while j < len(body) - 1:
        two = body[j:j + 2]
        if two == b"<<":
            depth += 1
            j += 2
            continue
        if two == b">>":
            depth -= 1
            j += 2
            if depth == 0:
                break
            continue
        if body[j:j + 1] == b"(":  # literal string, skip with escapes
            j += 1
            nest = 1
            while j < len(body) and nest:
                c = body[j]
                if c == 0x5C:
                    j += 2
                    continue
                if c == 0x28:
                    nest += 1
                elif c == 0x29:
                    nest -= 1
                j += 1
            continue
        j += 1
    o.dict_bytes = body[i:j]

    after = body[j:]
    m = re.match(rb"\s*stream(\r\n|\n|\r)", after)
    if m:
        o.stream_start = o.start + j + m.end()
        lm = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", o.dict_bytes)
        if lm:
            o.stream_len = int(lm.group(1))
        else:
            refm = re.search(rb"/Length\s+(\d+)\s+\d+\s+R", o.dict_bytes)
            if refm:
                ref = objs.get(int(refm.group(1)))
                if ref is not None:
                    v = re.search(rb"(\d+)", data[ref.start: ref.start + ref.raw_len])
                    if v:
                        o.stream_len = int(v.group(1))
        if o.stream_len is None:
            end = data.find(b"endstream", o.stream_start)
            o.stream_len = max(0, end - o.stream_start) if end > 0 else 0
    return o.dict_bytes


def dict_get_str(d, key):
    if not d:
        return None
    m = re.search(rb"/" + key + rb"\s*(\d+)\s+\d+\s+R", d)
    return int(m.group(1)) if m else None


def dict_get_ints(d, key):
    m = re.search(rb"/" + key + rb"\s*\[\s*([^\]]*)\]", d)
    if not m:
        return None
    return [float(x) for x in re.findall(rb"-?\d+\.?\d*", m.group(1))]


def resolve_pages(data, objs, root_num):
    """Walk /Root -> /Pages -> /Kids to get pages in true reading order."""
    root = objs.get(root_num)
    pages = []
    if root is None:
        return pages
    rd = parse_dict(data, objs, root)
    pages_tree = dict_get_str(rd, b"Pages")
    visited = set()

    def walk(num):
        if num in visited or num not in objs:
            return
        visited.add(num)
        d = parse_dict(data, objs, objs[num])
        if not d:
            return
        if re.search(rb"/Type\s*/Pages", d):
            km = re.search(rb"/Kids\s*\[([^\]]*)\]", d, re.S)
            if km:
                for kid in re.findall(rb"(\d+)\s+\d+\s+R", km.group(1)):
                    walk(int(kid))
        else:
            pages.append(num)

    if pages_tree is not None:
        walk(pages_tree)
    return pages


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else r"C:\harness工作区\spanish-reader\textbook.pdf"
    outdir = sys.argv[2] if len(sys.argv) > 2 else r"C:\harness工作区\spanish-reader\pages_raw"
    os.makedirs(outdir, exist_ok=True)

    with open(pdf, "rb") as f:
        data = f.read()
    print("loaded %.1f MB" % (len(data) / 1048576))

    objs = index_objects(data)
    print("objects:", len(objs))

    tail = data[-3000:]
    root_m = re.search(rb"/Root\s+(\d+)\s+\d+\s+R", tail)
    root_num = int(root_m.group(1)) if root_m else max(objs)
    print("root object:", root_num)

    page_nums = resolve_pages(data, objs, root_num)
    print("pages via page tree:", len(page_nums))

    if not page_nums:
        page_nums = [n for n in sorted(objs)
                     if re.search(rb"/Type\s*/Page\b", data[objs[n].start: objs[n].start + objs[n].raw_len])]
        print("pages via scan:", len(page_nums))

    def find_image(page_dict):
        """Resolve /Resources (direct or indirect) then pick the first image XObject."""
        res = page_dict
        rm = re.search(rb"/Resources\s+(\d+)\s+\d+\s+R", page_dict)
        if rm:
            ro = objs.get(int(rm.group(1)))
            if ro is not None:
                res = parse_dict(data, objs, ro) or b""
        xm = re.search(rb"/XObject\s*<<(.*?)>>", res, re.S)
        if not xm:
            xm = re.search(rb"/XObject\s+(\d+)\s+\d+\s+R", res)
            if xm:
                xo = objs.get(int(xm.group(1)))
                if xo is not None:
                    res2 = parse_dict(data, objs, xo) or b""
                    xm = re.search(rb"/XObject\s*<<(.*?)>>", res2, re.S)
        if not xm:
            return None
        for _, r in re.findall(rb"/(\w+)\s+(\d+)\s+\d+\s+R", xm.group(1)):
            od = parse_dict(data, objs, objs[int(r)])
            if od and b"/Image" in od:
                return int(r)
        return None

    manifest = []
    for idx, pnum in enumerate(page_nums):
        d = parse_dict(data, objs, objs[pnum]) or b""
        box = dict_get_ints(d, b"MediaBox") or [0, 0, 595, 842]
        img_num = find_image(d)
        rec = {"page": idx + 1, "page_obj": pnum,
               "width": box[2] - box[0], "height": box[3] - box[1],
               "media_box": box, "image_obj": img_num}
        if img_num is not None:
            io = objs[img_num]
            idict = parse_dict(data, objs, io)
            rec["img_w"] = (dict_get_ints(idict, b"Width") or [0])[0]
            rec["img_h"] = (dict_get_ints(idict, b"Height") or [0])[0]
            rec["filter"] = "DCT" if b"DCTDecode" in idict else "other"
            if io.stream_start is not None and rec["filter"] == "DCT":
                blob = data[io.stream_start: io.stream_start + io.stream_len]
                fn = "page_%04d.jpg" % (idx + 1)
                with open(os.path.join(outdir, fn), "wb") as g:
                    g.write(blob)
                rec["file"] = fn
        manifest.append(rec)
        if (idx + 1) % 50 == 0:
            print("  ...", idx + 1)

    with open(os.path.join(outdir, "pages_raw.json"), "w", encoding="utf-8") as g:
        json.dump(manifest, g, ensure_ascii=False, indent=1)

    with_img = sum(1 for r in manifest if r.get("file"))
    print("wrote %d pages, %d with jpeg" % (len(manifest), with_img))
    if manifest:
        r = manifest[0]
        print("page1: %.0fx%.0f pt, image %sx%s, filter=%s" %
              (r["width"], r["height"], r.get("img_w"), r.get("img_h"), r.get("filter")))


if __name__ == "__main__":
    main()
