#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_indesign_calibre.py — InDesign→calibre（繁中·重注释）EPUB xhtml 清洗

适用特征（源文件）:
  <body id="story-N" class="calibre2">、<div class="calibre3"> 包裹
  <h1 id="_idParaDest-N" class="calibre4|h1_"><span class="small">标签</span>　章名</h1>
  <h5 class="calibre8">节</h5>、<h6 class="h6_b|h6_s">索引/注释小节</h6>、<h4 class="calibre12">书名</h4>
  正文 <p class="calibre5|p_|p_b|p_s|p_1|p_2|p_3|calibre11|text_tp">、署名 <p class="end|end_k">
  楷体引文 <p class="kai_n|kai_nb">、图 <div class="container"><img class="fit"/><p class="caption">…</p></div>
  表 <table class="calibre9"><tr class="calibre10"><td class="td_|td_1">
  生僻字内嵌图 <img class="pw" src="image/a1.jpg"/>（a1=燠 a2=賴）
  章内脚注: <div class="foot"><hr class="calibre6"/><p class="footnote"><a id="foot-NNN" href="#back-NNN" class="green">[N]</a>注文</p></div>
            正文 ref <a id="back-NNN" href="story-N.xhtml#foot-NNN" class="ref1">N</a>
  跨文件引用注: ref <a id="back-aN" href="story-28.xhtml#foot-aN" class="ref1">N</a>（正文各章）
            注 <p class="footnote_a|_b|_c"><a id="foot-aN" href="story-20.xhtml#back-aN" class="calibre7">N</a>文献…（在 story-28* 注释章）

映射:
  css -> styles.css；body 去 class；div.calibre3 解包
  h1.calibre4|h1_ -> <h1>（span.small -> span.subtitle）；h5.calibre8 -> <h3>；h6.h6_* -> <h4>；h4.calibre12 -> <h4>
  正文 p.calibre5/p_*/calibre11/text_tp -> <p class="bodytext">；p.end|end_k -> <p class="right">
  p.kai_n|kai_nb（连续）-> <blockquote><p class="bodytext">；p.caption 保留；<p …>　</p> 空段删除
  div.container -> chatu；table/tr/td 去 class 保留；div.box/copyright 解包
  span.small1->small、bold1->bold；italic/kai/bold 保留
  章内脚注 -> 章末 <hr/> + <p class="fnote" id="foot-NNN">（每文件 [1] 重排、双向回链）
  跨文件引用注 ref -> <sup><a epub:type="noteref" href="story-28*xhtml#foot-aN" id="back-aN">[N]</a></sup>（编号不重排）
  固定版式页（meta viewport+SVG）原样保留

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:stylesheet|page_styles|style\d+)\.css",
    "wrapper_div": "calibre3",
    "rare_img_map": {"image/a1.jpg": "燠", "image/a2.jpg": "賴"},
    "bodytext_classes": ["calibre5", "p_", "p_1", "p_2", "p_3", "p_b", "p_s", "calibre11", "text_tp"],
    "right_classes": ["end", "end_k"],
    "quote_classes": ["kai_n", "kai_nb"],
    "footnote_p_re": r'<p class="footnote(?:_[abc])?">',
}

def list_files(d):
    files = []
    for pat in ("*.xhtml", "*.html"):
        files += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    return sorted(set(files), key=lambda p: (0, int(re.search(r'(\d+)', os.path.basename(p)).group(1)))
                  if re.search(r'\d', os.path.basename(p)) else (1, os.path.basename(p)))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def cls_of(attrs):
    m = re.search(r'class="([^"]*)"', attrs)
    return set(m.group(1).split()) if m else set()

def txt(s):
    return re.sub(r"\s+", "", re.sub(r"</?[^>]+>", "", s))

def flat(s):
    """保留内部空格与行内 span（英文脚注需要），去掉源 calibre 类"""
    s = re.sub(r'\s+class="calibre[^"]*"', "", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
        ctx["css"] += 1
    return c

def step_body(c, name, ctx):
    ctx["body"] += len(re.findall(r'<body[^>]*\bclass="[^"]*"', c))
    c = re.sub(r'<body([^>]*?)\s*class="[^"]*"\s*([^>]*)>', r'<body\1\2>', c)
    return re.sub(r'<body\s*>', '<body>', c)

def step_residual(c, name, ctx):
    c = re.sub(r'\s+class="calibre[^"]*"', "", c)
    return c

def step_rare(c, name, ctx):
    def repl(m):
        src = re.search(r'src="([^"]*)"', m.group(1))
        ch = CONFIG["rare_img_map"].get(src.group(1) if src else "")
        if ch is None:
            return m.group(0)
        ctx["rare"] += 1
        return ch
    return re.sub(r'<img\b([^>]*class="[^"]*\bpw\b[^"]*"[^>]*)/>', repl, c)

def step_figures(c, name, ctx):
    pat = re.compile(r'<div class="container">\s*<div[^>]*>\s*(<img[^>]*?/>)\s*(<p class="caption">.*?</p>)?\s*</div>\s*</div>', re.S)
    def repl(m):
        ctx["chatu"] += 1
        img = m.group(1)
        src = re.search(r'src="([^"]*)"', img)
        alt = re.search(r'alt="([^"]*)"', img)
        out = '<div class="chatu">\n<p class="image"><img src="%s" alt="%s"/></p>' % (
            src.group(1) if src else "", alt.group(1) if alt else "")
        if m.group(2):
            cap = re.sub(r'<span class="kai">(.*?)</span>', r'\1', m.group(2).strip(), flags=re.S)
            out += "\n" + cap
        return out + "\n</div>"
    return pat.sub(repl, c)

def step_footnotes(c, name, ctx):
    own = {}
    def foot(m):
        for pm in re.finditer(r'<p class="footnote[^"]*">\s*<a id="([^"]*)"[^>]*>\[[^\]]*\]</a>\s*(.*?)</p>', m.group(0), re.S):
            own[pm.group(1)] = flat(pm.group(2))
        return ""
    c = re.sub(r'(?s)[ \t]*<div class="foot">.*?</div>\n?', foot, c)

    def hrefs():
        return c
    order = []
    seq = {}
    ref = re.compile(r'<a id="(back-[^"]*)" href="([^"]*)#([^"]*)" class="[^"]*">(\d+)</a>')
    def rr(m):
        rid, tgt, num = m.group(1), m.group(2), m.group(4)
        nid = m.group(3)
        if nid in own:                       # 章内注：重排
            if rid not in seq:
                order.append(nid)
                seq[rid] = len(order)
            k = seq[rid]
            return '<sup><a epub:type="noteref" href="#%s" id="%s">[%d]</a></sup>' % (nid, rid, k)
        # 跨文件引用注：编号不重排，保留原 href
        return '<sup><a epub:type="noteref" href="%s#%s" id="%s">[%s]</a></sup>' % (m.group(2), nid, rid, num)
    c = ref.sub(rr, c)
    if own:
        # 章内尾注按 order 重排；同文件里没有 ref 的（罕见）附在后面
        ordered = [nid for nid in order] + [nid for nid in own if nid not in order]
        lines = []
        for k, nid in enumerate(ordered, 1):
            lines.append('<p class="fnote" id="%s"><a href="#%s">[%d]</a> %s</p>'
                         % (nid, nid.replace('foot-', 'back-'), k, own[nid]))
        ctx["fnotes"] = lines
        if not order and len(own) != len(ordered):
            ctx["unref"] += len(own) - len(order)
    # 注释章里的跨文件注（foot-aN/jN 等）就地转 fnote，编号保留
    def note(m):
        pm = m
        return '<p class="fnote" id="%s"><a href="%s">[%s]</a> %s</p>' % (
            pm.group(1), pm.group(2), pm.group(4), txt(pm.group(3)))
    c = re.sub(r'<p class="footnote[^"]*">\s*<a id="(foot-[^"]*)" href="([^"]*)#([^"]*)" class="[^"]*">\[?(\d+)\]?</a>\s*(.*?)</p>',
               lambda m: '<p class="fnote" id="%s"><a href="%s#%s">[%s]</a> %s</p>'
               % (m.group(1), m.group(2), m.group(3), m.group(4), flat(m.group(5))), c, flags=re.S)
    return c

def step_append(c, name, ctx):
    if not ctx["fnotes"]:
        return c
    block = "<hr/>\n" + "\n".join(ctx["fnotes"]) + "\n"
    return c.replace("</body>", block + "</body>")

def h1_inner(inner):
    # <span class="small"> 是「标签」（推薦序 / 第一章 …）。源用 　 把它与标题连在同一行，
    # 因此直接去掉标签 span（保留 　）；只有真的分行（<br/>）时才保留 <span class="subtitle">
    if re.search(r'<br\s*/?>', inner):
        return re.sub(r'<span class="small">(.*?)</span>', r'<span class="subtitle">\1</span>', inner, flags=re.S)
    return re.sub(r'<span class="small">(.*?)</span>', r'\1', inner, flags=re.S)

def step_headings(c, name, ctx):
    def mkh(tag):
        def repl(m):
            ctx["heads"] += 1
            return "<%s%s>%s</%s>" % (tag, (' id="%s"' % m.group(1)) if m.group(1) else "", h1_inner(m.group(2)).strip(), tag)
        return repl
    c = re.sub(r'<h1\b[^>]*\bid="([^"]*)"[^>]*class="(?:calibre4|h1_)"[^>]*>(.*?)</h1>', mkh("h1"), c, flags=re.S)
    c = re.sub(r'<h1\b(?![^>]*\bid=)([^>]*)class="(?:calibre4|h1_)"([^>]*)>(.*?)</h1>',
               lambda m: "<h1>%s</h1>" % h1_inner(m.group(3)).strip(), c, flags=re.S)
    c = re.sub(r'<h5\b[^>]*class="calibre8"[^>]*>(.*?)</h5>', lambda m: "<h3>%s</h3>" % m.group(1).strip(), c, flags=re.S)
    c = re.sub(r'<h6\b[^>]*class="h6_[bs]"[^>]*>(.*?)</h6>', lambda m: "<h4>%s</h4>" % m.group(1).strip(), c, flags=re.S)
    c = re.sub(r'<h4\b[^>]*class="calibre12"[^>]*>(.*?)</h4>', lambda m: "<h4>%s</h4>" % m.group(1).strip(), c, flags=re.S)
    return c

def step_quotes(c, name, ctx):
    qs = "|".join(re.escape(x) for x in CONFIG["quote_classes"])
    pat = re.compile(r'<p\b[^>]*class="[^"]*\b(?:%s)\b[^"]*"[^>]*>(.*?)</p>' % qs, re.S)
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
        def qtext(x):
            t = re.sub(r'<span class="kai">(.*?)</span>', r'\1', x.group(1), flags=re.S)  # 引文内不用 span.kai
            return '<p class="bodytext">%s</p>' % t.strip()
        body = "\n".join(qtext(x) for x in g)
        c = c[:start] + "<blockquote>\n" + body + "\n</blockquote>" + c[end:]
        ctx["quotes"] += len(g)
    return c

def step_paras(c, name, ctx):
    # 空行段（仅全角空格）→ <p class="bodytext"><br/></p>（保留源书空行：落款/署名前后、推荐语之间等）
    bc = "|".join(CONFIG["bodytext_classes"])
    def spacer(m):
        ctx["spacer"] += 1
        return '<p class="bodytext"><br/></p>'
    c = re.sub(r'<p class="(?:%s)">[\u3000\s]*</p>' % bc, spacer, c)
    # 署名 / 章首作者：紧跟在 </h1> 之后的署名段 = 该章作者 → <p class="author">（去内层 span）；
    # 其余（——落款、序末署名等）→ <p class="right">
    rc = "|".join(CONFIG["right_classes"])
    def sig(m):
        inner = m.group(1).strip()
        if c[:m.start()].rstrip().endswith("</h1>"):
            ctx["author"] += 1
            return '<p class="author">%s</p>' % re.sub(r"</?span[^>]*>", "", inner)
        ctx["right"] += 1
        return '<p class="right">%s</p>' % inner
    c = re.sub(r'<p class="(?:%s)">(.*?)</p>' % rc, sig, c, flags=re.S)
    # 正文
    bc = "|".join(CONFIG["bodytext_classes"])
    c = re.sub(r'<p class="(?:%s)">(.*?)</p>' % bc, lambda m: '<p class="bodytext">%s</p>' % m.group(1).strip(), c, flags=re.S)
    # 兜底：残留源 class 的 p → bodytext；**不动已产出的语义类**
    keep = r'(?:bodytext|right|caption|image|fnote|sprt|author|subtitle)'
    c = re.sub(r'<p class="(?!%s\b)[^"]*">(.*?)</p>' % keep,
               lambda m: '<p class="bodytext">%s</p>' % m.group(1).strip(), c, flags=re.S)
    return c

def step_table(c, name, ctx):
    c = re.sub(r'<(table|tr|td)\b[^>]*class="[^"]*"([^>]*)>',
               lambda m: "<%s%s>" % (m.group(1), m.group(2)), c)
    return c

def step_spans(c, name, ctx):
    c = re.sub(r'<span class="small1">', '<span class="small">', c)
    c = re.sub(r'<span class="bold1">', '<span class="bold">', c)
    return c

def step_unwrap_extra(c, name, ctx):
    for cls in ("box", "copyright"):
        pat = re.compile(r'<div\b[^>]*\bclass="[^"]*\b%s\b[^"]*"[^>]*>' % cls)
        while True:
            m = pat.search(c)
            if not m:
                break
            tok = re.compile(r"<div\b[^>]*>|</div>")
            depth, j, close = 1, m.end(), None
            while depth:
                m2 = tok.search(c, j)
                if not m2:
                    raise RuntimeError("%s: div.%s 不配对" % (name, cls))
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

def step_unwrap(c, name, ctx):
    pat = re.compile(r'<div\b[^>]*\bclass="%s"[^>]*>' % re.escape(CONFIG["wrapper_div"]))
    while True:
        m = pat.search(c)
        if not m:
            break
        tok = re.compile(r"<div\b[^>]*>|</div>")
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = tok.search(c, j)
            if not m2:
                raise RuntimeError("%s: div 不配对" % name)
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

STEPS = [("css", step_css), ("body", step_body), ("rare", step_rare), ("figures", step_figures),
         ("footnotes", step_footnotes), ("headings", step_headings), ("quotes", step_quotes),
         ("paras", step_paras), ("table", step_table), ("spans", step_spans),
         ("unwrap_extra", step_unwrap_extra), ("unwrap", step_unwrap), ("residual", step_residual),
         ("tidy", step_tidy), ("append", step_append)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    if re.search(r'class="calibre|\bclass="(?:h6_|h1_|p_|p_b|p_s|kai_n|footnote|end)', c):
        probs.append("残留源 class")
    if '<div class="foot"' in c or '<hr class="calibre6"' in c:
        probs.append("残留脚注结构")
    for bq in re.finditer(r'<blockquote>(.*?)</blockquote>', c, re.S):
        if 'class="kai"' in bq.group(1):
            probs.append("引文 blockquote 内残留 span.kai")
            break
    for cap in re.finditer(r'<p class="caption">(.*?)</p>', c, re.S):
        if 'class="kai"' in cap.group(1):
            probs.append("图注 p.caption 内残留 span.kai")
            break
    for h in re.finditer(r'<h1\b[^>]*>(.*?)</h1>', c, re.S):
        if 'class="subtitle"' in h.group(1) and '<br' not in h.group(1):
            probs.append("h1 未分行却保留 span.subtitle")
            break
    if re.search(r'class="pw"', c):
        probs.append("残留生僻字图")
    if re.search(r'href="[^"]*' + CONFIG["drop_css_re"] + r'"', c):
        probs.append("残留旧 css 链接")
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    return probs

def analyze(dirpath, out=None):
    import collections
    L = ["# analyze(indesign-calibre): %s" % dirpath, ""]
    files = list_files(dirpath)
    sig = collections.Counter(); feat = collections.Counter()
    for fp in files:
        c = read(fp)
        for m in re.finditer(r'<(p|div|h1|h4|h5|h6|span|a|img|table)\b([^>]*)>', c):
            cm = re.search(r'class="([^"]*)"', m.group(2))
            sig['%s .%s' % (m.group(1), cm.group(1) if cm else '(#)')] += 1
        if '<div class="foot"' in c: feat['div.foot'] += 1
        if 'class="container"' in c: feat['container'] += 1
        if 'viewport' in c: feat['fixed-layout'] += 1
        if 'class="pw"' in c: feat['rare-img'] += 1
    L.append("files=%d" % len(files))
    L.append("== element.class: %s" % ", ".join("%s x%d" % kv for kv in sig.most_common(30)))
    L.append("== feat: %s" % ", ".join("%s x%d" % kv for kv in feat.most_common()))
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
        ctx = dict.fromkeys(["css", "body", "rare", "chatu", "heads", "quotes", "unwrap",
                             "blank", "unref", "author", "right", "spacer"], 0)
        ctx["fnotes"] = []
        for s, fn in STEPS:
            c = fn(c, name, ctx)
        probs = verify_content(c, name, dirpath)
        if probs:
            ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-18s rare=%-2d chatu=%-2d fnote=%-3d heads=%-2d quote=%-3d unwrap=%-2d" % (
            name, ctx["rare"], ctx["chatu"], len(ctx["fnotes"]), ctx["heads"], ctx["quotes"], ctx["unwrap"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(dirpath):
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, dirpath)
        if probs:
            ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-18s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="InDesign→calibre 源 xhtml 清洗")
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
