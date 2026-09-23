# -*- coding: utf-8 -*-
"""
从一份扫描版 PDF 一路做到可用的阅读器。

    python tools/run_all.py              # 全自动（已有产物会跳过，可断点续跑）
    python tools/run_all.py --force-pre  # 连抽取/缩放/OCR 也重做
    python tools/run_all.py repair.py    # 只跑指定步骤（不检查前置）

第一次跑大约 4~6 分钟（OCR 占大头）。中途断掉没关系，重跑会跳过已完成的步骤。

数据流
    textbook.pdf
      -> pages_raw/*.jpg        从 PDF 里抽出的原始扫描图      extract_pages.py
      -> pages/*.jpg            缩放后供网页展示               resize_pages.ps1
      -> data/ocr_all.json      Windows OCR（双引擎 + 词级坐标）ocr_pages.ps1
      -> data/pages_ocr.json    热区（剔除中文区里的拉丁乱码）   build_pages.py
      -> data/lex_glossary.json 规范拼写词库                   extract_glossary.py
      -> data/lex_verbs.json    动词变位表                     conjugate.py
      -> data/pages.json        ★ 最终热区（OCR 纠错后）        repair.py
      -> data/vocab_raw.json    课本词表 + 中文释义             extract_dict.py
      -> data/dict.json         ★ 阅读器用的词典               build_dict.py

前置条件
    · 把你自己合法获得的教材 PDF 放到仓库根目录，命名 textbook.pdf
    · Windows（第三步用系统自带 OCR，Mac/Linux 没有这个引擎）
    · Python 3.8+；Node.js 只有自检需要
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PDF = os.path.join(ROOT, "textbook.pdf")

IS_WINDOWS = os.name == "nt"
PS = "powershell.exe"          # Windows PowerShell 5.1：WinRT OCR 只能在这里调


def have(rel):
    return os.path.exists(os.path.join(ROOT, rel))


def hr(title):
    print("\n" + "=" * 78)
    print("### " + title)
    print("=" * 78)


def run(argv, label):
    """跑一个子进程；失败就返回 False 并打印清楚的提示。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    print("  $ " + os.path.basename(argv[0]) + " " +
          " ".join(os.path.basename(a) if a.endswith((".py", ".ps1")) else a for a in argv[1:]))
    try:
        r = subprocess.run(argv, env=env, cwd=ROOT)
    except FileNotFoundError as e:
        print("\n  !! 找不到命令：%s" % e.filename)
        if "powershell" in str(e.filename).lower():
            print("     这一步需要 Windows PowerShell。")
        return False
    except OSError as e:
        print("\n  !! 无法执行：%s" % e)
        return False
    if r.returncode != 0:
        print("\n  !! 「%s」失败（退出码 %d）" % (label, r.returncode))
        return False
    return True


# ---------------------------------------------------------------------------
# 前半段：把 PDF 变成 OCR 结果。每一步都检查产物，已有就跳过。
# ---------------------------------------------------------------------------
def pre_steps(force):
    if not os.path.exists(PDF):
        hr("缺少 textbook.pdf")
        print("  这个仓库只包含工具，不包含教材。请把你自己的 PDF 放到：")
        print("      %s" % PDF)
        print("")
        print("  命名必须是 textbook.pdf。想用别的名字，改本脚本顶部的 PDF 变量。")
        return False

    print("\n  找到教材：textbook.pdf  (%.1f MB)" % (os.path.getsize(PDF) / 1048576.0))

    plan = [
        ("抽取扫描页", "pages_raw/pages_raw.json",
         [sys.executable, os.path.join(HERE, "extract_pages.py")]),
        ("缩放展示图", "pages/_sizes.json",
         [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
          os.path.join(HERE, "resize_pages.ps1"),
          "-InDir", "pages_raw", "-OutDir", "pages", "-MaxWidth", "1600", "-Quality", "80"]),
        ("OCR 文字识别", "data/ocr_all.json",
         [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
          os.path.join(HERE, "ocr_pages.ps1"),
          "-InDir", "pages_raw", "-OutFile", "data/ocr_all.json", "-Langs", "en-GB,zh-Hans-CN"]),
    ]

    for label, out, argv in plan:
        if have(out) and not force:
            print("\n  跳过「%s」（已有 %s）" % (label, out))
            continue
        if not IS_WINDOWS and argv[0] == PS:
            hr("这一步需要 Windows")
            print("  「%s」用的是 Windows 系统自带的 OCR 引擎（Windows.Media.Ocr），" % label)
            print("  Mac / Linux 上没有这个引擎。")
            print("")
            print("  想在别的系统上跑，得换一个 OCR（例如 Tesseract），")
            print("  并重写 tools/repair.py 里的纠错规则——")
            print("  那套规则是针对 Windows OCR 的错误模式总结出来的，换引擎就不适用了。")
            return False
        hr(label)
        if not run(argv, label):
            return False

    return True


# ---------------------------------------------------------------------------
# 后半段：从 OCR 结果到阅读器用的数据
# ---------------------------------------------------------------------------
STEPS = [
    ("build_pages.py", "OCR 结果 → 逐词热区（剔除中文区域里的拉丁乱码）"),
    ("extract_glossary.py", "总词汇表 → 规范拼写词库"),
    ("conjugate.py", "西语动词变位生成"),
    ("repair.py", "OCR 纠错 → data/pages.json"),
    ("extract_dict.py", "课本词表 → 带中文释义的词典条目"),
    ("build_dict.py", "合并词典 → data/dict.json"),
    ("verify.py", "残留错误统计"),
    ("check_after.py", "未收录词统计"),
]


def main():
    args = sys.argv[1:]
    force_pre = "--force-pre" in args
    only = [a for a in args if a.endswith(".py")]

    print("=" * 78)
    print("  西班牙语点读工具 —— 从 PDF 构建全部数据")
    print("=" * 78)

    if not only:
        if not pre_steps(force_pre):
            print("\n" + "=" * 78)
            print("构建中止。修好上面的问题后重跑即可，已完成的步骤会自动跳过。")
            sys.exit(1)

    failed = None
    skipped = []
    for script, desc in STEPS:
        if only and script not in only:
            continue
        path = os.path.join(HERE, script)
        if not os.path.exists(path):
            skipped.append(script)
            continue
        hr("%s — %s" % (script, desc))
        if not run([sys.executable, path], script):
            failed = script
            break                      # 后续步骤依赖前一步的产物，不再往下跑

    print("\n" + "=" * 78)
    if failed:
        print("构建失败于：%s" % failed)
        print("修好后重跑 python tools/run_all.py 即可，前面的步骤会自动跳过。")
        sys.exit(1)
    if skipped:
        print("跳过（文件不存在）：%s" % ", ".join(skipped))

    print("构建完成。")
    print("")
    print("  启动阅读器：  python serve.py")
    print("  自检（可选）：python tools/check_all.py")
    print("  打包便携版：  python tools/build_portable.py")


if __name__ == "__main__":
    main()
