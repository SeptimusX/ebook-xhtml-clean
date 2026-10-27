#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_kindle_cn2.py — Kindle-cn（亚马逊中国，三联/学术注释版）+ calibre 混合源清洗

与 profile L（epub_clean_kindle_cn.py）同源，但这一类书的 calibre 类号是**另一套**，且多出：
  - 正文是 `<p class="calibre8">`（不是 calibre1）；另有 `p.kindle-cn-para-no-indent` / `-2em-indent`
  - 小节标题是 `<p class="kindle-cn-noindent">一　平民家世</p>`（不是 h2），年表里同一个类装「前256年·秦昭王五十一年」
  - `div.kindle-cn-toc-level1` 在正文文件里是**段落外壳**（不是目录层级）→ 解包
  - 图注 `<p class="kindle-cn-picture-txt-withfewcharactors">` + `-withmanycharactors`
  - 版权页 `<p class="kindle-cn-copyright-text">`；表格 `<table class="kindle-cn-picture-parallel">`（双图并排）
  - 尾注 ref：`<a id="chN-back" href="file#chN"><sup class="calibre3">[N]</sup></a>`（sup 是 calibre3）
  - 尾注前分隔：`<div class="empty"></div>` + `<p class="kindle-cn-noindent">————…（20×—）</p>`
  - 行内字图 `img.kindle-cn-inline-image1`（可用 rare_map.json 换成汉字）

映射（统一到同目录 styles.css）:
  css -> styles.css；<body> 去 class（保留 id）；<html> 补 xmlns:epub
  目录：h1.kindle-cn-toc-title -> h1；div.kindle-cn-toc-level1 -> div.toc2；div.kindle-cn-toc-level -> div.toc1；a.calibre5 -> <a>
  标题：h1.kindle-cn-heading -> h1（保 id＝calibre_pb_N）；h2.calibre6 -> h2（内嵌 <a id=secNNN> 的 id 上提）；
        p.kindle-cn-noindent（纯文本）-> h3；含 span 的（年表年行）-> <p class="bodytext"><b>…</b><span class="kai">…</span>
  正文：p.calibre8 / p.kindle-cn-para-no-indent / p.kindle-cn-para-2em-indent / p.kindle-cn-copyright-text -> bodytext
        p.kindle-cn-kai -> <p class="bodytext"><span class="kai">…</span></p>
        span.kindle-cn-bold -> <b>；span.kindle-cn-kai1 -> <span class="kai">
        div.kindle-cn-toc-level1（正文外壳）解包
  尾注：ref -> <sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>（每文件从 1 重排）
        注文 -> <p class="fnote" id="foot-K"><a href="#back-K">[K]</a> 注文</p>（章末 <hr/> 之后）
  图：div.kindle-cn-bodycontent-div-alone -> <div class="chatu">；内部 `p.kindle-cn-picture-txt-*` -> p.caption（多行 <br/> 合并）
      孤立在图后的 `p.kindle-cn-picture-txt-*`（表格双图）-> p.caption
      行内字图 -> <img src alt/>（rare_map.json 命中则换汉字）
  表格：table/tr/td/caption 去 class 保留
  div.calibre2（空锚）/ div.empty 删除；hr.calibre10 -> <hr/>；href 里 .html -> .xhtml；文件 .html -> .xhtml

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, json, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import postprocess, ensure_styles

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:stylesheet\.css|page_styles\d*\.css|style\d+\.css)",
    "rare_map": "rare_map.json",
}


# ---------- 基础 ----------
def list_files(d):
    out = []
    for pat in ("*.xhtml", "*.html"):
        out += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    return sorted(set(out))


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def cap_txt(s):
    """图注取文本，但保留脚注引用 <sup>…</sup>"""
    sup = "".join(re.findall(r"<sup\b.*?</sup>", s, re.S))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip() + sup


def txt(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def cap_txt(s):
    """图注取文本，但保留脚注引用 <sup>…</sup>"""
    sups = "".join(re.findall(r"<sup\b.*?</sup>", s, re.S))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip() + sups


def load_rare(d):
    p = os.path.join(d, CONFIG["rare_map"])
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------- 步骤 ----------
def step_css(c, name, ctx, rare):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1<link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
        ctx["css"] += 1
    return c


def step_body(c, name, ctx, rare):
    c = re.sub(r'<body([^>]*?)\s+class="[^"]*"([^>]*)>', r"<body\1\2>", c)
    return c


def step_toc(c, name, ctx, rare):
    if "kindle-cn-toc-title" not in c:
        return c
    c = re.sub(r'<h1 class="kindle-cn-toc-title"([^>]*)>', r"<h1\1>", c)
    c = re.sub(r'<div class="kindle-cn-toc-level1">', '<div class="toc2">', c)
    c = re.sub(r'<div class="kindle-cn-toc-level">', '<div class="toc1">', c)
    c = re.sub(r'<a\b([^>]*?)\s+class="calibre5"', r'<a\1', c)
    ctx["toc"] += 1
    return c


def step_footnotes(c, name, ctx, rare):
    notes = []

    def note(m):
        notes.append((m.group(1), m.group(3)))
        return ""

    c = re.sub(r'<p class="fnote"><a id="([^"]+)" href="[^"]*#[^"]*">\[(\d+)\]</a>\s*(.*?)</p>\s*',
               note, c, flags=re.S)
    seq = [0]

    def ref(m):
        seq[0] += 1
        return '<sup><a epub:type="noteref" href="#foot-%d" id="back-%d">[%d]</a></sup>' % (
            seq[0], seq[0], seq[0])

    c = re.sub(r'<a id="([^"]+)-back"[^>]*><sup(?: class="[^"]*")?>\[(\d+)\]</sup></a>',
               ref, c)
    # 尾注前的分隔（div.empty + 20×横线）
    c = re.sub(r'<div class="empty">\s*</div>\s*', "", c)
    c = re.sub(r'<p class="kindle-cn-noindent">\s*[—－-]{8,}\s*</p>\s*', "", c)
    if notes:
        ctx["fnotes"] = notes
    return c


def step_headings(c, name, ctx, rare):
    # 章标题
    c = re.sub(r'<h1 class="kindle-cn-heading"([^>]*)>', r"<h1\1>", c)
    # 节标题 h2.calibre6（内嵌 <a id="secNNN" class="calibre6"></a>）
    def h2(m):
        attrs, inner = m.group(1), m.group(2)
        am = re.search(r'<a id="([^"]+)"[^>]*>\s*</a>', inner)
        inner = re.sub(r'<a id="[^"]+"[^>]*>\s*</a>', "", inner)
        cid = am.group(1) if am else ""
        attrs = re.sub(r'\s+class="[^"]*"', "", attrs)
        attrs = re.sub(r'\s+id="[^"]*"', "", attrs)
        sups = "".join(re.findall(r'<sup\b.*?</sup>', inner, re.S))
        ctx["heads"] += 1
        return '<h2%s>%s%s</h2>' % ((' id="%s"' % cid) if cid else "", txt(inner), sups)
    c = re.sub(r'<h2([^>]*class="[^"]*calibre6[^"]*"[^>]*)>(.*?)</h2>', h2, c, flags=re.S)
    # 小节标题 / 年表年行
    def sec(m):
        inner = m.group(1)
        if "<span" in inner:
            inner = re.sub(r'<span class="kindle-cn-bold">(.*?)</span>', r"<b>\1</b>", inner, flags=re.S)
            inner = re.sub(r'<span class="kindle-cn-kai1">(.*?)</span>', r'<span class="kai">\1</span>',
                           inner, flags=re.S)
            ctx["year"] += 1
            return '<p class="bodytext">%s</p>' % inner.strip()
        ctx["heads"] += 1
        return "<h3>%s</h3>" % txt(inner)
    c = re.sub(r'<p class="kindle-cn-noindent">(.*?)</p>', sec, c, flags=re.S)
    return c


def _unwrap_div(c, cls):
    """深度计数解包 div.class（内含多个块级元素也不会错配）"""
    token = re.compile(r"<div\b[^>]*>|</div>")
    open_re = re.compile(r'<div[^>]*class="[^"]*\b' + cls + r'\b[^"]*"[^>]*>')
    out, pos, n = [], 0, 0
    while True:
        m = open_re.search(c, pos)
        if not m:
            break
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = token.search(c, j)
            if not m2:
                break
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end()
            close = m2
        if not close:
            break
        out.append(c[pos:m.start()])
        out.append(c[m.end():close.start()])
        pos = close.end()
        n += 1
    out.append(c[pos:])
    return "".join(out), n


def step_paras(c, name, ctx, rare):
    c, n = _unwrap_div(c, "kindle-cn-toc-level1")
    ctx["unwrap"] += n
    # 楷体整段
    def kai(m):
        ctx["kai"] += 1
        return '<p class="bodytext"><span class="kai">%s</span></p>' % m.group(1).strip()
    c = re.sub(r'<p class="kindle-cn-kai">(.*?)</p>', kai, c, flags=re.S)
    # 普通正文
    def body(m):
        ctx["paras"] += 1
        return '<p class="bodytext">%s</p>' % m.group(1).strip()
    c = re.sub(r'<p class="(?:calibre8|kindle-cn-para-no-indent|kindle-cn-para-2em-indent|kindle-cn-copyright-text)">(.*?)</p>',
               body, c, flags=re.S)
    # 行内 span
    c = re.sub(r'<span class="kindle-cn-(?:bold|hei)">(.*?)</span>', r"<b>\1</b>", c, flags=re.S)
    c = re.sub(r'<span class="kindle-cn-kai1">(.*?)</span>', r'<span class="kai">\1</span>', c, flags=re.S)
    return c


def step_figures(c, name, ctx, rare):
    """图文块：深度计数取出 div.kindle-cn-bodycontent-div-alone 的内容"""
    token = re.compile(r"<div\b[^>]*>|</div>")
    open_re = re.compile(r'<div[^>]*class="[^"]*\bkindle-cn-bodycontent-div-alone\b[^"]*"[^>]*>')
    out, pos = [], 0
    while True:
        m = open_re.search(c, pos)
        if not m:
            break
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = token.search(c, j)
            if not m2:
                break
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end()
            close = m2
        if not close:
            break
        inner = c[m.end():close.start()]
        imgs = re.findall(r'<img[^>]*?/>', inner)
        caps = [cap_txt(x) for x in re.findall(r'<p class="kindle-cn-picture-txt-[^"]*">(.*?)</p>', inner, re.S)]
        out.append(c[pos:m.start()])
        ctx["chatu"] += 1
        block = '<div class="chatu">\n' + "\n".join(
            '<p class="image">%s</p>' % re.sub(r'\s+class="[^"]*"', "", im) for im in imgs)
        if caps:
            ctx["caption"] += 1
            block += '\n<p class="caption">%s</p>' % "<br/>".join(x for x in caps if x)
        out.append(block + "\n</div>")
        pos = close.end()
    if not out:
        return c
    out.append(c[pos:])
    c = "".join(out)
    # 表格双图后的图注
    def lone(m):
        ctx["caption"] += 1
        return '<p class="caption">%s</p>' % cap_txt(m.group(1))
    c = re.sub(r'<p class="kindle-cn-picture-txt-(?:withfew|withmany)charactors">(.*?)</p>',
               lone, c, flags=re.S)
    return c


def step_inline_imgs(c, name, ctx, rare):
    def repl(m):
        tag = m.group(1)
        src = re.search(r'src="([^"]*)"', tag)
        base = os.path.basename(src.group(1)) if src else ""
        if base in rare:
            ctx["glyph"] += 1
            return rare[base]
        alt = re.search(r'alt="([^"]*)"', tag)
        return '<img src="%s" alt="%s"/>' % (src.group(1) if src else "", alt.group(1) if alt else "")
    c = re.sub(r'(<img[^>]*class="kindle-cn-inline-image1?"[^>]*/>)', repl, c)
    return c


def step_tables(c, name, ctx, rare):
    c = re.sub(r'<(table|tr|td|caption)\b[^>]*\sclass="[^"]*"', r"<\1", c)
    c = re.sub(r'<table cellspacing="\d+">', "<table>", c)
    return c


def step_misc(c, name, ctx, rare):
    c = re.sub(r'<hr class="calibre10"/>?', "<hr/>", c)
    c = re.sub(r'<p class="page-break"[^>]*>\s*</p>\s*', "", c)
    # split 文件已合并：partNNNN_split_MMM.xhtml -> partNNNN.xhtml
    c = re.sub(r'(part\d+)_split_\d+\.x?html', r'\1.xhtml', c)
    c = re.sub(r'<div class="calibre2"[^>]*>\s*</div>\s*', "", c)
    c = re.sub(r'<div class="empty">\s*</div>\s*', "", c)
    ctx["href"] += len(re.findall(r'href="[^"]*\.html', c))
    c = re.sub(r'(href="[^"]*?)\.html', r"\1.xhtml", c)
    return c


ALLOW_CLASSES = {"bodytext", "bodytext-noindent", "fnote", "chatu", "image", "caption",
                 "right", "center", "left", "sprt", "toc1", "toc2", "subtitle", "kai",
                 "intro", "poem", "author", "date", "ref", "cover", "footnoteup"}


def step_classes(c, name, ctx, rare):
    def repl(m):
        keep = [x for x in m.group(1).split() if x in ALLOW_CLASSES]
        return (' class="%s"' % " ".join(keep)) if keep else ""
    return re.sub(r' class="([^"]*)"', repl, c)


ALLOW_CLASSES = {"bodytext", "bodytext-noindent", "fnote", "chatu", "image", "caption",
                 "right", "center", "left", "sprt", "toc1", "toc2", "subtitle", "kai",
                 "intro", "poem", "author", "date", "ref", "cover", "footnoteup"}


def step_classes(c, name, ctx, rare):
    """只保留语义 class；calibre*/kindle-cn-* 等版式类一律去掉"""
    def repl(m):
        keep = [x for x in m.group(1).split() if x in ALLOW_CLASSES]
        return (' class="%s"' % " ".join(keep)) if keep else ""
    return re.sub(r' class="([^"]*)"', repl, c)


def step_ns(c, name, ctx, rare):
    if "epub:type=" in c and "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>", r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
    return c


def step_tidy(c, name, ctx, rare):
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        c = c[:hm.start()] + re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0)) + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        body = re.sub(r"\n[ \t]*\n+", "\n", body)
        c = pre + body
    return c


def step_append(c, name, ctx, rare):
    notes = ctx.get("fnotes") or []
    if not notes:
        return c
    fixed = []
    for fid, t in notes:
        t = re.sub(r'(<img[^>]*class="kindle-cn-inline-image1?"[^>]*/>)',
                   lambda m: step_inline_imgs(m.group(1), name, ctx, rare), t)
        t = re.sub(r'<span class="kindle-cn-(?:bold|hei)">(.*?)</span>', r"<b>\1</b>", t, flags=re.S)
        t = re.sub(r'<span class="kindle-cn-kai1">(.*?)</span>', r'<span class="kai">\1</span>', t, flags=re.S)
        t = step_classes(t, name, ctx, rare)
        fixed.append((fid, t))
    notes = fixed
    lines = ['<p class="fnote" id="foot-%d"><a href="#back-%d">[%d]</a> %s</p>'
             % (i + 1, i + 1, i + 1, t) for i, (fid, t) in enumerate(notes)]
    return c.replace("</body>", "<hr/>\n" + "\n".join(lines) + "\n</body>")


STEPS = [("css", step_css), ("body", step_body), ("toc", step_toc), ("footnotes", step_footnotes),
         ("headings", step_headings), ("paras", step_paras), ("figures", step_figures),
         ("inline_imgs", step_inline_imgs), ("tables", step_tables), ("misc", step_misc), ("classes", step_classes),
         ("ns", step_ns), ("tidy", step_tidy), ("append", step_append)]


# ---------- 校验 ----------
def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    for pat, msg in [
        (r'class="calibre\d', "残留 calibre class"),
        (r'class="kindle-cn-', "残留 kindle-cn class"),
        (r'href="[^"]*\.html(?:"|#)', "残留 .html 链接"),
        (r'<div class="empty"', "残留空 div"),
        (r'<p class="kindle-cn-', "残留 kindle-cn 段落"),
    ]:
        if re.search(pat, c):
            probs.append(msg)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 styles.css 链接")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    nref = len(re.findall(r'epub:type="noteref"', c))
    nfn = len(re.findall(r'<p class="fnote"', c))
    if nref != nfn:
        probs.append("noteref(%d) != fnote(%d)" % (nref, nfn))
    for m in re.finditer(r'href="#([^"]+)"', c):
        if m.group(1) not in ids:
            probs.append("悬空内链 #%s" % m.group(1))
            break
    for m in re.finditer(r'<img[^>]*src="([^"]*)"', c):
        p = os.path.normpath(os.path.join(dirpath, m.group(1)))
        if not os.path.exists(p):
            probs.append("图片不存在 %s" % m.group(1))
            break
    return probs


def analyze(dirpath, out=None):
    files = list_files(dirpath)
    import collections
    sig = collections.Counter()
    for fp in files:
        c = read(fp)
        for m in re.finditer(r'<(\w+)\b([^>]*)>', c):
            cm = re.search(r'class="([^"]*)"', m.group(2))
            sig["%s .%s" % (m.group(1), cm.group(1) if cm else "(#)")] += 1
    rep = "files=%d\n== element.class: %s\n" % (
        len(files), ", ".join("%s x%d" % kv for kv in sig.most_common(30)))
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)


def process(dirpath, dry=False):
    _st = ensure_styles(dirpath)
    if _st not in ("same", "copied"):
        print("styles.css: %s" % _st)
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml/*.html")
        sys.exit(1)
    rare = load_rare(dirpath)
    print("rare_map: %d 项" % len(rare))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(dirpath)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录: %s" % outdir)
    ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        ctx = dict.fromkeys(["css", "toc", "heads", "paras", "kai", "chatu", "caption",
                             "glyph", "year", "unwrap", "href"], 0)
        for sname, fn in STEPS:
            c = fn(c, name, ctx, rare)
        c = postprocess(c)
        probs = verify_content(c, name, dirpath)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        if not dry and name.endswith(".html"):
            newp = fp[:-5] + ".xhtml"
            if os.path.exists(newp):
                os.remove(newp)
            os.rename(fp, newp)
        print("%-20s css=%d toc=%d h=%-3d para=%-4d kai=%-3d 图=%-3d 注=%-3d 字图=%-2d 年表=%-3d unwrap=%-3d" % (
            name, ctx["css"], ctx["toc"], ctx["heads"], ctx["paras"], ctx["kai"],
            ctx["chatu"], len(ctx.get("fnotes") or []), ctx["glyph"], ctx["year"], ctx["unwrap"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)


def verify_dir(dirpath):
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, dirpath)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-20s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description="Kindle-cn（三联/学术注释版）源 xhtml 清洗")
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
        sys.exit(1)
    if a.cmd == "analyze":
        analyze(d, out=getattr(a, "out", None))
    elif a.cmd == "process":
        process(d, dry=a.dry_run)
    else:
        verify_dir(d)


if __name__ == "__main__":
    main()
