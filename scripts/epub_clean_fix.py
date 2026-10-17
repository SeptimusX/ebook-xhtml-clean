#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_fix.py — 通用后处理（对已清洗过的目录补跑共同规则）

当前规则:
  1) 两个 <div class="chatu"> 之间不保留 <p class="sprt">…</p>（有则删）

用法:
  python epub_clean_fix.py process <dir> [--dry-run]
  python epub_clean_fix.py verify  <dir>
"""
import argparse, datetime, glob, os, shutil, sys

from epub_clean_common import strip_sprt_between_chatu, count_sprt_between_chatu


def list_files(d):
    files = []
    for pat in ("*.xhtml", "*.html"):
        files += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    return sorted(set(files))


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def process(d, dry=False):
    files = list_files(d)
    if not files:
        print("!! 未找到 *.xhtml / *.html")
        sys.exit(1)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "fix-%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录: %s" % outdir)
    total = 0
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        before = count_sprt_between_chatu(c)
        if not before:
            continue
        n = c
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        n = strip_sprt_between_chatu(c)
        write(os.path.join(outdir, name) if dry else fp, n)
        total += before
        print("%-20s 删除 chatu 之间的 sprt: %d" % (name, before))
    print("合计删除: %d" % total)
    print("RESULT: OK")


def verify_dir(d):
    bad = 0
    for fp in list_files(d):
        c = read(fp)
        k = count_sprt_between_chatu(c)
        if k:
            bad += k
            print("%-20s 仍有 %d 处 chatu 之间的 sprt" % (os.path.basename(fp), k))
    print("RESULT:", "PASS" if not bad else "FAIL（%d 处）" % bad)
    sys.exit(0 if not bad else 1)


def main():
    ap = argparse.ArgumentParser(description="EPUB xhtml 通用后处理")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("process", "verify"):
        sp = sub.add_parser(nm)
        sp.add_argument("dir")
        if nm == "process":
            sp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if not os.path.isdir(d):
        print("!! 目录不存在: %s" % d)
        sys.exit(1)
    if a.cmd == "process":
        process(d, dry=a.dry_run)
    else:
        verify_dir(d)


if __name__ == "__main__":
    main()
