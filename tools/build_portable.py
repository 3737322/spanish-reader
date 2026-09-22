# -*- coding: utf-8 -*-
"""
Build the portable, server-less edition.

`file://` pages may not fetch() local JSON, so the reader normally needs a
local web server.  In the portable build the three data files are inlined into
index.html as `window.__DSH_INLINE__`, and the page images are referenced with
relative <img> paths, which file:// does allow.  The result opens by
double-clicking index.html: no Python, no server, no install.

    python tools/build_portable.py

Produces  dist/西班牙语点读便携版/{index.html, pages/, 使用说明.txt}
"""
import io
import json
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "西班牙语点读便携版")

README = """西班牙语点读工具 · 便携版
======================================================

怎么用
------
1. 把整个文件夹解压出来（不要只解压 index.html）
2. 双击 index.html —— 用 Microsoft Edge 打开效果最好
3. 打开后点任意西班牙语单词，即可听到发音并看到中文释义

就这么简单。不需要安装任何东西，不需要联网也能阅读
（只有发音和「在线查词」需要联网）。

功能介绍
--------
· 原版版面点读：完整保留课本扫描版面，逐词点击
· 点词发音    ：优先使用 Edge 的西班牙语自然语音
· 点词翻译    ：内置 4700 余条西中词库，未收录的可一键在线查词
· 动词变位还原：点 tengo 会告诉你是 tener 的现在时第一人称单数
· 整句朗读    ：点行号圆点，或按住 Alt 点击句中任意词
· 全文搜索    ：忽略重音符号，输入 esta 也能搜到 está
· 生词本      ：⭐ 收藏、导出 txt
· 自动记住上次读到的页码

快捷键
------
  ←  →        上一页 / 下一页
  Esc         关闭词卡
  Ctrl + 滚轮  缩放页面

发音说明（重要）
----------------
本工具不内置音频，发音由浏览器负责：

  · 用 Edge 打开：走微软在线自然语音，西语发音质量最好
  · 用 Chrome 打开：本机若没装西班牙语语音包，会降级用在线 TTS 音频
  · 工具栏下方会显示当前用的是哪一级语音

如果完全听不到声音，检查两件事：
  1. 是不是用 Edge 打开的
  2. 电脑是否联网

想彻底离线发音：Windows 设置 → 时间和语言 → 语言和区域 →
添加「西班牙语(西班牙)」并勾选「语音」，装完刷新页面即可。

常见问题
--------
Q: 双击后页面空白 / 提示无法加载教材数据？
A: 多半是压缩包没解压完整。请确认 pages 文件夹和 index.html 在同一层，
   且 pages 里有 305 张 .jpg 图片。

Q: 提示「本地词库未收录」？
A: 说明这个词没进内置词库（多为专有名词或扫描识别残留），
   点词卡上的「🔍 在线查词」即可跳转查询。

Q: 能放到手机上用吗？
A: 图片和排版是为电脑屏幕做的，手机上能打开但读起来偏小。
   手机浏览器对 file:// 的支持也不一致，建议还是电脑上用。

版权提示
--------
本工具仅供个人学习使用。教材内容版权归原出版社所有，请勿公开传播或商用。
"""


def main():
    html_path = os.path.join(ROOT, "web", "index.html")
    with io.open(html_path, encoding="utf-8") as f:
        html = f.read()

    # ---- load the three data files -------------------------------------
    payload = {}
    sizes = {}
    for key, rel in (("pages", "data/pages.json"),
                     ("dict", "data/dict.json"),
                     ("lemmas", "data/lemmas.json")):
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(p):
            print("!! missing %s — run tools/run_all.py first" % rel)
            return 1
        with io.open(p, encoding="utf-8") as f:
            payload[key] = json.load(f)
        sizes[key] = os.path.getsize(p)
        print("  loaded %-22s %6.2f MB" % (rel, sizes[key] / 1048576))

    # `<` must be escaped so a string containing "</script>" cannot terminate
    # the inline block early.
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    inject = ('<script>/* 便携版内置数据：pages / dict / lemmas。'
              '由 tools/build_portable.py 生成，请勿手改。 */\n'
              'window.__DSH_INLINE__=' + blob + ';</script>\n')

    anchor = "<script>\n\"use strict\";"
    if anchor not in html:
        print("!! could not find the main <script> anchor in web/index.html")
        return 1
    out_html = html.replace(anchor, inject + anchor, 1)

    # ---- write the dist folder -----------------------------------------
    if os.path.isdir(DIST):
        print("  removing previous build…")
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    dst_html = os.path.join(DIST, "index.html")
    with io.open(dst_html, "w", encoding="utf-8") as f:
        f.write(out_html)
    print("  wrote index.html          %6.2f MB" % (os.path.getsize(dst_html) / 1048576))

    src_pages = os.path.join(ROOT, "pages")
    dst_pages = os.path.join(DIST, "pages")
    os.makedirs(dst_pages)
    t0 = time.time()
    n = 0
    total = 0
    for name in sorted(os.listdir(src_pages)):
        if not name.lower().endswith(".jpg"):
            continue
        s = os.path.join(src_pages, name)
        total += os.path.getsize(s)
        shutil.copy2(s, os.path.join(dst_pages, name))
        n += 1
        if n % 100 == 0:
            print("    copied %d pages…" % n)
    print("  copied %d pages           %6.2f MB  (%.1fs)" % (n, total / 1048576, time.time() - t0))

    with io.open(os.path.join(DIST, "使用说明.txt"), "w", encoding="utf-8") as f:
        f.write(README)

    grand = os.path.getsize(dst_html) + total
    print("\n  dist: %s" % DIST)
    print("  total %.1f MB" % (grand / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
