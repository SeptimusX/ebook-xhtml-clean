#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_calibre_endnotes.py — calibre 繁体书 + 书末跨文件注释（profile Y）

识别特征（《帝国暮色》一类，衛城/遠足 版）:
  `<body class="calibre3">` + `<div class="calibre4">` 外壳，字体 css 在书根（`../../stylesheet.css` + `../../page_styles.css`）
  正文 `<p class="calibre5">`；诗行 `<p class="t"><span class="kfont">…</span></p>` 或 `<p class="calibre5"><span class="kfont">`
  全角空格占位段 `<p class="calibre5">　</p>`
  注释全部集中在书末「注释」章（ch18_split_00N），按章用 `<h6 class="calibre6">` 分组：
      `<p id="foot-ch01-1" class="footnote" epub:type="footnote"><a href="../Text/pre3.xhtml#back-pre-1" class="calibre13"><span class="no">1.</span> </a>注文</p>`
  正文引用 `<a class="ref" epub:type="noteref" id="back-ch01-1" href="ch18_split_000.xhtml#foot-ch01-1">1</a>`（跨文件）
  书目 `<p class="t1">`；目次 `<h5 class="calibre7">目次</h5>` + `<h4 class="calibre10">部</h4>` + `<p class="calibre9"><a class="bli">`
  整页图（书名页/部扉页/地图）是 `<svg><image xlink:href="../Images/x.jpg"/></svg>`

映射:
  css → 同目录 `styles.css`；`<html>` 补 xmlns:epub；解包 `div.calibre4`/`div.calibre1`
  整页图 → `<div class="chatu"><p class="image"><img src/></p></div>`
  正文 `<p class="calibre5">` → `p.bodytext`；全角空格占位段删除
  诗行（连续 `span.kfont` 段）→ `<blockquote class="poem">` + 每行 `<p class="bodytext">`；`──` 开头的落款 → `p.right`
  行内 `span.kfont` → `span.kai`；`span.italic` → `<i>`
  引用 → `<sup><a epub:type="noteref" href="文件#foot-…" id="back-…">[N]</a></sup>`（保持跨文件 href、每章 1..N）
  注文 `p.footnote` → `<p class="fnote" id="foot-…"><a href="文件#back-…">[N]</a> 注文</p>`
  `h6.calibre6` → `h2`（注释分组、作者简介）；`h5.calibre7`（简介人名）→ `p.center > b`
  目次：目次 → `h1`，部（h4）与地图/引言/序幕 → `p.toc1`，章行 → `p.toc2`
  书目 `p.t1` → `p.bodytext-noindent`；献词 `p.calibre11` → `p.center`
  版权页（colophon）→ `p.bodytext-noindent`，书名为 `p.center > b`，装饰 logo 图删除

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse
import datetime
import glob
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from epub_clean_common import postprocess, ensure_styles

HEAD_PAT = r'<div class="calibre4">\s*'
IMAGE_PAGES = {"title.xhtml", "part1.xhtml", "part2.xhtml", "part3.xhtml", "map1.xhtml", "map2.xhtml"}
ROLE = {
    "pre1.xhtml": "dedication",
    "pre2.xhtml": "epigraph",
    "contents.xhtml": "toc",
    "author.xhtml": "author",
    "colophon.xhtml": "colophon",
}

SPACER_P = re.compile(r'<p class="calibre\d+">\s*　\s*</p>\n?')
RE_REF = re.compile(r'<a class="ref" epub:type="noteref" id="back-([^"]+)" href="([^"]+)">(\d+)</a>')
RE_NOTE = re.compile(
    r'<p id="(foot-[^"]+)" class="footnote" epub:type="footnote"><a href="([^"]+)" class="calibre13">'
    r'<span class="no">(\d+)\.</span>\s*</a>(.*?)</p>', re.S)
RE_POEM = re.compile(r'(?:<p class="(?:calibre5|t)"><span class="kfont">(.*?)</span></p>\s*)+', re.S)


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def text_of(c):
    c = re.sub(r"<head>.*?</head>", "", c, flags=re.S)
    c = re.sub(r'<span class="no">(\d+)\.</span>', r"\1", c)   # 注号「1.」同 [1]
    c = re.sub(r"<[^>]+>", "", c)
    c = re.sub(r"\[(\d+)\]", r"\1", c)
    c = c.replace("\u25cb", "\u3007")
    return re.sub(r"\s+", "", c)


def list_files(d):
    return sorted(f for f in glob.glob(os.path.join(d, "*.xhtml")))


def role_of(name):
    if name in IMAGE_PAGES:
        return "image"
    return ROLE.get(name, "content")


def norm_href(h):
    return h.replace("../Text/", "").replace("OEBPS/Text/", "")


# ---------- 正文 ----------

def clean(c, name, role):
    body = c[c.find("<body"):]
    body = re.sub(r"^<body[^>]*>", "", body)
    body = re.sub(r"</body>.*$", "", body, flags=re.S)
    body = body.strip()
    body = re.sub(r'^<div class="calibre(?:1|4)">\s*', "", body)
    body = re.sub(r"\s*</div>$", "", body)
    body = SPACER_P.sub("", body)

    # 整页图
    if role == "image":
        m = re.search(r'<image[^>]*xlink:href="([^"]+)"', body)
        if m:
            return ('<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>\n</div>' % m.group(1))

    # 脚注
    body = RE_REF.sub(
        lambda m: '<sup><a epub:type="noteref" href="%s" id="back-%s">[%s]</a></sup>'
                  % (norm_href(m.group(2)), m.group(1), m.group(3)), body)
    body = RE_NOTE.sub(
        lambda m: '<p class="fnote" id="%s"><a href="%s">[%s]</a>%s</p>'
                  % (m.group(1), norm_href(m.group(2)), m.group(3),
                     m.group(4) if m.group(4).startswith(" ") else " " + m.group(4).lstrip()), body)

    # 诗行
    def poem(m):
        lines = re.findall(r'<p class="(?:calibre5|t)"><span class="kfont">(.*?)</span></p>', m.group(0), re.S)
        blocks, cur = [], []
        for ln in lines:
            txt = re.sub(r"</?span[^>]*>", "", ln.strip()).strip()
            plain = re.sub(r"<[^>]+>", "", txt).strip()
            if plain.startswith("──"):
                cur.append('<p class="right">%s</p>' % txt)
                blocks.append(cur)
                cur = []
            else:
                cur.append('<p class="bodytext">%s</p>' % txt)
        if cur:
            blocks.append(cur)
        return "\n".join('<blockquote class="poem">\n' + "\n".join(b) + "\n</blockquote>"
                          for b in blocks) + "\n"
    body = RE_POEM.sub(poem, body)

    # 行内 span
    body = re.sub(r'<span class="kfont">(.*?)</span>', r'<span class="kai">\1</span>', body, flags=re.S)
    body = re.sub(r'<span class="italic">(.*?)</span>', r"<i>\1</i>", body, flags=re.S)
    body = body.replace('<img class="pw"', '<img class="image-inline"')   # 行内字图：缩小显示
    body = re.sub(r'<a ([^>]*?)class="calibre13"([^>]*)>', r"<a \1\2>", body)
    body = body.replace(' title="None"', "")
    body = re.sub(r'<a class="bli" href="([^"]+)">', lambda m: '<a href="%s">' % norm_href(m.group(1)), body)

    # 标题
    if role == "toc":
        body = re.sub(r'<h5 class="calibre7">(.*?)</h5>', r"<h1>\1</h1>", body, flags=re.S)
        body = re.sub(r'<h4 class="calibre10">(.*?)</h4>', r'<p class="toc1">\1</p>', body, flags=re.S)
        body = re.sub(r'<p class="calibre9">(<a href="ch\d+[^"]*">.*?</a>)</p>',
                      r'<p class="toc2">\1</p>', body, flags=re.S)
        body = re.sub(r'<p class="calibre9">(<a href="[^"]*">.*?</a>)</p>',
                      r'<p class="toc1">\1</p>', body, flags=re.S)
    elif role == "author":
        body = re.sub(r'<h6 class="calibre6">(.*?)</h6>', r"<h2>\1</h2>", body, flags=re.S)
        body = re.sub(r'<h5 class="calibre7">(.*?)</h5>', r'<p class="center"><b>\1</b></p>', body, flags=re.S)
        body = body.replace('<p class="calibre8">', '<p class="bodytext">')
    elif role == "colophon":
        body = re.sub(r'<img[^>]*icon\d*\.png[^>]*/>\n?', "", body)
        body = re.sub(r'<h6 class="calibre6">(.*?)</h6>', r'<p class="center"><b>\1</b></p>', body, flags=re.S)
        body = body.replace('<p class="calibre14">', '<p class="bodytext-noindent">')
    else:
        body = re.sub(r'<h6 class="calibre6">(.*?)</h6>', r"<h2>\1</h2>", body, flags=re.S)
        body = re.sub(r'<h5 class="calibre7">(.*?)</h5>', r"<h2>\1</h2>", body, flags=re.S)

    body = re.sub(r'<(h[1-6])\s+class="[^"]*"([^>]*)>', r'<\1\2>', body)
    # 其余段落
    if role == "dedication":
        body = body.replace('<p class="calibre11">', '<p class="center">')
    body = body.replace('<p class="t1">', '<p class="bodytext-noindent">')
    body = body.replace('<p class="calibre5">', '<p class="bodytext">')
    body = body.replace('<p class="t">', '<p class="bodytext">')
    body = re.sub(r'<p class="calibre\d+">　</p>\n?', "", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def process_file(fp):
    name = os.path.basename(fp)
    c = read(fp)
    role = role_of(name)
    m = re.search(r"<title>(.*?)</title>", c, re.S)
    title = m.group(1).strip() if m else ""
    body = clean(c, name, role)
    h = ('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
         'xml:lang="zh-TW">\n<head>\n<title>%s</title>\n'
         '<link href="styles.css" rel="stylesheet" type="text/css"/>\n'
         "</head>\n<body>\n%s\n</body>\n</html>\n" % (title, body.strip()))
    return postprocess(h), role


# ---------- 校验 ----------

def verify_dir(d):
    ok = True
    files = list_files(d)
    ids = {os.path.basename(f): set(re.findall(r'\bid="([^"]+)"', read(f))) for f in files}
    # 全局注文表：foot-id -> (所在文件, 回链 id, 回链指向文件)
    notes = {}
    for fp in files:
        c = read(fp)
        for m in re.finditer(r'<p class="fnote" id="(foot-[^"]+)"><a href="([^"#]*)#(back-[^"]+)">', c):
            notes[m.group(1)] = (os.path.basename(fp), m.group(3), m.group(2))
    refs = 0
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs = []
        try:
            ET.fromstring(c.encode("utf-8"))
        except ET.ParseError as e:
            probs.append("XML %s" % e)
        if 'class="calibre' in c or '<span class="kfont"' in c:
            probs.append("残留 calibre/kfont")
        for m in re.finditer(r'epub:type="noteref" href="([^"#]*)#(foot-[^"]+)" id="(back-[^"]+)"', c):
            refs += 1
            tgt, fid, bid = m.group(1), m.group(2), m.group(3)
            n = notes.get(fid)
            if not n:
                probs.append("引用 #%s 无对应注文" % fid); break
            nfile, nback, nsrc = n
            if nback != bid or (tgt and tgt != nfile) or (nsrc and nsrc != name):
                probs.append("注 %s 与引用回链不符" % fid); break
        for m in re.finditer(r'(?:href|src)="([^"]+)"', c):
            h = m.group(1)
            if h.startswith(("http", "mailto:")) or h == "styles.css":
                continue
            fn, _, frag = h.partition("#")
            if not fn:
                fn = name
            if not os.path.exists(os.path.join(os.path.dirname(fp), fn)):
                probs.append("链接缺失 %s" % h)
            elif frag and frag not in ids.get(fn, set()):
                probs.append("锚点缺失 %s" % h)
        if probs:
            ok = False
            print("%-22s FAIL: %s" % (name, "; ".join(sorted(set(probs)))))
        else:
            print("%-22s OK  %d B" % (name, len(c.encode())))
    print("ref=%d note=%d %s" % (refs, len(notes), "匹配" if refs == len(notes) else "不匹配"))
    print("RESULT:", "PASS" if ok and refs == len(notes) else "FAIL")
    return 0 if ok and refs == len(notes) else 1


# ---------- package ----------

def clean_package(d):
    ops = []
    root = os.path.dirname(os.path.dirname(d))          # OEBPS/Text -> 书根
    opf = os.path.join(root, "content.opf")
    std = os.path.join(root, "stylesheet.css")
    pgs = os.path.join(root, "page_styles.css")
    if os.path.exists(opf):
        c = read(opf)
        for fn in ("stylesheet.css", "page_styles.css"):
            c = re.sub(r'\s*<item[^>]*href="[^"]*%s"[^>]*/>' % re.escape(fn), "", c)
        if 'id="css"' not in c:
            c = c.replace("</manifest>",
                          '    <item id="css" href="OEBPS/Text/styles.css" media-type="text/css"/>\n  </manifest>')
        write(opf, c)
        ops.append("opf: item=%d spine=%d" % (len(re.findall(r"<item\b", c)), len(re.findall(r"<itemref", c))))
    for p in (std, pgs):
        if os.path.exists(p):
            os.remove(p)
            ops.append("删除 %s" % os.path.basename(p))
    ops.append("styles.css: %s" % ensure_styles(d))
    return ops


def process(d, dry=False):
    files = list_files(d)
    if not files:
        print("!! 未找到 *.xhtml")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录:", outdir)
    ok = True
    results = {}
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        try:
            new, role = process_file(fp)
        except Exception as e:
            ok = False
            print("%-22s FAIL: %s" % (name, e))
            continue
        a, b = text_of(c), text_of(new)
        if a != b:
            ok = False
            print("%-22s FAIL: 文本比对不一致（%d vs %d）" % (name, len(a), len(b)))
            continue
        results[name] = new
        print("%-22s %-10s %6d B" % (name, role, len(new.encode())))
    if not ok:
        print("RESULT: FAIL（未写回）")
        return 1
    if dry:
        for n, v in results.items():
            write(os.path.join(outdir, n), v)
        print("RESULT: 预演完成")
        return 0
    for fp in files:
        shutil.copy2(fp, os.path.join(base, os.path.basename(fp)))
    for n, v in results.items():
        write(os.path.join(d, n), v)
    for line in clean_package(d):
        print("  " + line)
    print("RESULT: OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("analyze", "process", "verify"):
        sp = sub.add_parser(nm)
        sp.add_argument("dir")
        if nm == "process":
            sp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if a.cmd == "process":
        return process(d, dry=a.dry_run)
    if a.cmd == "verify":
        return verify_dir(d)
    files = list_files(d)
    print("文件:", len(files))
    for f in files:
        print("  %-22s %s" % (os.path.basename(f), role_of(os.path.basename(f))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
