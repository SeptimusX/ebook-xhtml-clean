#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_indesign_vrtl.py — InDesign 导出的繁体竖排 EPUB（profile Z）

识别特征（《紅曦照耀中國》一类，八旗/聯經 的 vrtl 导出）:
  `<html … class="vrtl">`；`<link href="../style/book-style-tw.css"/>`（+ style-reset/standard/advance）
  `<body class="p-text|p-image|p-colophon|p-reference">`
  正文 `<p class="indent-2em">`；版式类全是排版尺寸（`m-before-2em`、`start-4em`、`indent--2em`、`align-center|align-end`）
  标题 `<p><span class="k-double-after">第一部</span></p>` +
       `<p class="m-after-2em"><span class="big-h1">萌芽<span class="font-080per">（一九二一—一九二六）</span></span></p>`
  小节 `<p …><span class="small-h3">檔案</span></p>`
  注文（章末）`<p><span class="k-double-after">注釋</span></p>` + 分隔 `div.p-before-3em > div.k-solid-before`
       `<aside epub:type="footnote" id="note-001"><p class="start-3em indent--2em">`
       `<span class="hiv"><a href="#link-001">01</a></span><span class="p-start-1em"></span>注文（含 span.italic）`
  引用 `<span class="ref"><span class="hiv"><a epub:type="noteref" href="#note-001" id="link-001">01</a></span></span>`
  图版 `<svg class="fit" viewBox><image xlink:href="../image/xx.jpg"/></svg>` + `<p class="m-before-0 line-height-1em"><span class="font-080per">图注</span></p>`
  整页图 `<body class="p-image"><svg width="100%" height="100%"><image …/></svg></body>`

映射（用户 2026-11-11 口径）:
  · **转横排**：去 html 的 vrtl / body 的 p-*；`span.hiv` 去壳留数字
  · 章标题：部号 + 章名 → `<h1>第一部　萌芽<br/><span class="subtitle">一九二一—一九二六</span></h1>`
  · 注釋：删「注釋」小标题与分隔线，章末 `<hr/>` + `p.fnote`（编号沿用源「01」，双向回链）
  · 图版 → `div.chatu` + `p.caption`（图版目录同）；整页图 → chatu
  · `p.indent-2em` → bodytext；`p.start-2em.indent--2em`（参考文献）→ bodytext-noindent；
    `p.align-center` → center；`p.align-end` → right；`p.m-before-1em.m-after-1em.align-center`（***）→ center；
    `p.m-before-1em.m-after-1em.start-2em.indent-2em`（诗/引文）→ blockquote
  · `span.italic` → `<i>`；`span.bold` → `<b>`；`span.kai` → `span.kai`；`span.em-dash` → 文本；
    其余 size/spacing/height 类去壳
  · 目次页：目次 → h1；章行 → `p.toc2`；前言/致謝/參考文獻 → `p.toc1`
  · 献词 → `p.center`；题词 → `blockquote.intro` + `p.right`；作者/譯者簡介 → h2 + `p.center<b>`

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

DROP_CSS_RE = r"(?:book-style|style-reset|style-standard|style-advance|stylesheet|page_styles)\.css"

RE_REF = re.compile(r'<span class="ref"><span class="hiv">\s*<a epub:type="noteref" '
                    r'href="#([^"]+)" id="([^"]+)">([^<]*)</a>\s*</span></span>')
RE_NOTE = re.compile(r'<aside epub:type="footnote" id="([^"]+)"><p[^>]*>\s*'
                     r'<span class="hiv">\s*<a href="#([^"]+)">([^<]*)</a>\s*</span>'
                     r'<span class="p-start-1em"></span>(.*?)</p>\s*</aside>', re.S)
RE_SVG = re.compile(r'<svg[^>]*>.*?<image[^>]*xlink:href="([^"]+)"[^>]*>.*?</svg>', re.S)
RE_NOTES_HEAD = re.compile(r'\s*(?:<div class="p-before-3em">\s*<div class="k-solid-before[^"]*"></div>\s*</div>\s*)?'
                           r'<p[^>]*><span class="k-double-after">注釋</span></p>\s*')


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def list_files(d):
    return sorted(f for f in glob.glob(os.path.join(d, "*.xhtml")) + glob.glob(os.path.join(d, "*.html"))
                  if not f.endswith(".bak"))


def norm_inline(c):
    """行内 span 语义化：italic/bold/kai/subtitle 保留语义，其余去壳"""
    c = re.sub(r'<span class="italic">(.*?)</span>', r"<i>\1</i>", c, flags=re.S)
    c = re.sub(r'<span class="bold">(.*?)</span>', r"<b>\1</b>", c, flags=re.S)
    while True:
        c2 = re.sub(r'<span(?!\s+class="(?:kai|subtitle)")\s*(?:class="[^"]*")?\s*>((?:(?!<span).)*?)</span>',
                    r"\1", c, flags=re.S)
        if c2 == c:
            break
        c = c2
    return c


def clean_para(c, role="plain"):
    """段落类 → 语义类（带负向断言，避免二次改写）"""
    KEEP = r'(?!(?:bodytext|bodytext-noindent|fnote|center|right|left2|toc1|toc2|chatu|image|caption|subtitle)\b)'
    # 诗/引文
    c = re.sub(r'<p class="[^"]*\bstart-2em\b[^"]*\bindent-2em\b[^"]*">(.*?)</p>',
               r'<blockquote><p class="bodytext">\1</p></blockquote>', c, flags=re.S)
    # *** 分节
    c = re.sub(r'<p class="[^"]*\balign-center\b[^"]*">(\s*\*\*\*\s*)</p>', r'<p class="sprt">\1</p>', c)
    # 居中 / 右对齐
    c = re.sub(r'<p class="[^"]*\balign-end\b[^"]*">(.*?)</p>', r'<p class="right">\1</p>', c, flags=re.S)
    c = re.sub(r'<p class="[^"]*\balign-center\b[^"]*">(.*?)</p>', r'<p class="center">\1</p>', c, flags=re.S)
    # 参考文献条目（悬挂缩进）
    c = re.sub(r'<p class="[^"]*\bstart-2em\b[^"]*\bindent--2em\b[^"]*">(.*?)</p>',
               r'<p class="bodytext-noindent">\1</p>', c, flags=re.S)
    # 档案子项（缩进）
    c = re.sub(r'<p class="[^"]*\bstart-4em\b[^"]*\bindent--1em\b[^"]*">(.*?)</p>',
               r'<p class="left2">\1</p>', c, flags=re.S)
    # 正文（首行缩进）
    c = re.sub(r'<p class="[^"]*\bindent-2em\b[^"]*">(.*?)</p>', r'<p class="bodytext">\1</p>', c, flags=re.S)
    # 目次行
    if role == "toc":
        c = re.sub(r'<p class="[^"]*start-4em[^"]*">(.*?)</p>', r'<p class="toc2">\1</p>', c, flags=re.S)
        c = re.sub(r'<p>(<a [^>]*>.*?</a>)</p>', r'<p class="toc1">\1</p>', c, flags=re.S)
    # 其余带 class 的 p → 顶格
    c = re.sub(r'<p class="%s[^"]*">(.*?)</p>' % KEEP, r'<p class="bodytext-noindent">\1</p>', c, flags=re.S)
    # 无 class 的 p
    c = re.sub(r'<p>(.*?)</p>', r'<p class="bodytext">\1</p>', c, flags=re.S)
    return c


def clean(c, name, role):
    c = re.sub(r"<!DOCTYPE[^>]*>\s*", "", c)
    c = re.sub(r'\s+lang="[^"]*"', "", c)
    c = re.sub(r'<html([^>]*)\bclass="[^"]*"([^>]*)>', r"<html\1\2>", c)
    c = re.sub(r'<img([^>]*?)\s+class="[^"]*"([^>]*)/>', r"<img\1\2/>", c)
    c = re.sub(r'<link[^>]*rel="stylesheet"[^>]*/>\s*', "", c)
    c = re.sub(r"</head>", '<link href="styles.css" rel="stylesheet" type="text/css"/>\n</head>', c, count=1)
    c = re.sub(r'<body[^>]*>', "<body>", c, count=1)

    # 注文
    notes = []

    def take_note(m):
        nid, back, num, txt = m.group(1), m.group(2), m.group(3), m.group(4)
        txt = re.sub(r'<span class="p-start-1em"></span>', "", txt)
        notes.append((nid, back, num, txt.strip()))
        return ""
    c = RE_NOTE.sub(take_note, c)
    c = RE_NOTES_HEAD.sub("", c)
    c = RE_REF.sub(lambda m: '<sup><a epub:type="noteref" href="#%s" id="%s">[%s]</a></sup>'
                   % (m.group(1), m.group(2), m.group(3).strip()), c)

    # 图版：svg → chatu（带图注则 caption）
    def fig(m):
        src = m.group(1)
        return '<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>\n</div>' % src
    c = RE_SVG.sub(fig, c)
    # svg 后的图注（p.m-before-0.line-height-1em）
    c = re.sub(r'(<div class="chatu">\s*<p class="image">.*?</p>\s*)\n?</div>\s*'
               r'<p class="[^"]*\bline-height-1em\b[^"]*">(.*?)</p>',
               lambda m: m.group(1) + '\n<p class="caption">%s</p>\n</div>' % re.sub(r"<[^>]+>", "", m.group(2)).strip(),
               c, flags=re.S)
    # 题图（div.align-center > img.fit）
    c = re.sub(r'<div class="align-center">\s*<img([^>]*?)class="fit"\s*/>\s*</div>',
               lambda m: '<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>\n</div>'
                         % re.search(r'src="([^"]+)"', m.group(0)).group(1), c, flags=re.S)
    # 任何「div 内只有一张图」→ chatu
    c = re.sub(r'<div[^>]*>\s*<img([^>]*?)/>\s*</div>',
               lambda m: '<div class="chatu">\n<p class="image"><img%s/></p>\n</div>' % m.group(1),
               c, flags=re.S)

    if role == "chapter":
        # 章号 + 章名：<p><span class="k-double-after">第一章</span></p> + big-h1
        c = re.sub(r'<p>\s*<span class="k-double-after">(第[一二三四五六七八九十]+[章部])</span>\s*</p>\s*'
                   r'<p class="m-after-2em"><span class="big-h1">(.*?)<span class="font-080per">（(.*?)）</span></span></p>',
                   lambda m: '<h1>%s　%s<br/><span class="subtitle">（%s）</span></h1>'
                             % (m.group(1), m.group(2).strip(), m.group(3).strip()), c, flags=re.S)
    # 其余大标题
    c = re.sub(r'<p class="m-after-2em"><span class="big-h1">(.*?)</span></p>',
               lambda m: '<h1>%s</h1>' % re.sub(r"<[^>]+>", "", m.group(1)).strip(), c, flags=re.S)
    c = re.sub(r'<p class="big-h1">(.*?)</p>',
               lambda m: '<h1>%s</h1>' % re.sub(r"<[^>]+>", "", m.group(1)).strip(), c, flags=re.S)
    # 小标题
    c = re.sub(r'<p[^>]*><span class="small-h3">(.*?)</span></p>',
               r"<h3>\1</h3>", c, flags=re.S)

    # 目次页
    if role == "toc":
        c = re.sub(r'<p class="bodytext">(\s*<a [^>]*>第[^<]*</a>[^<]*)</p>',
                   r'<p class="toc2">\1</p>', c)

    # 献词 / 题词（题词在 clean_para 之后组装）
    if role == "dedication":
        pass
    if role == "epigraph":
        pass

    # 外框 div 一律交给 unwrap_divs() 处理（保留 div.chatu）
    return c, notes


def unwrap_divs(c):
    """把剩余的纯包裹 div 去掉（保留 chatu）"""
    while True:
        m = re.search(r'<div(?! class="chatu")(?:[^>]*)>', c)
        if not m:
            break
        # 找到配对的 </div>
        depth, j = 1, m.end()
        token = re.compile(r"<div\b[^>]*>|</div>")
        close = None
        while depth:
            m2 = token.search(c, j)
            if not m2:
                return c
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end()
            close = m2
        c = c[:m.start()] + c[m.end():close.start()] + c[close.end():]
    return c


def process_file(fp):
    name = os.path.basename(fp)
    raw = read(fp)
    body_cls = (re.search(r'<body class="([^"]*)"', raw) or [None, ""])[1]
    if "p-image" in body_cls:
        role = "image"
    elif "p-colophon" in body_cls:
        role = "colophon"
    elif "p-reference" in body_cls:
        role = "promo"
    elif "dedication" in raw and "align-end" in raw:
        role = "epigraph"
    elif "dedication" in raw:
        role = "dedication"
    elif '<span class="big-h1">' in raw and "目次" in raw:
        role = "toc"
    elif '<span class="k-double-after">第' in raw:
        role = "chapter"
    elif '<span class="big-h1">' in raw:
        role = "front"
    else:
        role = "plain"

    c = raw
    c, notes = clean(c, name, role)
    c = clean_para(c, role)
    c = norm_inline(c)
    c = re.sub(r'\s+class="(?:m-|start-|indent-|line-height-|font-)[^"]*"', "", c)
    c = unwrap_divs(c)
    # 标题内的 b/i 去壳（h 标签不带 b）
    c = re.sub(r'<h([1-6])([^>]*)>(.*?)</h\1>',
               lambda m: '<h%s%s>%s</h%s>' % (m.group(1), m.group(2), re.sub(r"</?b>", "", m.group(3)), m.group(1)),
               c, flags=re.S)

    # 题词：正文 + 落款 → blockquote.intro
    if role == "epigraph":
        c = re.sub(r'<p class="center">(.*?)</p>\s*<p class="right">(.*?)</p>',
                   lambda m: '<blockquote class="intro">\n<p class="bodytext">%s</p>\n<p class="right">%s</p>\n</blockquote>'
                             % (m.group(1), m.group(2)), c, flags=re.S)
    # 目次：只有链接的行（前言/致謝/參考文獻）
    if role == "toc":
        c = re.sub(r'<p class="bodytext(?:-noindent)?">(<a [^>]*>.*?</a>)</p>',
                   r'<p class="toc1">\1</p>', c, flags=re.S)

    # 作者/译者简介页
    if role == "plain" and "作者" in raw:
        # 「作者 / 譯者」标签 → h2；姓名行 → 居中加粗
        c = re.sub(r'<p class="bodytext-noindent">(<b>)(作者|譯者)(</b>)</p>', r"<h2>\2</h2>", c)
        c = re.sub(r'<p class="bodytext(?:-noindent)?">(<b>.*?</b>.*?)</p>', r'<p class="center">\1</p>', c, flags=re.S)
    if role == "colophon":
        c = re.sub(r'<p class="bodytext(?:-noindent)?">(<b>.*?</b>)</p>', r'<p class="center">\1</p>', c, flags=re.S)
        c = c.replace('<p class="bodytext">', '<p class="bodytext-noindent">')
    if role == "promo":
        c = re.sub(r'<p class="bodytext(?:-noindent)?">(<b>.*?</b>)</p>', r'<p class="center">\1</p>', c, flags=re.S)

    # 末尾注文
    if notes:
        def note_html(txt):
            txt = re.sub(r'<span class="italic">(.*?)</span>', r"<i>\1</i>", txt, flags=re.S)
            txt = re.sub(r'<span class="kai">(.*?)</span>', r'<span class="kai">\1</span>', txt, flags=re.S)
            txt = re.sub(r'<span(?: class="[^"]*")?\s*>((?:(?!<span).)*?)</span>', r"\1", txt, flags=re.S)
            return txt
        block = "<hr/>\n" + "\n".join(
            '<p class="fnote" id="%s"><a href="#%s">[%s]</a> %s</p>' % (nid, back, num.strip(), note_html(txt))
            for nid, back, num, txt in notes) + "\n"
        c = c.replace("</body>", block + "</body>")

    # head/body 收尾
    title = (re.search(r"<title>(.*?)</title>", c, re.S) or [None, ""])[1].strip()
    body = c[c.find("<body"):]
    body = re.sub(r"^<body[^>]*>\s*", "", body)
    body = re.sub(r"\s*</body>.*$", "", body, flags=re.S)
    body = re.sub(r"(?m)^[ \t]+$", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    out = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
           'xml:lang="zh-TW">\n<head>\n<title>%s</title>\n'
           '<link href="styles.css" rel="stylesheet" type="text/css"/>\n</head>\n<body>\n%s\n</body>\n</html>\n'
           % (title, body))
    return postprocess(out), role, len(notes)


def text_of(c, side):
    c = re.sub(r"<head>.*?</head>", "", c, flags=re.S)
    if side == "src":
        c = re.sub(r"<aside.*?</aside>", "", c, flags=re.S)
        c = re.sub(r'<p[^>]*><span class="k-double-after">注釋</span></p>', "", c)
        c = re.sub(r"<link[^>]*/>", "", c)
    else:
        c = re.sub(r'<p class="fnote".*?</p>', "", c, flags=re.S)
        c = re.sub(r"<hr/>", "", c)
        c = re.sub(r"<link[^>]*/>", "", c)
    c = re.sub(r"<(svg|image)\b.*?</\1>", "", c, flags=re.S)
    c = re.sub(r"<img\b[^>]*/>", "", c)
    c = re.sub(r"<[^>]+>", "", c)
    c = c.replace("[", "").replace("]", "")
    c = c.replace("\u25cb", "\u3007")
    return re.sub(r"\s+", "", c)


# ---------- analyze ----------

def analyze(d, out=None):
    files = list_files(d)
    L = ["# analyze(indesign-vrtl): %s" % d, ""]
    for f in files:
        c = read(f)
        n_aside = len(re.findall(r'<aside epub:type="footnote"', c))
        n_ref = len(re.findall(r'epub:type="noteref"', c))
        n_svg = len(re.findall(r"<svg[^>]*>", c))
        n_h1 = len(re.findall(r'class="big-h1"', c))
        cls = sorted(set(re.findall(r'<p class="([^"]*)"', c)))
        L.append("%-20s aside=%-3d ref=%-3d svg=%-3d big-h1=%-2d  p: %s"
                 % (os.path.basename(f), n_aside, n_ref, n_svg, n_h1, ", ".join(cls)[:70]))
    rep = "\n".join(L) + "\n"
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        open(out, "w", encoding="utf-8").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)


# ---------- process ----------

def process(d, dry=False):
    _st = ensure_styles(d)
    if _st not in ("same", "copied"):
        print("styles.css: %s" % _st)
    files = list_files(d)
    if not files:
        print("!! 未找到 xhtml")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "vrtl-%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录:", outdir)
    ok = True
    results = {}
    for fp in files:
        name = os.path.basename(fp)
        raw = read(fp)
        try:
            new, role, n_notes = process_file(fp)
        except Exception as e:
            ok = False
            print("%-20s FAIL: %s" % (name, e))
            continue
        a, b = text_of(raw, "src"), text_of(new, "out")
        if a != b:
            ok = False
            i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            print("%-20s FAIL: 文本不一致 %d/%d @%d 源[%s] 新[%s]"
                  % (name, len(a), len(b), i, a[max(0, i - 12):i + 12], b[max(0, i - 12):i + 12]))
            continue
        results[name] = new
        print("%-20s %-8s note=%-3d %6d B" % (name, role, n_notes, len(new.encode())))
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
    print("styles.css: %s" % ensure_styles(d))
    print("RESULT: OK")
    return 0


# ---------- verify ----------

def verify_dir(d):
    ok = True
    files = list_files(d)
    ALLOWED = {"bodytext", "bodytext-noindent", "fnote", "center", "right", "left2", "toc1", "toc2",
               "chatu", "image", "caption", "subtitle", "kai", "sprt", "intro"}
    ids = {}
    for f in files:
        c = read(f)
        ids[os.path.basename(f)] = set(re.findall(r'\bid="([^"]+)"', c))
    total_n = total_r = 0
    for f in files:
        name = os.path.basename(f)
        c = read(f)
        probs = []
        try:
            ET.fromstring(c.encode("utf-8"))
        except ET.ParseError as e:
            probs.append("XML %s" % e)
        bad = sorted({x for m in re.findall(r'class="([^"]*)"', c) for x in m.split() if x not in ALLOWED})
        if bad:
            probs.append("残留类名 %s" % ",".join(bad[:4]))
        if "vrtl" in c:
            probs.append("残留 vrtl")
        if re.search(r'<span(?! class="(?:kai|subtitle)")', c):
            probs.append("残留 span")
        n = len(re.findall(r'<p class="fnote" id="([^"]+)"><a href="#([^"]+)">', c))
        total_n += n
        for fid, back in re.findall(r'<p class="fnote" id="([^"]+)"><a href="#([^"]+)">', c):
            if back not in ids[name]:
                probs.append("注 %s 回链缺失" % fid)
                break
        for m in re.finditer(r'epub:type="noteref" href="#([^"]+)" id="([^"]+)"', c):
            total_r += 1
            if m.group(1) not in ids[name]:
                probs.append("引用 #%s 无注文" % m.group(1))
                break
        for m in re.finditer(r'(?:href|src)="([^"]+)"', c):
            h = m.group(1)
            if h.startswith(("http", "mailto:")) or h == "styles.css":
                continue
            fn, _, frag = h.partition("#")
            if not fn:
                fn = name
            if not os.path.exists(os.path.join(d, fn)):
                probs.append("链接缺失 %s" % h)
            elif frag and fn.endswith(".xhtml") and frag not in ids.get(fn, set()):
                probs.append("锚点缺失 %s" % h)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(sorted(set(probs)))))
        else:
            print("%-20s OK  %d B" % (name, len(c.encode())))
    print("ref=%d note=%d %s" % (total_r, total_n, "匹配" if total_r == total_n else "不匹配"))
    print("RESULT:", "PASS" if ok and total_r == total_n else "FAIL")
    return 0 if ok and total_r == total_n else 1


def main():
    ap = argparse.ArgumentParser()
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
    if a.cmd == "analyze":
        analyze(d, getattr(a, "out", None))
        return 0
    if a.cmd == "process":
        return process(d, dry=a.dry_run)
    return verify_dir(d)


if __name__ == "__main__":
    sys.exit(main())
