# -*- coding: utf-8 -*-
"""
Run the whole extraction pipeline in the correct order.

    python tools/run_all.py                 # everything
    python tools/run_all.py repair.py ...   # only the named steps

Data flow
    textbook.pdf
      -> pages_raw/*.jpg      raw page scans pulled out of the PDF      (extract_pages.py)
      -> pages/*.jpg          downscaled copies for the web reader      (resize_pages.ps1)
      -> data/ocr_all.json    Windows OCR, both engines, word boxes     (ocr_pages.ps1)
      -> data/pages_ocr.json  hotspots, Chinese-region noise removed    (build_pages.py)
      -> data/lex_glossary.json  canonical spellings from the GLOSARIO  (extract_glossary.py)
      -> data/lex_verbs.json  Spanish verb forms                        (conjugate.py)
      -> data/pages.json      FINAL hotspots, OCR damage repaired       (repair.py)
      -> data/vocab_raw.json  the book's own word lists + Chinese       (extract_dict.py)
      -> data/dict.json       merged dictionary for the reader          (build_dict.py)
"""
import subprocess, sys, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    ("build_pages.py", "OCR output -> page hotspots"),
    ("extract_glossary.py", "GLOSARIO -> canonical spelling lexicon"),
    ("conjugate.py", "Spanish verb morphology"),
    ("repair.py", "repair OCR damage -> data/pages.json"),
    ("extract_dict.py", "book word lists -> dictionary entries with Chinese"),
    ("build_dict.py", "merge dictionaries for the reader"),
    ("verify.py", "report residual damage + coverage"),
    ("check_after.py", "report residual unknown tokens"),
]

only = sys.argv[1:] or None
failed = []
for script, desc in STEPS:
    if only and script not in only:
        continue
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        print("\n### SKIP %s (not present)" % script)
        continue
    print("\n" + "=" * 78)
    print("### %s — %s" % (script, desc))
    print("=" * 78)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, path], env=env)
    if r.returncode != 0:
        print("!!! %s exited with code %d" % (script, r.returncode))
        failed.append(script)

print("\n" + "=" * 78)
if failed:
    print("FAILED steps:", ", ".join(failed))
    sys.exit(1)
print("all steps completed.")
