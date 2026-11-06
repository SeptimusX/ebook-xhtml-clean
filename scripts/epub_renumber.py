#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_renumber.py — 按 opf spine（= 书内阅读顺序，与 toc.ncx 一致）给 xhtml 加序号前缀

约定：`NN_<原语义 stem>.xhtml`，如 `01_cover.xhtml`、`12_ch01.xhtml`、`31_ch18_notes_1.xhtml`。
  - NN 从 01 起，按 spine 顺序；超过 99 个自动扩位
  - 保留原有语义 stem（去掉旧的数字前缀，可反复执行 = 幂等）
  - 可用 `--rename 旧=新` 覆盖个别命名（如 ch18_split_000 → ch18_notes_1）
  - 同步改写：所有 xhtml 的 href/src、toc.ncx 的 content src、content.opf 的 item href
  - 备份到 %TEMP%\opencode\renumber-bak-<时间戳>

用法:
  python epub_renumber.py <书根目录> [--dry-run] [--rename ch18_split_000=ch18_notes_1 ...]
"""
import argparse
import datetime
import os
import re
import shutil
import sys

XHTML_EXT = (".xhtml", ".html", ".htm")


def read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, c):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def find_opf(root):
    for d in (root, os.path.join(root, "OEBPS"), os.path.join(root, "OPS")):
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.lower().endswith(".opf"):
                return os.path.join(d, f)
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".opf"):
                return os.path.join(dirpath, f)
    return None


def find_ncx(root, opf):
    for d in (os.path.dirname(opf), root):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(".ncx"):
                return os.path.join(d, f)
    return None


def rp(base, href):
    return os.path.normpath(os.path.join(base, href))


def stem_of(name):
    s = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"^\d+[_-]", "", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rename", action="append", default=[])
    a = ap.parse_args()
    root = os.path.abspath(a.dir)

    opf = find_opf(root)
    if not opf:
        print("!! 未找到 opf")
        return 1
    opf_dir = os.path.dirname(opf)
    c = read(opf)
    man = {}
    for m in re.finditer(r"<item\b[^>]*>", c):
        tag = m.group(0)
        i = re.search(r'\bid="([^"]+)"', tag)
        h = re.search(r'\bhref="([^"]+)"', tag)
        if i and h:
            man[i.group(1)] = h.group(1)
    spine = re.findall(r'<itemref\b[^>]*\bidref="([^"]+)"', c)
    if not spine:
        print("!! spine 为空")
        return 1

    over = {}
    for r in a.rename:
        if "=" not in r:
            print("!! --rename 需要 旧=新:", r)
            return 1
        k, v = r.split("=", 1)
        over[os.path.basename(k)] = v

    items = []
    for sid in spine:
        h = man.get(sid)
        if not h or not h.lower().endswith(XHTML_EXT):
            continue
        items.append((sid, h))
    w = max(2, len(str(len(items))))
    plan = []
    for idx, (sid, href) in enumerate(items, 1):
        src = rp(opf_dir, href)
        base = os.path.basename(src)
        stem = over.get(base, stem_of(base))
        stem = re.sub(r"\.x?html?$", "", stem, flags=re.I)
        new_base = "%0*d_%s%s" % (w, idx, stem, os.path.splitext(base)[1])
        plan.append((src, os.path.join(os.path.dirname(src), new_base), base, new_base))

    changed = [(o, n, ob, nb) for o, n, ob, nb in plan if ob != nb]
    for o, n, ob, nb in plan:
        print("%-28s -> %-30s %s" % (ob, nb, "改名" if ob != nb else "不变"))
    if not changed:
        print("无需改名（已是序号前缀）")
        return 0
    if a.dry_run:
        print("RESULT: 预演（%d 个待改）" % len(changed))
        return 0

    bak = os.path.join(os.environ.get("TEMP", "."), "opencode",
                       "renumber-bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(bak, exist_ok=True)
    for src, _n, _ob, _nb in plan:
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(bak, os.path.basename(src)))
    for f in (opf, find_ncx(root, opf)):
        if f and os.path.exists(f):
            shutil.copy2(f, os.path.join(bak, os.path.basename(f)))
    print("备份:", bak)

    rename_map = {}
    for src, dst, ob, nb in changed:
        if os.path.exists(dst):
            print("!! 目标已存在:", dst)
            return 1
        rename_map[ob] = nb
        os.replace(src, dst)

    pat = re.compile(r'(?<=["/])(%s)(?=["#])' % "|".join(re.escape(k) for k in rename_map))
    targets = []
    for dirpath, _d, files in os.walk(root):
        for f in files:
            if f.lower().endswith((".xhtml", ".html", ".htm", ".ncx", ".opf")):
                p = os.path.join(dirpath, f)
                if p not in targets:
                    targets.append(p)
    n = 0
    for p in targets:
        c0 = read(p)
        c1 = pat.sub(lambda m: rename_map[m.group(1)], c0)
        if c1 != c0:
            write(p, c1)
            n += 1
    print("改写引用文件: %d 个" % n)
    print("RESULT: OK（%d 个文件改名）" % len(rename_map))
    return 0


if __name__ == "__main__":
    sys.exit(main())
