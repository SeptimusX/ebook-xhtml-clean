#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_indesign_epub3.py — InDesign EPUB3（ebookredo）源 xhtml 清洗

适用特征（源文件）:
  <body id="BK7026X-N">、外层无 class 的 <div> 包裹；css 链 css/YYYY.N.h.css；同目录另有规范版 styles.css
  正文 <p class="ff_serif fz_1-0em ti_2em">、顶格 <p class="ff_serif fz_1-0em ta_left">
  楷体引文 <p class="ff_cursive fz_1-0em mg-str_2-0em">、署名 <p class="… ta_right">
  小标题 <p class="ff_serif fz_1-6em ta_left">（如「參考書目」）、居中行 <p class="ff_sans fz_1-0em ta_center">
  章首作者 <p class="ff_sans fz_0-8em ta_left">（紧跟 </h1> 之后）
  行内 <span class="ff_serif|ff_sans fw_900">（粗）、<span class="ff_cursive fs_italic">（斜）
  脚注（EPUB3）：正文 <span class="ff_sans fz_0-6em va_super"><span>
      <a id="footnote-NNN-backlink" class="_idFootnoteLink" role="doc-noteref" epub:type="noteref" href="FILE#footnote-NNN">NN</a></span></span>
    文末 <hr class="HorizontalRule-1"/> + <section class="_idFootnotes" epub:type="endnotes"><ol class="_idFootAndEndNoteOLAttrs">
      <li id="footnote-NNN" class="_idFootnote"><p class="ff_serif fz_0-8em ta_left">
      <a class="_idFootnoteAnchor" role="doc-backlink" href="FILE#footnote-NNN-backlink">NN</a>：注文</p></li></ol></section>
  图 <div class="mg-str_10pr mg-end_10pr"><img …/></div>；引文框 <div class="bd-w_1px … box">
  空行段 <p class="…">　</p>；h1 带 id="_idParaDest-N"（toc 按它跳转）

映射（统一到同目录 styles.css）:
  css -> styles.css；body 去 class（保留 id）；无 class 的 <div> 深度计数解包
  <title> 改为该文件第一个 h1 的文字
  正文 -> p.bodytext（ti_2em/mg-str 带缩进）、ta_left -> p.bodytext-noindent、ta_right -> p.right
  ff_cursive 段（连续）-> <blockquote><p class="bodytext">；fz_1-6em 段 -> <h3>；ff_sans ta_center -> p.sprt
  紧跟 </h1> 的 ff_sans fz_0-8em ta_left -> p.author
  行内：ff_serif/ff_sans fw_900 -> <b>；ff_cursive fs_italic -> <i>（+fw_900 则 <b><i>）；ff_cursive -> <span class="kai">
  脚注：ref -> <sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>；
        注（收集全篇所有 section 里的 li）-> 全部 <section>/<hr> 收起，末尾只留一个 <hr/> + 一串
        <p class="fnote" id="foot-K"><a href="#back-K">[K]</a> 注文</p>（每文件=每章从 1 重排）
  图 -> <div class="chatu"><p class="image"><img …/></p></div>；引文框 -> <div class="box">
  <p>　</p> -> <p class="bodytext"><br/></p>（连续折为一个）
  未在映射里的 p.ff_* 兜底为 bodytext 并计数（报告里列出）；span 兜底去 class

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:\d{4}\.\d+\.h\.css|stylesheet\.css|page_styles\d*\.css|style\d+\.css)",
    "bodytext_re": r"ff_serif fz_1-0em ti_2em|ff_serif fz_1-0em mg-str_2-0em mg-end_2-0em",
    "noindent_re": r"ff_serif fz_1-0em ta_left",
    "right_re": r"ff_serif fz_1-0em ta_right|ff_cursive fz_1-0em ta_right",
    "quote_re": r"ff_cursive fz_1-0em mg-str_2-0em",
    "h3_re": r"ff_serif fz_1-6em ta_left",
    "sprt_re": r"ff_sans fz_1-0em ta_center",
    "author_re": r"ff_sans fz_0-8em ta_left",
    "note_p_re": r"ff_serif fz_0-8em ta_left",
}

def list_files(d):
    files = glob.glob(os.path.join(d, "*.xhtml")) + glob.glob(os.path.join(d, "*.html"))
    def key(p):
        m = re.search(r"-(\d+)\.xhtml?$", os.path.basename(p))
        if m:
            return (0, int(m.group(1)))
        return (1, os.path.basename(p))
    return sorted(set(files), key=key)

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def flat(s):
    s = re.sub(r"\s+class=\"(?:ff_|fz_|ti_|ta_|mg-|fw_|fs_|va_)[^\"]*\"", "", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
        ctx["css"] += 1
    return c

def step_title(c, name, ctx):
    m = re.search(r'<h1\b[^>]*>(.*?)</h1>', c, re.S)
    if m:
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        c, n = re.subn(r"<title>.*?</title>", "<title>%s</title>" % t, c, flags=re.S)
        ctx["title"] += n
    return c

def step_headings(c, name, ctx):
    def repl(m):
        idm = re.search(r'\bid="([^"]*)"', m.group(1))
        inner = m.group(2)
        # h1 内的 span：短标签、或以 ──/—— 开头的副题 -> span.subtitle；其余拆掉
        def sp(sm):
            t = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
            if len(t) <= 6 or t.startswith(("──", "——")):
                ctx["subtitle"] += 1
                return '<span class="subtitle">%s</span>' % sm.group(1)
            return sm.group(1)
        inner = re.sub(r'<span class="[^"]*">(.*?)</span>', sp, inner, flags=re.S)
        return "<h1%s>%s</h1>" % ((' id="%s"' % idm.group(1)) if idm else "", inner.strip())
    c = re.sub(r'<h1\b([^>]*\bff_serif[^>]*)>(.*?)</h1>', repl, c, flags=re.S)
    c = re.sub(r'<p class="' + CONFIG["h3_re"] + r'">(.*?)</p>',
               lambda m: "<h3>%s</h3>" % m.group(1).strip(), c, flags=re.S)
    ctx["heads"] = len(re.findall(r"<h[1-3][ >]", c))
    return c

def step_footnotes(c, name, ctx):
    # 1) 正文 ref
    order, seq = [], {}
    ref = re.compile(r'<span class="ff_sans fz_0-6em va_super">\s*<span>\s*'
                     r'<a\b([^>]*\bid="footnote-(\d+)-backlink"[^>]*)>(.*?)</a>\s*</span>\s*</span>', re.S)
    def rr(m):
        n = m.group(2)
        if n not in seq:
            order.append(n); seq[n] = len(order)
        k = seq[n]
        ctx["notes"] += 1
        return '<sup><a epub:type="noteref" href="#foot-%d" id="back-%d">[%d]</a></sup>' % (k, k, k)
    c = ref.sub(rr, c)
    # 2) 收集全篇 <li id="footnote-NNN"> 注文（可能分布在多个 section 里）
    notes = []
    def li(m):
        n = m.group(1)
        k = seq.get(n)
        if k is None:
            ctx["orphan"] += 1
            return ""
        body = re.sub(r'<a\b[^>]*class="_idFootnoteAnchor"[^>]*>.*?</a>', "", m.group(2), flags=re.S)
        body = re.sub(r'^\s*<p\b[^>]*>(.*?)</p>\s*$', r'\1', body, flags=re.S)
        return '<p class="fnote" id="foot-%d"><a href="#back-%d">[%d]</a> %s</p>' % (
            k, k, k, flat(body).lstrip("：: "))
    c = re.sub(r'<li id="footnote-(\d+)"[^>]*class="_idFootnote"[^>]*>(.*?)</li>', li, c, flags=re.S)
    notes = re.findall(r'<p class="fnote" id="foot-\d+">.*?</p>', c, re.S)
    if notes:
        # 收掉所有 <hr class="HorizontalRule-1"/> 与 section/ol 壳，末尾统一 <hr/> + 注
        c = re.sub(r'(?s)[ \t]*<hr\b[^>]*HorizontalRule[^>]*/>[ \t]*\n?', "", c)
        c = re.sub(r'(?s)[ \t]*<section class="_idFootnotes".*?</section>[ \t]*\n?', "", c)
        c = re.sub(r'(?s)[ \t]*<ol class="_idFootAndEndNoteOLAttrs"[^>]*>\s*</ol>[ \t]*\n?', "", c)
        for nt in notes:
            c = c.replace(nt, "")
        ctx["fnote_out"] = notes
    return c

def step_append(c, name, ctx):
    notes = ctx.get("fnote_out") or []
    if not notes:
        return c
    block = "<hr/>\n" + "\n".join(notes) + "\n"
    return c.replace("</body>", block + "</body>")

def step_quotes(c, name, ctx):
    pat = re.compile(r'<p class="' + CONFIG["quote_re"] + r'">(.*?)</p>', re.S)
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
        body = "\n".join('<p class="bodytext">%s</p>' % x.group(1).strip() for x in g)
        c = c[:g[0].start()] + "<blockquote>\n" + body + "\n</blockquote>" + c[g[-1].end():]
        ctx["quotes"] += len(g)
    return c

def step_paras(c, name, ctx):
    def sw(cls_re, out):
        def repl(m):
            ctx["paras"] += 1
            return '<p class="%s">%s</p>' % (out, m.group(1).strip())
        return re.sub(r'<p class="(?:%s)"[^>]*>(.*?)</p>' % cls_re, repl, c, flags=re.S)
    # 空行段（仅全角空格）-> bodytext + br，连续折叠为一个
    c = re.sub(r'<p class="[^"]*">[\u3000\s]*</p>', '<p class="bodytext\"><br/></p>', c)
    c = re.sub(r'(?:<p class="bodytext"><br/></p>\s*){2,}', '<p class="bodytext"><br/></p>\n', c)
    # 章首作者：紧跟 </h1> 的 ff_sans fz_0-8em
    def author(m):
        if c[:m.start()].rstrip().endswith("</h1>"):
            ctx["author"] += 1
            return '<p class="author">%s</p>' % m.group(1).strip()
        return '<p class="bodytext-noindent">%s</p>' % m.group(1).strip()
    c = re.sub(r'<p class="' + CONFIG["author_re"] + r'">(.*?)</p>', author, c, flags=re.S)
    c = sw(CONFIG["right_re"], "right")
    c = sw(CONFIG["sprt_re"], "sprt")
    c = sw(CONFIG["bodytext_re"], "bodytext")
    c = sw(CONFIG["noindent_re"], "bodytext-noindent")
    # 兜底：剩余 p.ff_* -> bodytext（记录）
    def fb(m):
        ctx["fallback"] += 1
        ctx.setdefault("fallback_list", []).append(m.group(1))
        return '<p class="bodytext">%s</p>' % m.group(2).strip()
    c = re.sub(r'<p class="(ff_[^"]*)">(.*?)</p>', fb, c, flags=re.S)
    return c

def step_spans(c, name, ctx):
    c = re.sub(r'<span class="[^"]*\bfw_900\b[^"]*\bfs_italic\b[^"]*">(.*?)</span>',
               lambda m: "<b><i>%s</i></b>" % m.group(1), c, flags=re.S)
    c = re.sub(r'<span class="[^"]*\bfs_italic\b[^"]*\bfw_900\b[^"]*">(.*?)</span>',
               lambda m: "<b><i>%s</i></b>" % m.group(1), c, flags=re.S)
    c = re.sub(r'<span class="[^"]*\bfw_900\b[^"]*">(.*?)</span>',
               lambda m: "<b>%s</b>" % m.group(1), c, flags=re.S)
    c = re.sub(r'<span class="[^"]*\bfs_italic\b[^"]*">(.*?)</span>',
               lambda m: "<i>%s</i>" % m.group(1), c, flags=re.S)
    c = re.sub(r'<span class="[^"]*\bff_cursive\b[^"]*">(.*?)</span>',
               lambda m: '<span class="kai">%s</span>' % m.group(1), c, flags=re.S)
    ctx["span_left"] += len(re.findall(r'<span class="[^"]*">', c))
    c = re.sub(r'<span class="(?!(?:kai|italic|bold|small|subtitle|lefttitle|jiazhu)\b)[^"]*">(.*?)</span>',
               lambda m: "<span>%s</span>" % m.group(1), c, flags=re.S)
    c = re.sub(r"<span></span>", "", c)
    return c

def step_figures(c, name, ctx):
    def repl(m):
        ctx["chatu"] += 1
        src = re.search(r'src="([^"]*)"', m.group(1))
        return '<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>\n</div>' % (
            src.group(1) if src else "")
    return re.sub(r'<div\b[^>]*class="mg-str_10pr mg-end_10pr"[^>]*>\s*(<img[^>]*/>)\s*</div>', repl, c, flags=re.S)

def step_box(c, name, ctx):
    ctx["box"] += len(re.findall(r'<div\b[^>]*\bbox\b[^>]*>', c))
    return re.sub(r'<div\b[^>]*class="[^"]*\bbox\b[^"]*"[^>]*>', '<div class="box">', c)

def unwrap_div(c, cls_re, name, ctx):
    pat = re.compile(r'<div\b([^>]*)>')
    i = 0
    while True:
        m = pat.search(c, i)
        if not m:
            break
        attrs = m.group(1)
        if re.search(r'\bclass="', attrs):
            i = m.end(); continue
        # 无 class 的 div -> 解包
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
        i = a
    return c

def step_unwrap(c, name, ctx):
    return unwrap_div(c, None, name, ctx)

def step_body(c, name, ctx):
    ctx["body"] += len(re.findall(r'<body[^>]*\bclass="', c))
    c = re.sub(r'<body([^>]*?)\s*class="[^"]*"\s*([^>]*)>', r'<body\1\2>', c)
    return c

def step_tidy(c, name, ctx):
    c = re.sub(r"[ \t]+/>", "/>", c)
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        c = c[:hm.start()] + re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0)) + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        c = pre + body
    return c

STEPS = [("css", step_css), ("title", step_title), ("headings", step_headings),
         ("footnotes", step_footnotes), ("quotes", step_quotes), ("paras", step_paras),
         ("spans", step_spans), ("figures", step_figures), ("box", step_box),
         ("unwrap", step_unwrap), ("body", step_body), ("tidy", step_tidy),
         ("append", step_append)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    for pat, msg in [
        (r'class="(?:ff_|fz_|ti_|ta_|mg-str|fw_|fs_|va_super)', "残留源 class"),
        (r'_idFootnoteLink|_idFootnoteAnchor|_idFootnotes|HorizontalRule', "残留脚注结构"),
        (r'id="footnote-', "残留 footnote-NNN id"),
        (r'href="[^"]*' + CONFIG["drop_css_re"] + r'"', "残留旧 css 链接"),
    ]:
        if re.search(pat, c):
            probs.append(msg)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    refs = set(re.findall(r'epub:type="noteref" href="#(foot-\d+)"', c))
    feet = set(re.findall(r'<p class="fnote" id="(foot-\d+)"', c))
    if refs - feet:
        probs.append("有 ref 无注: %s" % sorted(refs - feet)[:3])
    if feet - refs:
        probs.append("有注无 ref: %s" % sorted(feet - refs)[:3])
    return probs

def analyze(dirpath, out=None):
    import collections
    L = ["# analyze(indesign-epub3): %s" % dirpath, ""]
    sig = collections.Counter(); feat = collections.Counter()
    for fp in list_files(dirpath):
        c = read(fp)
        for m in re.finditer(r'<(\w+)\b([^>]*)>', c):
            cm = re.search(r'class="([^"]*)"', m.group(2))
            sig['%s .%s' % (m.group(1), cm.group(1) if cm else '(#)')] += 1
        for k, pat in [("footnote-file", r'footnote-\d+-backlink'), ("endnotes", r'class="_idFootnotes"'),
                       ("hr", r'HorizontalRule'), ("chatu", r'mg-str_10pr'), ("box", r'\bbox\b')]:
            if re.search(pat, c): feat[k] += 1
    L.append("files=%d" % len(list_files(dirpath)))
    L.append("== element.class: %s" % ", ".join("%s x%d" % kv for kv in sig.most_common(25)))
    L.append("== feat: %s" % ", ".join("%s x%d" % kv for kv in feat.most_common()))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep); print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def process(dirpath, dry=False):
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml"); sys.exit(1)
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
        src_ids = set(re.findall(r'\bid="([^"]+)"', c))
        keep = {i for i in src_ids if not i.startswith(("footnote-", "_idContainer")) and "-backlink" not in i}
        ctx = dict.fromkeys(["css", "title", "heads", "notes", "orphan", "fnote_out", "quotes", "subtitle",
                             "paras", "author", "fallback", "span_left", "chatu", "box",
                             "unwrap", "body"], 0)
        ctx["fnote_out"] = []
        for s, fn in STEPS:
            c = fn(c, name, ctx)
        probs = verify_content(c, name, dirpath)
        lost = sorted(keep - set(re.findall(r'\bid="([^"]+)"', c)))
        if lost:
            probs.append("丢失源 id: %s" % lost[:5])
        if probs:
            ok = False
            print("%-22s FAIL: %s" % (name, "; ".join(probs))); continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-22s 标题=%-2d h=%-3d 脚注=%-3d 引文=%-3d 段=%-4d 作者=%-2d 兜底=%-2d chatu=%-2d box=%-2d 解包=%-2d span剩=%d" % (
            name, ctx["title"], ctx["heads"], ctx["notes"], ctx["quotes"], ctx["paras"],
            ctx["author"], ctx["fallback"], ctx["chatu"], ctx["box"], ctx["unwrap"], ctx["span_left"]))
        if ctx["fallback"]:
            print("      兜底类: %s" % dict((k, ctx["fallback_list"].count(k)) for k in set(ctx["fallback_list"])))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(dirpath):
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, dirpath)
        if probs:
            ok = False; print("%-22s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-22s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="InDesign EPUB3 源 xhtml 清洗")
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
        print("!! 目录不存在: %s" % d); sys.exit(1)
    if a.cmd == "analyze":
        analyze(d, out=getattr(a, "out", None))
    elif a.cmd == "process":
        process(d, dry=a.dry_run)
    else:
        verify_dir(d)

if __name__ == "__main__":
    main()
