#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_fix.py — 通用后处理（对已清洗过的目录补跑共同规则）

当前规则（见 epub_clean_common.py）:
  1) 正文 chatu 去重：同一 (img src + 图注) 只保留首次出现（跨文件；彩图页整体跳过）
  2) 两个 <div class="chatu"> 之间不保留 <p class="sprt">…</p>（有则删）
  3) 文本节点规范化：NBSP→空格、○(U+25CB)→〇(U+3007)、中英之间不留空格、逐字 <i> 合并
  4) <blockquote> 内没有 class 的 <p> 补 class="bodytext"
  5) 删掉正文段首手工缩进用的全角空格「　」（styles.css 已用 text-indent）
  6) <html> 上 zh-TW/zh-Hant/zh-Hans/zh-HK/zh-cn 统一为 zh-CN（zh 保持）

用法:
  python epub_clean_fix.py process <dir> [--dry-run]
  python epub_clean_fix.py verify  <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys

from epub_clean_common import (postprocess, reset_dedupe, register_chatu,
                               count_dupe_chatu, count_sprt_between_chatu,
                               count_indent_spaces, count_lang_non_cn,
                               is_gallery, _CHATU, ensure_styles)


def list_files(d):
    files = []
    for pat in ("*.xhtml", "*.html"):
        files += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]

    def key(p):
        m = re.search(r"(\d+)", os.path.basename(p))
        return (0, int(m.group(1))) if m else (1, os.path.basename(p))
    return sorted(set(files), key=key)


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def process(d, dry=False):
    _st = ensure_styles(d)          # 先把 skill 内的 styles.css 放到目标目录
    if _st not in ("same", "copied"):
        print("styles.css: %s" % _st)
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

    reset_dedupe()
    tdup = tsprt = tind = 0
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if is_gallery(c):
            print("%-20s 彩图页，跳过（%d 张图）" % (name, len(_CHATU.findall(c))))
            continue
        nd = count_dupe_chatu(c)
        ns = count_sprt_between_chatu(c)
        ni = count_indent_spaces(c)
        nl = count_lang_non_cn(c)
        if not nd and not ns and not ni and not nl:
            register_chatu(c)          # 记入 seen，供后续文件比对
            continue
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        n = postprocess(c)
        write(os.path.join(outdir, name) if dry else fp, n)
        tdup += nd
        tsprt += ns
        tind += ni
        print("%-20s 删重复 chatu: %-2d 删 chatu 间 sprt: %-2d 删段首全角空格: %-2d 改 lang: %d"
              % (name, nd, ns, ni, nl))
    print("合计: 重复 chatu %d 处，chatu 间 sprt %d 处，段首全角空格 %d 段" % (tdup, tsprt, tind))
    print("RESULT: OK")


def verify_dir(d):
    reset_dedupe()
    bad_d = bad_s = bad_i = bad_l = 0
    for fp in list_files(d):
        c = read(fp)
        if is_gallery(c):
            continue
        nd = count_dupe_chatu(c)
        ns = count_sprt_between_chatu(c)
        ni = count_indent_spaces(c)
        nl = count_lang_non_cn(c)
        register_chatu(c)
        if nd:
            bad_d += nd
            print("%-20s 仍有 %d 处重复 chatu" % (os.path.basename(fp), nd))
        if ns:
            bad_s += ns
            print("%-20s 仍有 %d 处 chatu 间 sprt" % (os.path.basename(fp), ns))
        if ni:
            bad_i += ni
            print("%-20s 仍有 %d 段段首全角空格" % (os.path.basename(fp), ni))
        if nl:
            bad_l += nl
            print("%-20s 仍有 %d 处 lang 非 zh-CN" % (os.path.basename(fp), nl))
    ok = not (bad_d or bad_s or bad_i or bad_l)
    print("RESULT:", "PASS" if ok else
          "FAIL（重复 chatu %d，chatu 间 sprt %d，段首全角空格 %d，lang %d）"
          % (bad_d, bad_s, bad_i, bad_l))
    sys.exit(0 if ok else 1)


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
