#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_gbs.py — Google Books 增强版（GBS）EPUB3 profile

识别特征（GoogleEbooks / GBS 加工过的 EPUB3）:
  opf 里 <meta content="GoogleEbooks" name="GBSEpubSource"/>
  正文夹大量扫描页码锚点 <a id="GBS.0059.02"/> 与 <div style="display:none;"><a id="GBS…"/></div>
  封面 / 书名页 / 部扉页是固定版式页：
      <ops:switch><ops:case><svg><image xlink:href="image/part01.jpg"/></svg></ops:case>
      <ops:default><img src="inserted_file_…_svg_raster.jpeg"/></ops:default></ops:switch>
  正文 <p> / 引文 <p class="sans0|sans|skai"> / 插图 <div class="picbox"><p class="pic"><img class="w100"/>…
  尾注 <p class="footnote" id="foot-N"><a href="文件#back-N"><span class="no">N</span></a>注文</p>
      正文 <a class="ref" href="文件#foot-N" id="back-N">N</a>
  章首 <p class="leading">第一</p> + <h2>章名</h2>
  书内目录 <p class="chapter">篇 / <p class="part">章 / <p>节

映射（→ 最新约定）:
  GBS 锚点 / display:none 容器        -> 删除（无任何链接引用）
  <p>                                 -> <p class="bodytext">
  sans0 / sans / skai（连续者合并）   -> <blockquote><p>…</p>…</blockquote>
  leading + h2                        -> <h2><span class="subtitle">第一</span><br/>章名</h2>
  div.picbox                          -> <div class="chatu"><p class="image"><img/></p><p class="caption">…</p></div>
  p.footnote                          -> <p class="fnote" id="foot-N"><a href="#back-N">[N]</a> …</p>
  a.ref                               -> <sup><a epub:type="noteref" href="#foot-N" id="back-N">[N]</a></sup>
  span.italic                         -> <i>
  span.dash / span.space2             -> 去壳留字
  固定版式页                          -> 流式图片页（image/*.jpg），删 inserted_file_*_svg_raster.jpeg
  三份 css                            -> 单一 styles.css（skill assets 版）
  opf                                 -> 去 page-map、去 pre-paginated / svg switch、去 GBS meta

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

# 固定版式页 -> (图片, 版式)
FIXED_PAGES = {
    "cover.xhtml": ("image/cover.jpg", "cover"),
    "title.xhtml": ("image/title.jpg", "page"),
    "part01-00.xhtml": ("image/part01.jpg", "page"),
    "part02-00.xhtml": ("image/part02.jpg", "page"),
    "part03-00.xhtml": ("image/part03.jpg", "page"),
}

DROP_FILES_RE = re.compile(r"^(?:css/[^/]+\.css|_page_map_\.xml|inserted_file_.*_svg_raster\.jpe?g)$")

ALLOWED_CLASSES = {
    "bodytext", "bodytext-noindent", "fnote", "fnotel", "image", "caption",
    "chatu", "toutu", "center", "right", "left", "left2", "toc1", "toc2",
    "intro", "poem", "blockcenter", "menu", "sprt", "pgbrk", "cover",
    "date", "author", "box", "subtitle",
}

# ---------- 基础 ----------


def list_files(d):
    files = []
    for pat in ("*.xhtml", "*.html"):
        files += glob.glob(os.path.join(d, pat))
    return sorted(set(files))


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def text_of(c):
    """元素文字（去标签、去空白），用于完整性核对"""
    c = re.sub(r"<head>.*?</head>", "", c, flags=re.S)
    c = re.sub(r"<a[^>]*>\[(\d+)\]</a>", r"\1", c)      # 注号 [N] 视为原数字
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", "", c).replace("\u25cb", "\u3007")   # ○→〇 属规范化，不算文本改动


def head_title(c):
    m = re.search(r"<title>(.*?)</title>", c, re.S)
    return (m.group(1).strip() if m else "")


def doc(title, body):
    return ('<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops">\n<head>\n'
            "<title>%s</title>\n"
            '<link href="styles.css" rel="stylesheet" type="text/css"/>\n'
            "</head>\n<body>\n%s\n</body>\n</html>\n" % (title, body.strip()))


# ---------- 正文清洗 ----------

_RE_NOTE = re.compile(
    r'<p[^>]*class="footnote"[^>]*id="foot-(\d+)"[^>]*>\s*'
    r'<a[^>]*href="[^"#]*#back-(\d+)"[^>]*>\s*<span class="no">\d+</span>\s*</a>(.*?)</p>', re.S)
_RE_NOTE2 = re.compile(
    r'<p[^>]*id="foot-(\d+)"[^>]*class="footnote"[^>]*>\s*'
    r'<a[^>]*href="[^"#]*#back-(\d+)"[^>]*>(.*?)</a>(.*?)</p>', re.S)
_RE_REF = re.compile(
    r'<a class="ref" href="[^"#]*#foot-(\d+)" id="back-(\d+)">(\d+)</a>')
_RE_PICBOX = re.compile(r'<div class="picbox">(.*?)</div>', re.S)
_RE_QUOTE_RUN = re.compile(
    r'(?:<p class="(?:sans0|sans|skai)">.*?</p>\s*)+', re.S)


def _picbox(m):
    block = m.group(1)
    img = re.search(r'<img[^>]*src="([^"]*)"[^>]*/>', block)
    cap = re.search(r'<p class="caption">(.*?)</p>', block, re.S)
    if not img:
        return ""
    out = ['<div class="chatu">',
           '<p class="image"><img src="%s" alt=""/></p>' % img.group(1)]
    if cap:
        out.append('<p class="caption">%s</p>' % cap.group(1).strip())
    out.append("</div>")
    return "\n".join(out)


def _quote_run(m):
    ps = re.findall(r'<p class="(?:sans0|sans|skai)">(.*?)</p>', m.group(0), re.S)
    if not ps:
        return m.group(0)
    return ("<blockquote>\n"
            + "\n".join('<p class="bodytext">%s</p>' % p.strip() for p in ps)
            + "\n</blockquote>")


def clean_body(inner, name):
    # 1) 隐藏页码容器 / 行内页码锚点
    inner = re.sub(r'<div style="display:none;">.*?</div>', "", inner, flags=re.S)
    inner = re.sub(r'<a id="GBS[^"]*"\s*/>', "", inner)
    inner = re.sub(r'<a id="GBS[^"]*"></a>', "", inner)

    # 2) 占位空段
    inner = re.sub(r'<p class="clear">[^<]*</p>', "", inner)
    inner = re.sub(r"<p>[ \u3000]*</p>", "", inner)

    # 3) 插图
    inner = _RE_PICBOX.sub(_picbox, inner)

    # 4) 尾注
    def note1(m):
        n, b, rest = m.group(1), m.group(2), m.group(3)
        return ('<p class="fnote" id="foot-%s"><a href="#back-%s">[%s]</a>%s</p>'
                % (n, b, n, rest if rest.startswith(" ") else " " + rest.lstrip()))
    inner = _RE_NOTE.sub(note1, inner)

    def note2(m):
        n, b, num, rest = m.group(1), m.group(2), re.sub(r"<[^>]+>", "", m.group(3)), m.group(4)
        return ('<p class="fnote" id="foot-%s"><a href="#back-%s">[%s]</a>%s</p>'
                % (n, b, n, rest if rest.startswith(" ") else " " + rest.lstrip()))
    inner = _RE_NOTE2.sub(note2, inner)

    # 5) 注号引用
    inner = _RE_REF.sub(
        lambda m: '<sup><a epub:type="noteref" href="#foot-%s" id="back-%s">[%s]</a></sup>'
                  % (m.group(1), m.group(2), m.group(3)), inner)

    # 6) 表格：只留 table/tr/td
    inner = re.sub(r"<colgroup>.*?</colgroup>", "", inner, flags=re.S)
    inner = re.sub(r"</?tbody>", "", inner)
    inner = re.sub(r"<td>\s*<p>(.*?)</p>\s*</td>", r"<td>\1</td>", inner, flags=re.S)
    inner = re.sub(r"<td>\s*</td>", "", inner)

    # 7) 章号并进 h2
    inner = re.sub(r'<p class="leading">(.*?)</p>\s*<h2>(.*?)</h2>',
                   lambda m: '<h2><span class="subtitle">%s</span><br/>%s</h2>'
                             % (m.group(1).strip(), m.group(2).strip()), inner, flags=re.S)

    # 8) 连续引文 -> 一个 blockquote（先取出，避免下面的段落映射改到引文内部）
    inner = _RE_QUOTE_RUN.sub(_quote_run, inner)
    bq, tokens = [], []

    def stash(m):
        tokens.append(m.group(0))
        return "@@BQ%d@@" % (len(tokens) - 1)
    inner = re.sub(r"<blockquote>.*?</blockquote>", stash, inner, flags=re.S)

    # 9) 其余段落按文件性质映射
    def pmap(m):
        attrs, txt = m.group(1), m.group(2)
        cm = re.search(r'class="([^"]*)"', attrs)
        cls = (cm.group(1).strip() if cm else "")
        if cls in ("footnote", "pic", "caption", "image", "fnote"):
            return m.group(0)
        if name == "colophon.xhtml":
            return '<p class="bodytext-noindent">%s</p>' % txt
        if cls in ("p02", ""):
            return '<p class="bodytext">%s</p>' % txt
        if cls in ("s0", "s1"):
            return '<p class="bodytext-noindent">%s</p>' % txt
        if cls in ("end",):
            return '<p class="right">%s</p>' % txt
        if cls in ("serif", "booktitle"):
            return '<p class="center">%s</p>' % txt
        if cls == "p1":
            return '<p class="bodytext">%s</p>' % txt
        return '<p class="bodytext">%s</p>' % txt
    inner = re.sub(r"<p([^>]*)>(.*?)</p>", pmap, inner, flags=re.S)
    inner = re.sub(r"@@BQ(\d+)@@", lambda m: tokens[int(m.group(1))], inner)

    # 10) 行内 span 去语义化
    inner = re.sub(r'<span class="italic">(.*?)</span>', r"<i>\1</i>", inner, flags=re.S)
    inner = re.sub(r'<span class="_2-斜體">(.*?)</span>', r"<i>\1</i>", inner, flags=re.S)
    inner = re.sub(r'<span class="(?:dash|space2|no|sans|serif)">(.*?)</span>', r"\1", inner, flags=re.S)
    keep_span = r"(?:italic|bold|underline|small|smallcaps|lefttitle|jiazhu|del|kai|kaiti|name|super|sub|subtitle)"
    inner = re.sub(r'<span class="(?!%s[ "])[^"]*">(.*?)</span>' % keep_span, r"\1", inner, flags=re.S)
    inner = re.sub(r"<a>([^<]*)</a>", r"\1", inner)          # 无 href 的空链接

    # 11) 杂项
    inner = re.sub(r'<h5>(.*?)</h5>', r'<p class="center"><b>\1</b></p>', inner, flags=re.S)
    inner = re.sub(r'\s*style="[^"]*"', "", inner)
    inner = re.sub(r"\n{3,}", "\n\n", inner)
    return inner


def clean_contents(inner):
    inner = re.sub(r'<div style="display:none;">.*?</div>', "", inner, flags=re.S)
    inner = re.sub(r'<a id="GBS[^"]*"\s*/>', "", inner)
    inner = re.sub(r'<p class="clear">[^<]*</p>', "", inner)
    inner = re.sub(r"<p>[ \u3000]*</p>", "", inner)
    inner = re.sub(r'<h3 class="p0">(.*?)</h3>', r"<h1>\1</h1>", inner, flags=re.S)
    inner = re.sub(r'<p class="chapter">(.*?)</p>', r'<p class="toc1">\1</p>', inner, flags=re.S)
    inner = re.sub(r'<p class="part">(.*?)</p>', r'<p class="toc1">\1</p>', inner, flags=re.S)
    inner = re.sub(r'<p class="s0">(.*?)</p>', r'<p class="toc1">\1</p>', inner, flags=re.S)
    inner = re.sub(r"<p>(<a .*?</a>)</p>", r'<p class="toc2">\1</p>', inner, flags=re.S)
    inner = re.sub(r"\n{3,}", "\n\n", inner)
    return inner


def clean_nav(inner):
    inner = re.sub(r'<div style="display:none;">.*?</div>', "", inner, flags=re.S)
    inner = re.sub(r'<a id="GBS[^"]*"\s*/>', "", inner)
    return inner


def process_file(name, c):
    """返回 (新内容, 统计)"""
    title = head_title(c)
    ctx = {"chatu": 0, "refs": 0, "fnotes": 0, "quote": 0, "subt": 0}

    if name in FIXED_PAGES:
        img, kind = FIXED_PAGES[name]
        if kind == "cover":
            body = '<div><img src="%s" alt="封面"/></div>' % img
            h = (('<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n<title>%s</title>\n'
                  '<link href="styles.css" rel="stylesheet" type="text/css"/>\n</head>\n'
                  '<body class="cover">\n%s\n</body>\n</html>\n') % (title, body))
            return h, ctx
        body = '<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>\n</div>' % img
        return doc(title, body), ctx

    m = re.search(r"<body([^>]*)>(.*)</body>", c, re.S)
    if not m:
        raise ValueError("未找到 <body>")
    battrs, inner = m.group(1), m.group(2)
    orig_text = text_of(c)

    if name == "contents.xhtml":
        inner = clean_contents(inner)
    elif name == "toc.xhtml":
        inner = clean_nav(inner)
    else:
        inner = clean_body(inner, name)

    body = inner.strip()
    h = doc(title, body)
    # 保留 body 上的 lang / xml:lang
    if 'lang="' in battrs:
        h = h.replace("<body>", "<body %s>" % battrs.strip(), 1)

    ctx["chatu"] = len(re.findall(r'<div class="chatu">', h))
    ctx["refs"] = len(re.findall(r'epub:type="noteref"', h))
    ctx["fnotes"] = len(re.findall(r'<p class="fnote"', h))
    ctx["quote"] = len(re.findall(r"<blockquote>", h))
    ctx["subt"] = len(re.findall(r'<span class="subtitle">', h))

    if name not in ("toc.xhtml",) and text_of(h) != orig_text:
        raise ValueError("文本比对不一致（清洗前后逐字不同）")
    return h, ctx


# ---------- 包级 ----------


def clean_package(d):
    ops = []
    for fn in ("volume.opf", "content.opf", "package.opf"):
        p = os.path.join(d, fn)
        if os.path.exists(p):
            break
    else:
        return ["未找到 opf"]

    c = read(p)
    dropped = set()

    def item(m):
        s = m.group(0)
        href = re.search(r'href="([^"]*)"', s)
        iid = re.search(r'\bid="([^"]*)"', s)
        if href and DROP_FILES_RE.match(href.group(1)):
            if iid:
                dropped.add(iid.group(1))
            return ""
        if href and os.path.basename(href.group(1)) in FIXED_PAGES:
            s = s.replace(' properties="svg switch"', "")
        return s
    c = re.sub(r"<item\b[^>]*/>", item, c)

    def itemref(m):
        s = m.group(0)
        iid = re.search(r'idref="([^"]*)"', s)
        if iid and iid.group(1) in dropped:
            return ""
        return re.sub(r' properties="[^"]*"', "", s)
    c = re.sub(r"<itemref\b[^>]*/>", itemref, c)

    c = c.replace(' page-map="_page_map_"', "")
    c = re.sub(r'\s*<meta[^>]*name="GBS[^"]*"[^>]*/>', "", c)
    if 'id="styles.css"' not in c:
        c = c.replace("</manifest>",
                      '    <item href="styles.css" id="styles.css" media-type="text/css"/>\n  </manifest>')
    else:
        c = re.sub(r'<item[^>]*id="styles.css"[^>]*/>',
                   '<item href="styles.css" id="styles.css" media-type="text/css"/>', c)
    c = re.sub(r"\n{3,}", "\n\n", c)
    write(p, c)
    ops.append("%s: item=%d itemref=%d" % (os.path.basename(p),
                                           len(re.findall(r"<item\b", c)),
                                           len(re.findall(r"<itemref\b", c))))

    # 删多余文件
    for pat in ("css", "_page_map_.xml"):
        t = os.path.join(d, pat)
        if os.path.isdir(t):
            shutil.rmtree(t)
            ops.append("删除目录 %s/" % pat)
        elif os.path.exists(t):
            os.remove(t)
            ops.append("删除 %s" % pat)
    for f in glob.glob(os.path.join(d, "inserted_file_*_svg_raster.*")):
        os.remove(f)
    ops.append("删除 inserted_file_* 备用图 %d 个" %
               len(glob.glob(os.path.join(d, "inserted_file_*"))))
    ops.append("styles.css: %s" % ensure_styles(d))
    return ops


# ---------- 校验 ----------


def verify_content(c, name):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except ET.ParseError as e:
        probs.append("XML %s" % e)
        return probs, {}
    if "GBS" in c:
        probs.append("残留 GBS 锚点")
    if "\u25cb" in c:
        probs.append("残留 ○(U+25CB)，应为 〇")
    for bad in ('class="footnote"', 'class="picbox"', 'class="sans', 'class="skai"',
                "display:none", "css/fixed", "css/styles.css", "<ops:switch", "<svg"):
        if bad in c:
            probs.append("残留 %s" % bad)
    refs = re.findall(r'epub:type="noteref" href="#foot-(\d+)" id="back-(\d+)"', c)
    notes = re.findall(r'<p class="fnote" id="foot-(\d+)"><a href="#back-(\d+)"', c)
    if len(refs) != len(notes):
        probs.append("noteref(%d) != fnote(%d)" % (len(refs), len(notes)))
    back = {b for _, b in refs}
    for n, b in notes:
        if b not in back:
            probs.append("注文 foot-%s 回链 back-%s 悬空" % (n, b))
            break
    for n, b in refs:
        if n not in {x for x, _ in notes}:
            probs.append("引用 #foot-%s 无对应注文" % n)
            break
    for m in re.finditer(r'<div class="chatu">(.*?)</div>', c, re.S):
        if "<img" not in m.group(1):
            probs.append("chatu 缺图")
            break
    for m in re.finditer(r'<(h1|h2|h3)[^>]*>(.*?)</\1>', c, re.S):   # 标题「」成对
        t = re.sub(r'<[^>]+>', '', m.group(2))
        if t.count('「') != t.count('」'):
            probs.append("标题引号不成对: %s" % t[:24])
            break
    for cls in set(re.findall(r'class="([^"]+)"', c)):
        for one in cls.split():
            if one not in ALLOWED_CLASSES:
                probs.append("未知 class: %s" % one)
                break
    info = {"chatu": len(re.findall(r'<div class="chatu">', c)),
            "fnote": len(notes), "quote": len(re.findall(r"<blockquote>", c)),
            "h2": len(re.findall(r"<h2", c)), "h3": len(re.findall(r"<h3", c))}
    return probs, info


def verify_dir(d):
    ok = True
    files = list_files(d)
    ids = {}
    for fp in files:
        c = read(fp)
        ids[os.path.basename(fp)] = set(re.findall(r'\bid="([^"]+)"', c))
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
            print("%-20s FAIL: %s" % (name, "; ".join(sorted(set(probs)))))
        else:
            print("%-20s OK  %s" % (name, " ".join("%s=%d" % kv for kv in sorted(info.items()))))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---------- analyze ----------


def analyze(d, out=None):
    files = list_files(d)
    L = ["目录: %s" % d, "xhtml: %d" % len(files)]
    tot = {}
    for key, pat in (("GBS 锚点", r'<a id="GBS'), ("display:none", r"display:none"),
                     ("footnote", r'class="footnote"'), ("ref", r'class="ref"'),
                     ("picbox", r'class="picbox"'), ("chatu", r'class="chatu"'),
                     ("table", r"<table"), ("tr", r"<tr"), ("h2", r"<h2"), ("h3", r"<h3"),
                     ("h4", r"<h4"), ("leading", r'class="leading"'),
                     ("sans0/sans/skai", r'class="(?:sans0|sans|skai)"'),
                     ("p02/s0/s1", r'class="(?:p02|s0|s1)"'),
                     ("ops:switch", r"<ops:switch"), ("svg", r"<svg")):
        tot[key] = sum(len(re.findall(pat, read(f))) for f in files)
    for k, v in tot.items():
        L.append("  %-18s %d" % (k, v))
    if os.path.exists(os.path.join(d, "_page_map_.xml")):
        L.append("  _page_map_.xml   有（Google Books 固定版式）")
    L.append("固定版式页: %s" % ", ".join(sorted(FIXED_PAGES)))
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
        print("!! 未找到 *.xhtml / *.html")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录: %s" % outdir)
    ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        try:
            new, ctx = process_file(name, c)
            new = postprocess(new)
        except Exception as e:
            ok = False
            print("%-20s FAIL: %s" % (name, e))
            continue
        probs, _ = verify_content(new, name)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, new)
        print("%-20s chatu=%-3d fnote=%-4d ref=%-4d quote=%-2d 副题=%-2d" % (
            name, ctx["chatu"], ctx["fnotes"], ctx["refs"], ctx["quote"], ctx["subt"]))
    if not ok:
        print("RESULT: FAIL（有文件未通过校验，未写回）")
        return 1
    if dry:
        print("RESULT: 预演完成（未改动原文件）")
        return 0
    for line in clean_package(d):
        print("  " + line)
    print("RESULT: OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Google Books 增强版 EPUB3 清洗")
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
