# -*- coding: utf-8 -*-
"""
构建内置演示（demo/）。

    python tools/build_demo.py

为什么需要它
    仓库里不含教材内容，所以刚克隆下来的人没有东西可看。这个脚本用
    tools/make_demo_pages.ps1 渲染 3 页合成「教材」（正文取自公版的
    《堂吉诃德》开篇，词汇表与练习题为本项目自写），然后**跑真正的流水线**
    —— 不另写一套简化逻辑。

    这样做有两个好处：
      1. 克隆者执行 python serve.py 就能立刻看到阅读器在跑
      2. 证明流水线对一本它从没见过的书同样有效

实现方式
    把各工具的模块级 ROOT 临时指向 demo/，于是同一套代码把产物写进 demo/data/。
    三个与教材无关的通用词库（常用词、缩合词、不规则动词）先从仓库根的 data/
    复制过来，它们不在 demo 里重复提交（见 .gitignore）。
"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEMO = os.path.join(REPO, "demo")
DEMO_DATA = os.path.join(DEMO, "data")

sys.path.insert(0, HERE)

GENERIC = ["dict_seed.json", "dict_extra.json", "lex_irregular.json"]

# 这些模块的 main() 都靠模块级 ROOT 定位输入输出，改掉它就等于换项目目录
PIPELINE = [
    ("build_pages", "OCR 结果 → 逐词热区"),
    ("extract_glossary", "词表页 → 规范拼写词库"),
    ("conjugate", "西语动词变位生成"),
    ("repair", "OCR 纠错 → pages.json"),
    ("extract_dict", "词表页 → 带释义的词典条目"),
    ("build_dict", "合并词典 → dict.json / lemmas.json"),
]


def step(msg):
    print("\n" + "=" * 70)
    print("### " + msg)
    print("=" * 70)


def main():
    print("=" * 70)
    print("  构建内置演示")
    print("=" * 70)

    os.makedirs(DEMO_DATA, exist_ok=True)
    os.makedirs(os.path.join(DEMO, "pages"), exist_ok=True)

    # ---- 1. 渲染页面 ----------------------------------------------------
    step("渲染演示页面")
    pages = [f for f in os.listdir(os.path.join(DEMO, "pages")) if f.endswith(".jpg")]
    if pages:
        print("  已有 %d 页，跳过（要重做就删掉 demo/pages/*.jpg）" % len(pages))
    else:
        ps = os.path.join(HERE, "make_demo_pages.ps1")
        if os.name != "nt":
            print("  !! 渲染需要 Windows（用的是 WPF 的文字绘制）")
            return 1
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", ps], cwd=REPO)
        if r.returncode != 0:
            print("  !! 渲染失败")
            return 1

    # ---- 2. OCR ---------------------------------------------------------
    step("对演示页做 OCR")
    ocr_out = os.path.join(DEMO_DATA, "ocr_all.json")
    if os.path.exists(ocr_out):
        print("  已有 ocr_all.json，跳过")
    else:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", os.path.join(HERE, "ocr_pages.ps1"),
                            "-InDir", os.path.join(DEMO, "pages"),
                            "-OutFile", ocr_out,
                            "-Langs", "en-GB,zh-Hans-CN"], cwd=REPO)
        if r.returncode != 0:
            print("  !! OCR 失败")
            return 1

    # ---- 3. 通用词库就位（不重复提交）-----------------------------------
    step("准备通用词库")
    for name in GENERIC:
        src = os.path.join(REPO, "data", name)
        if not os.path.exists(src):
            print("  !! 缺少 %s" % src)
            return 1
        shutil.copy2(src, os.path.join(DEMO_DATA, name))
        print("  复制 %s" % name)

    # ---- 4. 跑真正的流水线 ----------------------------------------------
    for modname, desc in PIPELINE:
        step("%s.py — %s" % (modname, desc))
        mod = __import__(modname)
        mod.ROOT = DEMO            # <- 只改这一处，代码完全复用
        try:
            mod.main()
        except SystemExit as e:
            if e.code:
                print("  !! %s 以退出码 %s 结束" % (modname, e.code))
                return 1
        except Exception as e:
            print("  !! %s 抛出异常：%s: %s" % (modname, type(e).__name__, e))
            return 1

    # ---- 5. 结果 --------------------------------------------------------
    step("演示构建完成")
    total = 0
    for root, _dirs, files in os.walk(DEMO):
        for f in files:
            p = os.path.join(root, f)
            total += os.path.getsize(p)
    print("  demo/ 总体积 %.2f MB" % (total / 1048576.0))
    print("")
    print("  现在可以直接： python serve.py")
    print("  未构建教材数据时，服务会自动切到这份演示。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
