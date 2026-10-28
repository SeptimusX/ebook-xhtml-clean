#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_kindle_calibre2.py — Kindle（AZW3）经 calibre 转码的另一套类号（profile U）

与 profile Q（epub_clean_kindle_calibre.py）同源，但类号分配不同，特征：
  标题不是 h1，而是 **blockquote**：
      <blockquote id="fileposNNN" class="calibre_13"><span class="calibre2"><span class="bold">
        <span class="calibre_14">第一章</span></span></span></blockquote>
      <blockquote class="calibre_15"><span class="calibre7"><span class="bold">章名</span></span></blockquote>
      （單元标题如 導論/結語/參考書目/誌謝 只有 calibre_13，或直接用 p.calibre_4）
  节标题 <p id="fileposNNN" class="calibre_4"><span class="calibre1"><span class="bold">…</span>…</p>
  正文 p.calibre_7 / _8 / _16 / _20 / _26 / _30；推荐序署名 p.calibre_6
  图 <p class="calibre_"><img src="images/NNNNN.jpg"/></p> + 图注 <blockquote class="calibre_18">…</blockquote>
  尾注 <ol class="calibre_11"><li value="N" id="fileposNNN" class="calibre_12">注文
        <a href="#fileposNNN"><span class="calibre6">↩</span></a></li>…</ol>
  正文引用 <sup class="calibre3"><small id="fileposNNN" class="calibre4"><a href="#fileposNNN">
        <span class="calibre5"><span class="calibre_9">[N  ]</span></span></a></small></sup>
  有序引文清单 <ol class="calibre_11"><li class="calibre_25">…</li></ol>（保留 ol/li，编号即内容）
  参考文献 <p class="calibre_28">小节</p> + <ul class="calibre_29"><li class="calibre_25">条目</li></ul>
  书内目录 <p class="calibre_31">Table of Contents</p> + <ol class="calibre_33"><li class="calibre_34">
        <a href="…">章</a><ol class="calibre_35"><li class="calibre_34"><a href="…">节</a></li></ol></li></ol>
  空壳 <a></a>、<div class="calibre_10|24|32"> </div>、<div class="mbp_pagebreak">

映射:
  章   -> <h1 id="fileposNNN"><span class="subtitle">第一章</span><br/>章名</h1>（单行则 <h1>标题</h1>）
  节   -> <h2 id="fileposNNN">…</h2>（文件中第一个 p.calibre_4 且无章标题时作 h1）
  正文 -> p.bodytext；署名 -> p.author；参考文献条目 -> p.bodytext
  图+图注 -> div.chatu
  引用 -> <sup><a epub:type="noteref" href="#foot-K" id="noteref-K">[K]</a></sup>
  注文 -> 章末 <hr/> + <p class="fnote" id="foot-K"><a href="#noteref-K">[K]</a> …</p>（每文件 1..N）
  目录 -> <h1>目次</h1> + p.toc1/p.toc2
  封面 titlepage.xhtml -> body.cover
  .html -> .xhtml；css -> 单一 styles.css；可删的重复封面页 index_split_000 一并清理 opf/spine

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

COVER = "titlepage.xhtml"
DROP_PAGES = {"index_split_000.html"}          # 与封面同图的重复页
TOC_PAGE = "index_split_018.html"
DROP_IMAGES = {"images/00003.jpg"}             # 随重复页一起删

ALLOWED_CLASSES = {
    "bodytext", "bodytext-noindent", "fnote", "fnotel", "image", "caption",
    "chatu", "toutu", "center", "right", "left", "left2", "toc1", "toc2",
    "intro", "poem", "blockcenter", "menu", "sprt", "pgbrk", "cover",
    "date", "author", "box", "subtitle",
}


# ---------- 基础 ----------

def list_files(d):
    fs = []
    for pat in ("*.html", "*.xhtml"):
        fs += [f for f in glob.glob(os.path.join(d, pat))]
    def key(p):
        m = re.search(r"(\d+)", os.path.basename(p))
        return (0, int(m.group(1))) if m else (1, os.path.basename(p))
    return sorted(set(fs), key=key)


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()


def text_of(c):
    c = re.sub(r"<head>.*?</head>", "", c, flags=re.S)
    c = re.sub(r"<sup[^>]*>.*?</sup>", "", c, flags=re.S)   # 注号整体不计入比对
    c = re.sub(r"<a[^>]*>\[\d+\]</a>", "", c)             # fnote 的 [N] 前缀
    c = re.sub(r"<[^>]+>", "", c)
    return (re.sub(r"\s+", "", c).replace("\u25cb", "\u3007")
            .translate({0x21A9: None, 0x21BA: None, 0xFE0E: None}))


def title_of(c):
    m = re.search(r"<title>(.*?)</title>", c, re.S)
    return plain(m.group(1)) if m else ""


def doc(title, body, attrs=""):
    return ('<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops">\n<head>\n'
            "<title>%s</title>\n"
            '<link href="styles.css" rel="stylesheet" type="text/css"/>\n'
            "</head>\n<body%s>\n%s\n</body>\n</html>\n" % (title, attrs, body.strip()))


# ---------- 各段处理 ----------

RE_NOTES = re.compile(r'<ol[^>]*class="calibre_11"[^>]*>(.*?)</ol>', re.S)
RE_NOTE_LI = re.compile(r'<li([^>]*)class="calibre_12"([^>]*)>(.*?)</li>', re.S)
RE_REF = re.compile(
    r'<sup[^>]*class="calibre3"[^>]*>\s*<small([^>]*)>(.*?)</small>\s*</sup>', re.S)
RE_IMG = re.compile(
    r'<p[^>]*>\s*<img([^>]*)/>\s*</p>\s*'
    r'(?:<blockquote[^>]*class="calibre_18"[^>]*>(.*?)</blockquote>)?', re.S)
RE_HEAD = re.compile(
    r'<blockquote([^>]*)class="calibre_13"([^>]*)>(.*?)</blockquote>\s*'
    r'(?:<blockquote[^>]*class="calibre_15"[^>]*>(.*?)</blockquote>)?', re.S)


def clean_note_text(h):
    h = re.sub(r'<a[^>]*>\s*<span[^>]*>[^<]*</span>\s*</a>', "", h)     # 回链 ↩
    h = re.sub(r"<a[^>]*>\s*</a>", "", h)
    return h.strip()


def process_content(c, name, ctx):
    body = c[c.find("<body"):]
    body = re.sub(r"^<body[^>]*>", "", body)
    body = re.sub(r"</body>.*$", "", body, flags=re.S)

    # 1) 空壳
    body = re.sub(r"<a></a>", "", body)
    body = re.sub(r'<a\s*/>', "", body)
    body = re.sub(r'<div[^>]*class="calibre_(?:10|24|32)"[^>]*>\s*</div>', "", body)
    body = re.sub(r'<div[^>]*class="mbp_pagebreak"[^>]*>\s*</div>', "", body)

    # 2) 尾注：取出，按出现顺序编号
    notes = []

    def grab_notes(m):
        inner = m.group(1)
        lis = list(RE_NOTE_LI.finditer(inner))
        if not lis:
            return m.group(0)                       # 有序引文清单，稍后处理
        for li in lis:
            attr = li.group(1) + li.group(2)
            nid = re.search(r'id="([^"]+)"', attr)
            notes.append((nid.group(1) if nid else "", clean_note_text(li.group(3))))
        return ""
    body = RE_NOTES.sub(grab_notes, body)

    # 3) 引用 -> noteref（按注文 id 对应）
    kmap = {nid: i + 1 for i, (nid, _t) in enumerate(notes) if nid}
    seq = [0]

    def ref(m):
        seg = m.group(2)
        href = re.search(r'href="#([^"]+)"', seg)
        num = re.search(r"\[(\d+)\s*\]", plain(seg))
        k = kmap.get(href.group(1)) if href else None
        if k is None:
            seq[0] += 1
            k = seq[0]
        return ('<sup><a epub:type="noteref" href="#foot-%d" id="noteref-%d">[%d]</a></sup>'
                % (k, k, k))
    body = RE_REF.sub(ref, body)

    # 4) 章标题（calibre_13 [+ calibre_15]）
    ctx["h1"] = False

    def head(m):
        attrs = m.group(1) + m.group(2)
        hid = re.search(r'id="([^"]+)"', attrs)
        t1 = plain(m.group(3))
        t2 = plain(m.group(4)) if m.group(4) else ""
        ctx["h1"] = True
        idattr = ' id="%s"' % hid.group(1) if hid else ""
        if t2:
            return '<h1%s><span class="subtitle">%s</span><br/>%s</h1>' % (idattr, t1, t2)
        return "<h1%s>%s</h1>" % (idattr, t1)
    body = RE_HEAD.sub(head, body)

    # 5) 图 + 图注
    def img(m):
        attrs = m.group(1)
        src = re.search(r'src="([^"]+)"', attrs).group(1)
        cap = plain(m.group(2)) if m.group(2) else ""
        out = ['<div class="chatu">',
               '<p class="image"><img src="%s" alt=""/></p>' % src]
        if cap:
            out.append('<p class="caption">%s</p>' % cap)
        out.append("</div>")
        return "\n".join(out)
    body = RE_IMG.sub(img, body)

    # 6) 有序引文清单：去掉 class 保留 ol/li
    def quote_list(m):
        if 'calibre_12' in m.group(1):
            return m.group(0)
        inner = re.sub(r'<li[^>]*class="calibre_25"[^>]*>', "<li>", m.group(1))
        inner = re.sub(r"<a></a>", "", inner)
        return "<ol>%s</ol>" % inner
    body = RE_NOTES.sub(quote_list, body)

    # 7) 参考文献：ul.calibre_29 的条目 -> 段落
    def bib(m):
        items = re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S)
        return "\n".join('<p class="bodytext">%s</p>' % i.strip() for i in items)
    body = re.sub(r'<ul[^>]*class="calibre_29"[^>]*>(.*?)</ul>', bib, body, flags=re.S)

    # 8) 段落
    sec_flag = [0]

    def pmap(m):
        attrs, txt = m.group(1), m.group(2)
        cm = re.search(r'class="([^"]*)"', attrs)
        cls = cm.group(1) if cm else ""
        hid = re.search(r'id="([^"]*)"', attrs)
        idattr = ' id="%s"' % hid.group(1) if hid else ""
        body_txt = txt.strip()
        if cls in ("image", "caption", "fnote"):
            return m.group(0)
        if cls == "calibre_6":
            return '<p class="author">%s</p>' % body_txt   # 推荐序/序跋署名
        if cls in ("calibre_4", "calibre_28"):
            if cls == "calibre_4" and sec_flag[0] == 0 and not ctx["h1"]:
                sec_flag[0] = 1
                return "<h1%s>%s</h1>" % (idattr, plain(body_txt))
            return "<h2%s>%s</h2>" % (idattr, plain(body_txt))
        if not plain(body_txt):
            return ""
        return '<p class="bodytext">%s</p>' % body_txt
    body = re.sub(r"<p([^>]*)>(.*?)</p>", pmap, body, flags=re.S)

    # 9) span / br
    body = re.sub(r'<span[^>]*class="bold"[^>]*>(.*?)</span>', r"<b>\1</b>", body, flags=re.S)
    body = re.sub(r'<span[^>]*class="italic"[^>]*>(.*?)</span>', r"<i>\1</i>", body, flags=re.S)
    while True:
        new = re.sub(r'<span[^>]*class="[^"]*(?:calibre[^"]*)"[^>]*>(.*?)</span>', r"\1", body, flags=re.S)
        new = re.sub(r'<span>(.*?)</span>', r"\1", new, flags=re.S)
        if new == body:
            break
        body = new
    body = re.sub(r'<br[^>]*/>', "<br/>", body)
    body = re.sub(r"\n{3,}", "\n\n", body)

    # 10) 章末注文
    if notes:
        lines = ["<hr/>"]
        for i, (nid, txt) in enumerate(notes, 1):
            txt = re.sub(r"<[^>]+>", "", txt) if "<" in txt else txt
            lines.append('<p class="fnote" id="foot-%d"><a href="#noteref-%d">[%d]</a> %s</p>'
                         % (i, i, i, txt.strip()))
        body = body.rstrip() + "\n" + "\n".join(lines) + "\n"
    return body


def process_toc(c, name, ctx):
    body = c[c.find("<body"):]
    body = re.sub(r"^<body[^>]*>", "", body)
    body = re.sub(r"</body>.*$", "", body, flags=re.S)
    body = re.sub(r"<a></a>", "", body)
    body = re.sub(r'<p[^>]*class="calibre_31"[^>]*>.*?</p>', "", body, flags=re.S)
    body = re.sub(r'<div[^>]*class="calibre_32"[^>]*>\s*</div>', "", body)
    body = re.sub(r'<div[^>]*class="mbp_pagebreak"[^>]*>\s*</div>', "", body)

    def lis(html, cls):
        out = []
        for m in re.finditer(r"<li[^>]*>(.*?)</li>", html, re.S):
            inner = m.group(1)
            link = re.search(r"<a[^>]*>.*?</a>", inner, re.S)
            rest = inner[link.end():].strip() if link else ""
            out.append('<p class="%s">%s</p>' % (cls, (link.group(0) if link else inner).strip()))
            if rest:
                out.append(rest)
        return "\n".join(out)

    body = re.sub(r'<ol[^>]*class="calibre_35"[^>]*>(.*?)</ol>',
                  lambda m: lis(m.group(1), "toc2"), body, flags=re.S)
    body = re.sub(r'<ol[^>]*class="calibre_33"[^>]*>(.*?)</ol>',
                  lambda m: lis(m.group(1), "toc1"), body, flags=re.S)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return "<h1>目次</h1>\n" + body.strip()


def process_cover(c, book_title=None):
    title = book_title or title_of(c) or "封面"
    return ('<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n'
            "<title>%s</title>\n"
            '<link href="styles.css" rel="stylesheet" type="text/css"/>\n'
            "</head>\n<body class=\"cover\">\n"
            '<div><img src="images/calibre_cover.jpg" alt="封面"/></div>\n'
            "</body>\n</html>\n" % title)


def process_file(fp, book_title=""):
    name = os.path.basename(fp)
    c = read(fp)
    title = title_of(c) or "意外的國度"
    ctx = {}

    if name == COVER:
        return process_cover(c, book_title), ctx
    if name == TOC_PAGE:
        body = process_toc(c, name, ctx)
    else:
        body = process_content(c, name, ctx)
    h = doc(title, body)
    return h, ctx


# ---------- 包级 ----------

def clean_package(d):
    ops = []
    # 1) 删重复页与随之作废的图片
    for p in DROP_PAGES:
        fp = os.path.join(d, p)
        if os.path.exists(fp):
            os.remove(fp)
            ops.append("删除 %s" % p)
    for p in DROP_IMAGES:
        fp = os.path.join(d, p)
        if os.path.exists(fp):
            os.remove(fp)
            ops.append("删除 %s" % p)
    # 2) 旧 css
    for p in ("stylesheet.css", "page_styles.css"):
        fp = os.path.join(d, p)
        if os.path.exists(fp):
            os.remove(fp)
            ops.append("删除 %s" % p)
    ops.append("styles.css: %s" % ensure_styles(d))

    # 3) opf
    opf = None
    for fn in ("content.opf", "volume.opf", "package.opf"):
        if os.path.exists(os.path.join(d, fn)):
            opf = os.path.join(d, fn)
            break
    if opf:
        c = read(opf)
        drop_ids = set()

        def item(m):
            s = m.group(0)
            h = re.search(r'href="([^"]+)"', s)
            i = re.search(r'\bid="([^"]+)"', s)
            if h and (h.group(1) in DROP_PAGES or h.group(1) in DROP_IMAGES
                      or h.group(1) in ("stylesheet.css", "page_styles.css")):
                if i:
                    drop_ids.add(i.group(1))
                return ""
            if h:
                s = s.replace('href="%s"' % h.group(1), 'href="%s"' % h.group(1).replace(".html", ".xhtml"))
            return s
        c = re.sub(r"<item\b[^>]*/>", item, c)

        def itemref(m):
            i = re.search(r'idref="([^"]+)"', m.group(0))
            return "" if i and i.group(1) in drop_ids else m.group(0)
        c = re.sub(r"<itemref\b[^>]*/>", itemref, c)
        c = re.sub(r'<item[^>]*href="[^"]*stylesheet\.css"[^>]*/>', "", c)
        if 'id="styles.css"' not in c:
            c = c.replace("</manifest>",
                          '    <item href="styles.css" id="styles.css" media-type="text/css"/>\n  </manifest>')
        write(opf, c)
        ops.append("%s: item=%d itemref=%d" % (os.path.basename(opf),
                                               len(re.findall(r"<item\b", c)),
                                               len(re.findall(r"<itemref\b", c))))
    # 4) ncx
    ncx = os.path.join(d, "toc.ncx")
    if os.path.exists(ncx):
        c = read(ncx)
        c = re.sub(r'(<content src="[^"]*?)\.html', r"\1.xhtml", c)
        c = re.sub(r'<navPoint[^>]*>\s*<navLabel>\s*<text>[^<]*</text>\s*</navLabel>\s*'
                   r'<content src="index_split_000\.xhtml"/>\s*</navPoint>', "", c)
        write(ncx, c)
        ops.append("toc.ncx 链接 .html -> .xhtml")
    return ops


def rename_pages(d):
    """*.html -> *.xhtml（内容文件），并同步所有 href"""
    ren = {}
    for fp in glob.glob(os.path.join(d, "*.html")):
        new = fp[:-5] + ".xhtml"
        ren[os.path.basename(fp)] = os.path.basename(new)
        os.replace(fp, new)
    for fp in glob.glob(os.path.join(d, "*.xhtml")):
        c = read(fp)
        new = c
        for old, nn in ren.items():
            new = new.replace(old, nn)
        if new != c:
            write(fp, new)
    return len(ren)


# ---------- 校验 ----------

def verify_content(c, name):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except ET.ParseError as e:
        probs.append("XML %s" % e)
        return probs, {}
    for bad in ('class="calibre', 'class="mbp_pagebreak', "<a></a>", "display:none"):
        if bad in c:
            probs.append("残留 %s" % bad)
    refs = re.findall(r'epub:type="noteref" href="#foot-(\d+)" id="noteref-(\d+)"', c)
    notes = re.findall(r'<p class="fnote" id="foot-(\d+)"><a href="#noteref-(\d+)"', c)
    if len(refs) != len(notes):
        probs.append("noteref(%d) != fnote(%d)" % (len(refs), len(notes)))
    for n, b in notes:
        if n != b:
            probs.append("注 foot-%s 回链 noteref-%s 不一致" % (n, b))
            break
    for m in re.finditer(r'<div class="chatu">(.*?)</div>', c, re.S):
        if "<img" not in m.group(1):
            probs.append("chatu 缺图")
            break
    for m in re.finditer(r'<(h1|h2)[^>]*>(.*?)</\1>', c, re.S):   # 标题「」成对
        t = re.sub(r'<[^>]+>', '', m.group(2))
        if t.count('「') != t.count('」'):
            probs.append("标题引号不成对: %s" % t[:24])
            break
    for m in re.finditer(r'<p class="toc[12]">(.*?)</p>', c, re.S):
        t = re.sub(r'<[^>]+>', '', m.group(1))
        if t.count('「') != t.count('」'):
            probs.append("目录行引号不成对: %s" % t[:24])
            break
    for cls in set(re.findall(r'class="([^"]+)"', c)):
        for one in cls.split():
            if one not in ALLOWED_CLASSES:
                probs.append("未知 class: %s" % one)
                break
    info = {"chatu": len(re.findall(r'<div class="chatu">', c)),
            "fnote": len(notes), "h1": len(re.findall(r"<h1", c)),
            "h2": len(re.findall(r"<h2", c)), "toc": len(re.findall(r'class="toc', c))}
    return probs, info


def verify_dir(d):
    ok = True
    files = list_files(d)
    ids = {}
    for fp in files:
        ids[os.path.basename(fp)] = set(re.findall(r'\bid="([^"]+)"', read(fp)))
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs, info = verify_content(c, name)
        for m in re.finditer(r'href="([^"]+)"', c):
            h = m.group(1)
            if h.startswith(("http", "mailto:")) or h == "styles.css":
                continue
            fn, _, frag = h.partition("#")
            fn = fn or name
            if fn not in ids:
                probs.append("链接目标缺失 %s" % h)
            elif frag and frag not in ids[fn]:
                probs.append("锚点缺失 %s" % h)
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(sorted(set(probs)))))
        else:
            print("%-24s OK  %s" % (name, " ".join("%s=%d" % kv for kv in sorted(info.items()))))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---------- analyze ----------

def analyze(d, out=None):
    files = list_files(d)
    L = ["目录: %s" % d, "xhtml/html: %d" % len(files)]
    for key, pat in (("blockquote.calibre_13", r'class="calibre_13"'),
                     ("blockquote.calibre_15", r'class="calibre_15"'),
                     ("p.calibre_4 节标题", r'class="calibre_4"'),
                     ("p.calibre_6 署名", r'class="calibre_6"'),
                     ("图片段 p.calibre_", r'class="calibre_"[^>]*>\s*<img'),
                     ("图注 blockquote_18", r'class="calibre_18"'),
                     ("尾注 li.calibre_12", r'class="calibre_12"'),
                     ("引用 sup.calibre3", r'class="calibre3"'),
                     ("引文清单 li.calibre_25", r'class="calibre_25"'),
                     ("参考文献 ul.calibre_29", r'class="calibre_29"'),
                     ("书内目录 li.calibre_34", r'class="calibre_34"'),
                     ("空壳 <a></a>", r"<a></a>")):
        L.append("  %-24s %d" % (key, sum(len(re.findall(pat, read(f))) for f in files)))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)
    return rep


# ---------- process ----------

def process(d, dry=False):
    files = list_files(d)
    if not files:
        print("!! 未找到 *.html / *.xhtml")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录: %s" % outdir)
    ok = True
    results = {}
    book_title = ""
    for fp in files:
        if os.path.basename(fp) not in (COVER,) and not book_title:
            book_title = title_of(read(fp))
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        try:
            new, ctx = process_file(fp, book_title)
            new = postprocess(new)
        except Exception as e:
            ok = False
            print("%-24s FAIL: %s" % (name, e))
            continue
        probs, info = verify_content(new, name)
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
            continue
        a, b = text_of(c), text_of(new)
        if name == TOC_PAGE:
            a = a.replace("TableofContents", "")
            b = b.replace("目次", "")
        if a != b:
            ok = False
            print("%-24s FAIL: 文本比对不一致（%d vs %d）" % (name, len(a), len(b)))
            continue
        results[name] = new
        print("%-24s chatu=%-3d fnote=%-4d h1=%-2d h2=%-3d toc=%-3d" % (
            name, info["chatu"], info["fnote"], info["h1"], info["h2"], info["toc"]))
    if not ok:
        print("RESULT: FAIL（有文件未通过校验，未写回）")
        return 1
    if dry:
        for name, new in results.items():
            write(os.path.join(outdir, name[:-5] + ".xhtml" if name.endswith(".html") else name), new)
        print("RESULT: 预演完成（未改动原文件）")
        return 0
    # 写回 + 备份
    for fp in files:
        shutil.copy2(fp, os.path.join(base, os.path.basename(fp)))
    for name, new in results.items():
        write(os.path.join(d, name), new)
    for line in clean_package(d):
        print("  " + line)
    n = rename_pages(d)
    print("  改名 %d 个 .html -> .xhtml" % n)
    print("RESULT: OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Kindle→calibre（第二套类号）清洗")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("analyze", "process", "verify"):
        sp = sub.add_parser(nm)
        sp.add_argument("dir")
        if nm == "analyze":
            sp.add_argument("-o", "--out")
        if nm == "process":
            sp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if not os.path.isdir(d):
        print("!! 目录不存在: %s" % d)
        return 1
    if a.cmd == "analyze":
        analyze(d, getattr(a, "out", None))
        return 0
    if a.cmd == "process":
        return process(d, dry=a.dry_run)
    return verify_dir(d)


if __name__ == "__main__":
    sys.exit(main())
