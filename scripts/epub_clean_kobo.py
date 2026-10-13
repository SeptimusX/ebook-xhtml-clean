#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_kobo.py — Kobo 导出（「多看」式排版）EPUB xhtml 清洗

适用特征（源文件）:
  <style type="text/css" class="kobostylehacks">…</style> + <link href="../Styles/css.css"/>
  <div id="book-columns"><div id="book-inner"> 包裹；正文每一段文字都被
  <span class="koboSpan" id="kobo.N.M">…</span> 逐句包裹
  <h1 class="h2">楔子　北境</h1>（章标题页）/ <h1 class="h1">后记</h1> / <h2>一</h2>（节）
  <p>正文</p>、<p class="no fs"><b>年份</b></p>（年表）、<p class="kh">楷体引文</p>
  <div class="hr"><p class="fs center">引文</p><p class="fs right">——落款<br/>《出处》</p></div>（章首题词）
  <div class="logo"/><div class="image"/>（空装饰）
  脚注: 正文 <a class="duokan-footnote" epub:type="noteref" href="#B_N" id="A_N"><img src="../Images/06.png"/></a>
        文末 <aside epub:type="footnote"><div><hr class="xian"/></div>
             <ol class="duokan-footnote-content"><li class="duokan-footnote-item" id="B_N">
             <p class="footnote"><a href="#A_N">⊙</a>注文</p></li></ol></aside>

映射:
  koboSpan -> 去 span 留文字；book-columns/book-inner -> 解包
  <p> / p.fs / p.no fs / p.cp / p.cp1 / p.vol / p.bookname -> <p class="bodytext">（去段首全角空格）
  p.center kt -> <p class="center">；p.right / p.fs right -> <p class="right">
  p.kh（连续）-> <blockquote><p class="bodytext">（每行独立成段）
  div.hr（章首题词）-> <blockquote class="intro">（引文 bodytext、落款 right、块内拆 <br/>）
  h1.h1 / h1.h2 -> <h1>；h1[display:none] -> 删；<h2> 保留；<h3><span class="h3kt"> -> <h3>
  div.logo / div.image（空装饰）-> 删除
  脚注 -> 章末 <hr/> + <p class="fnote" id="B_N"><a href="#noteref-K">[K]</a> 注文</p>（每文件从 1、双向回链）
  css -> styles.css（删 kobostylehacks 内联 style 与 ../Styles/css.css）

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:css|stylesheet|page_styles|style\d+)\.css",
    "wrap_ids": ["book-columns", "book-inner"],
    "drop_div_classes": ["logo", "image"],
    "drop_div_style_re": r"page-break-before\s*:\s*always",
    "epigraph_div": "hr",
    "quote_classes": ["kh"],
    "bodytext_class_re": None,   # None = 下面的 bodytext_classes 列表
    "bodytext_classes": ["fs", "cp", "cp1", "vol", "bookname", "no"],
    "center_pairs": [("center", "kt")],
    "decorative_empty_body": False,
}

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

def classes(attrs):
    m = re.search(r'class="([^"]*)"', attrs)
    return set(m.group(1).split()) if m else set()

def drop_div(c, pat_open):
    """按 class/style 找到 div，深度计数删除（含内容）"""
    out = c
    while True:
        m = pat_open.search(out)
        if not m:
            break
        tok = re.compile(r"<div\b[^>]*>|</div>")
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = tok.search(out, j)
            if not m2:
                break
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end(); close = m2
        a, b = m.start(), m.end()
        if out[b:b+1] == "\n":
            b += 1
        cs, ce = close.start(), close.end()
        if out[cs-1:cs] == "\n" and out[ce:ce+1] in ("", "\n"):
            cs -= 1
        out = out[:a] + out[b:cs] + out[ce:]
    return out

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c = re.sub(r'(?s)[ \t]*<style[^>]*class="kobostylehacks"[^>]*>.*?</style>[ \t]*\n?', "", c)
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
        ctx["css"] += 1
    return c

def step_body(c, name, ctx):
    n = len(re.findall(r'<body[^>]*class="[^"]*">', c))
    ctx["body"] += n
    return re.sub(r'<body[^>]*class="[^"]*">', "<body>", c)

def step_strip_kobo(c, name, ctx):
    pat = re.compile(r'<span[^>]*class="koboSpan"[^>]*>((?:(?!<span).)*?)</span>', re.S)
    while True:
        c, n = pat.subn(r"\1", c)
        ctx["kobo"] += n
        if not n:
            break
    return c

def step_wrap(c, name, ctx):
    for wid in CONFIG["wrap_ids"]:
        pat = re.compile(r'<div\b[^>]*\bid="%s"[^>]*>' % re.escape(wid))
        while True:
            m = pat.search(c)
            if not m:
                break
            tok = re.compile(r"<div\b[^>]*>|</div>")
            depth, j, close = 1, m.end(), None
            while depth:
                m2 = tok.search(c, j)
                if not m2:
                    raise RuntimeError("%s: div#%s 不配对" % (name, wid))
                depth += -1 if m2.group(0).startswith("</") else 1
                j = m2.end(); close = m2
            a, b = m.start(), m.end()
            if c[b:b+1] == "\n":
                b += 1
            cs, ce = close.start(), close.end()
            if c[cs-1:cs] == "\n" and c[ce:ce+1] in ("", "\n"):
                cs -= 1
            c = c[:a] + c[b:cs] + c[ce:]
            ctx["unwrap"] += 1
    return c

def step_drop_divs(c, name, ctx):
    for cls in CONFIG["drop_div_classes"]:
        pat = re.compile(r'<div\b[^>]*\bclass="[^"]*\b%s\b[^"]*"[^>]*>' % re.escape(cls))
        before = c
        c = drop_div(c, pat)
        ctx["dropdiv"] += 0 if c == before else 1
    if CONFIG.get("drop_div_style_re"):
        pat = re.compile(r'<div\b[^>]*\bstyle="[^"]*' + CONFIG["drop_div_style_re"] + r'[^"]*"[^>]*>')
        c = drop_div(c, pat)
    return c

def step_headings(c, name, ctx):
    # 隐藏 h1（版权页）
    c2 = re.sub(r'(?s)<h1\b[^>]*style="[^"]*display\s*:\s*none[^"]*"[^>]*>.*?</h1>\s*', "", c)
    if c2 != c:
        ctx["hdrop"] += 1
        c = c2
    # h1.h1 / h1.h2 -> <h1>
    def h1(m):
        ctx["h1"] += 1
        idm = re.search(r'\bid="([^"]*)"', m.group("attrs"))
        return "<h1%s>%s</h1>" % ((' id="%s"' % idm.group(1)) if idm else "", m.group("body").strip())
    c = re.sub(r'<h1\b(?P<attrs>[^>]*)>(?P<body>.*?)</h1>', h1, c, flags=re.S)
    # <h3><span class="h3kt">…</span></h3> -> <h3>
    c = re.sub(r'<h3\b([^>]*)>\s*<span[^>]*class="h3kt"[^>]*>(.*?)</span>\s*</h3>',
               lambda m: "<h3%s>%s</h3>" % (m.group(1), m.group(2).strip()), c, flags=re.S)
    # 残留 <span class="h3kt">
    c = re.sub(r'<span[^>]*class="h3kt"[^>]*>(.*?)</span>', r"\1", c, flags=re.S)
    return c

def step_footnotes(c, name, ctx):
    notes = {}
    def aside(m):
        inner = m.group(1)
        for li in re.finditer(r'<li\b[^>]*id="([^"]*)"[^>]*>\s*<p class="footnote">(.*?)</p>', inner, re.S):
            fid, p = li.group(1), li.group(2)
            txt = re.sub(r'(?s)<a\b[^>]*>.*?</a>', "", p)      # 去掉前面的 ⊙ 回链
            notes[fid] = re.sub(r"\s+", "", re.sub(r"</?[^>]+>", "", txt))
        return ""
    c = re.sub(r'(?s)<aside epub:type="footnote">(.*?)</aside>\n?', aside, c)
    order = []
    a_pat = re.compile(r'<a\b[^>]*class="duokan-footnote"[^>]*>.*?</a>', re.S)
    def arepl(m):
        tag = m.group(0)
        hm = re.search(r'href="#([^"]*)"', tag)
        fid = hm.group(1) if hm else ""
        order.append(fid)
        k = len(order)
        ctx["nref"] += 1
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%d]</a></sup>' % (fid, k, k)
    c = a_pat.sub(arepl, c)
    if order:
        def fids():
            used = {}
            out = []
            for fid in order:
                if fid and fid not in used:
                    used[fid] = 1
                    out.append(fid)
                else:
                    i = len(out) + 1
                    nf = "footnote-%d" % i
                    while nf in used:
                        nf += "x"
                    used[nf] = 1
                    out.append(nf)
            return out
        fs = fids()
        # noteref 的 href 需要指向去重后的 id
        for k, (old, new) in enumerate(zip(order, fs), 1):
            if old != new:
                c = c.replace('href="#%s" id="noteref-%d"' % (old, k), 'href="#%s" id="noteref-%d"' % (new, k))
        ctx["fnotes"] = [(fs[i], i + 1, notes.get(order[i], "")) for i in range(len(order))]
    return c

def step_append(c, name, ctx):
    if not ctx["fnotes"]:
        return c
    block = "<hr/>\n" + "\n".join(
        '<p class="fnote" id="%s"><a href="#noteref-%d">[%d]</a> %s</p>' % (fid, i, i, txt)
        for fid, i, txt in ctx["fnotes"]) + "\n"
    return c.replace("</body>", block + "</body>")

def step_epigraph(c, name, ctx):
    div_cls = re.escape(CONFIG["epigraph_div"])
    pat = re.compile(r'<div\b[^>]*\bclass="[^"]*\b%s\b[^"]*"[^>]*>(.*?)</div>' % div_cls, re.S)
    def repl(m):
        inner = m.group(1)
        lines = []
        for pm in re.finditer(r'<p\b([^>]*)>(.*?)</p>', inner, re.S):
            cl = classes(pm.group(1))
            body = pm.group(2).strip()
            cls = "right" if "right" in cl else "bodytext"
            for seg in re.split(r'<br\s*/?>', body):
                seg = seg.strip()
                if seg:
                    lines.append('<p class="%s">%s</p>' % (cls, seg))
        ctx["epigraph"] += 1
        return '<blockquote class="intro">\n' + "\n".join(lines) + "\n</blockquote>"
    return pat.sub(repl, c)

def step_quotes(c, name, ctx):
    qs = "|".join(re.escape(x) for x in CONFIG["quote_classes"])
    pat = re.compile(r'<p\b[^>]*\bclass="[^"]*\b(?:%s)\b[^"]*"[^>]*>(.*?)</p>' % qs, re.S)
    ms = list(pat.finditer(c))
    if not ms:
        return c
    groups, cur = [], [ms[0]]
    for prev, m in zip(ms, ms[1:]):
        if c[prev.end():m.start()].strip() == "":
            cur.append(m)
        else:
            groups.append(cur); cur = [m]
    groups.append(cur)
    for g in reversed(groups):
        start, end = g[0].start(), g[-1].end()
        body = "\n".join('<p class="bodytext">%s</p>' % x.group(1).strip() for x in g)
        c = c[:start] + "<blockquote>\n" + body + "\n</blockquote>" + c[end:]
        ctx["quotes"] += len(g)
    return c

def step_paras(c, name, ctx):
    def repl(m):
        attrs, body = m.group(1), m.group(2)
        cl = classes(attrs)
        if "right" in cl:
            cls = "right"
        elif "center" in cl or "vol" in cl:
            cls = "center"
        else:
            cls = "bodytext"
        body = re.sub(r'^[\u3000\s]+', "", body.strip())
        ctx["bodytext"] += 1
        return '<p class="%s">%s</p>' % (cls, body)
    pat = re.compile(r'<p\b([^>]*)>(.*?)</p>', re.S)
    return pat.sub(repl, c)

def step_tidy(c, name, ctx):
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        head = re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0))
        c = c[:hm.start()] + head + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        ctx["blank"] += len(re.findall(r"^[ \t]*\n", body, re.M))
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        c = pre + body
    return c

STEPS = [("css", step_css), ("body", step_body), ("kobo", step_strip_kobo), ("wrap", step_wrap),
         ("dropdiv", step_drop_divs), ("headings", step_headings), ("footnotes", step_footnotes),
         ("epigraph", step_epigraph), ("quotes", step_quotes), ("paras", step_paras),
         ("tidy", step_tidy), ("append", step_append)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    if "koboSpan" in c or "kobo." in c:
        probs.append("残留 koboSpan")
    if "duokan-footnote" in c or "<aside" in c:
        probs.append("残留脚注结构")
    if 'class="kh"' in c or 'class="fs' in c or 'class="no' in c or 'class="h3kt"' in c:
        probs.append("残留源 class")
    if "book-columns" in c or "book-inner" in c:
        probs.append("残留包裹 div")
    if re.search(r'href="[^"]*' + CONFIG["drop_css_re"] + r'"', c):
        probs.append("残留旧 css 链接")
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    for src in re.findall(r'<img[^>]*?src="([^"]+)"', c):
        if not os.path.exists(os.path.normpath(os.path.join(dirpath, src))):
            probs.append("图片不存在 %s" % src)
    mk = len(re.findall(r'<sup><a epub:type="noteref"', c))
    fn = len(re.findall(r'<p class="fnote"', c))
    if mk != fn:
        probs.append("注释标记(%d) != 尾注(%d)" % (mk, fn))
    return probs

def analyze(dirpath, out=None):
    L = ["# analyze(kobo/duokan): %s" % dirpath, ""]
    files = list_files(dirpath)
    import collections
    cls = collections.Counter(); tags = collections.Counter()
    for fp in files:
        c = read(fp)
        for t in re.findall(r'<([a-zA-Z][\w:]*)[\s>/]', c):
            tags[t.lower()] += 1
        for cl in re.findall(r'class="([^"]*)"', c):
            for x in cl.split():
                cls[x] += 1
    L.append("files=%d" % len(files))
    L.append("== tags: %s" % ", ".join("%s x%d" % kv for kv in tags.most_common(20)))
    L.append("== classes: %s" % ", ".join("%s x%d" % kv for kv in cls.most_common(40)))
    used = collections.Counter()
    for fp in files:
        for src in re.findall(r'<img[^>]*?src="([^"]+)"', read(fp)):
            used[src] += 1
    L.append("== images: %s" % ", ".join("%s x%d" % kv for kv in used.most_common()))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def process(dirpath, dry=False):
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml")
        sys.exit(1)
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
        ctx = dict.fromkeys(["css", "body", "kobo", "unwrap", "dropdiv", "hdrop", "h1",
                             "nref", "epigraph", "quotes", "bodytext", "blank"], 0)
        ctx["fnotes"] = []
        for s, fn in STEPS:
            c = fn(c, name, ctx)
        probs = verify_content(c, name, dirpath)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s kobo=%-4d h1=%-2d hdrop=%-d epi=%-2d quote=%-3d body=%-4d fnote=%-3d unwrap=%-2d" % (
            name, ctx["kobo"], ctx["h1"], ctx["hdrop"], ctx["epigraph"], ctx["quotes"],
            ctx["bodytext"], len(ctx["fnotes"]), ctx["unwrap"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(dirpath):
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, dirpath)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-16s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="Kobo(duokan 式)源 xhtml 清洗")
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
