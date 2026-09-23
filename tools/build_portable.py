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
2. 双击「用Edge打开.bat」   ← 推荐，它会用 Edge 打开
   （也可以直接双击 index.html，但那样可能被 Chrome 打开，发音会差很多）
3. 打开后点任意西班牙语单词，即可听到发音并看到中文释义

就这么简单。不需要安装任何东西，不需要联网也能阅读
（只有发音和「在线查词」需要联网）。

为什么一定要用 Edge
-------------------
本工具不内置音频，发音交给浏览器：
· Edge 自带微软的西班牙语在线自然语音，音质好、发音准
· Chrome 只能用系统里装的语音，而 Windows 默认只有中文语音，读不了
  西班牙语，会退化成在线音频，效果差一截

如果双击 .bat 没反应，就手动打开 Edge，把 index.html 拖进去。

功能介绍
--------
· 原版版面点读：完整保留课本扫描版面，逐词点击
· 点词发音    ：优先使用 Edge 的西班牙语自然语音
· 点词翻译    ：内置数千条词库，未收录的可一键在线查词
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

如果听不到声音
--------------
工具栏下方有一行小字，显示当前用的是哪一级语音：

  「系统语音」   正常，音质最好
  「在线音频」   没检测到西语系统语音，已自动降级（仍能出声）
  「不可用」     两样都失败，检查是否联网

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

# 启动器：绕开「双击 html 被 Chrome 打开 → 没有西语发音」这个最常见的坑。
# 内容刻意只用 ASCII —— .bat 里的中文受控制台代码页影响，在非中文 Windows 上会乱码，
# 而文件名用中文没问题（文件名由文件系统处理，不走批处理的代码页）。
LAUNCHER = r"""@echo off
rem Opens the reader in Microsoft Edge, which is the browser that actually
rem has a good Spanish voice on a stock Windows machine.
setlocal
set "HERE=%~dp0"
set "EDGE=%ProgramFiles(x86)%\Microsoft Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft Edge\Application\msedge.exe"

if exist "%EDGE%" (
  start "" "%EDGE%" "%HERE%index.html"
) else (
  echo.
  echo Microsoft Edge was not found on this machine.
  echo Opening with the default browser instead.
  echo.
  echo If you hear no Spanish audio, please open index.html with Edge manually.
  echo.
  start "" "%HERE%index.html"
)
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

    # 启动器必须用 GBK-ASCII 之外的编码？不需要：内容全是 ASCII，
    # 但换行用 CRLF，否则老式 cmd 解析会出问题。
    launcher = os.path.join(DIST, "用Edge打开.bat")
    with io.open(launcher, "w", encoding="ascii", newline="\r\n") as f:
        f.write(LAUNCHER)
    print("  wrote 用Edge打开.bat (%d bytes)" % os.path.getsize(launcher))

    grand = os.path.getsize(dst_html) + total
    print("\n  dist: %s" % DIST)
    print("  total %.1f MB" % (grand / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
