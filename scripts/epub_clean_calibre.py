#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_calibre.py — calibre + 多看(duokan) 源 EPUB xhtml 清洗

适用特征（源文件）:
  <body class="calibre2">、<p class="calibre7"><span class="calibre10">正文</span></p>
  <span class="calibre23">引文/诗句</span>、<span class="calibre19/27/28"><i>书名</i></span>
  <span class="calibre17"> 加粗小标题/小节号、calibre24/29 次标题
  <div class="calibre13"><img/></div> 插图、<div class="calibre3"> 包裹层
  <aside epub:type="footnote" id="…"><ol class="duokan-footnote-content"><li …>注文</li></ol></aside>

映射（可在 CONFIG 调整）:
  calibre10 / calibre26           -> <p class="bodytext">（去 span）
  calibre23（连续整段）           -> <blockquote> + <p class="bodytext">
  紧跟插图的 calibre23（配图说明） -> 并入该 <div class="chatu"> 的 <p class="caption">
  calibre19 / 27 / 28             -> 去 span，保留 <i>
  calibre17                       -> <h3>（保留 id）
  calibre24 / 29                  -> <h4>（保留 id）
  calibre21 / 22                  -> <p class="author"> / <p class="date">
  calibre13 图 div                -> <div class="chatu"><p class="image"><img/></p>…</div>
  <h1> 包图                      -> 加 title="<title>内容"，去 class
  <h1> 文字                      -> <h1>文本</h1>（去 span/b，保留 id）
  duokan aside + noteref          -> 章末 <hr/> + <p class="fnote">，正文 [N] + 双向回链
  css 链接                        -> styles.css（删除 calibre css 链接）
  <body class="calibre2">         -> <body>
  <div class="calibre3">          -> 解包

子命令:
  analyze <dir> [-o REPORT]   结构普查（只读）
  process <dir> [--dry-run]   执行清洗（自动备份；--dry-run 输出到临时目录）
  verify  <dir>               独立校验
"""
import argparse, datetime, glob, html, json, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "body_span": ["calibre10", "calibre26"],   # 正文 span
    "quote_span": "calibre23",                 # 引文 span
    "italic_spans": ["calibre19", "calibre27", "calibre28"],
    "h3_span": "calibre17",
    "h4_spans": ["calibre24", "calibre29"],
    "author_span": "calibre21",                # 正文底部署名 -> <p class="right">
    "date_span": "calibre22",                  # 正文底部日期 -> <p class="right">
    "fig_div": "calibre13",
    "wrapper_div": "calibre3",
    "body_class": "calibre2",
    "hr": True,
    # 装饰图：小于该字节数（或列在 drop_images）的图视为装饰图；
    # 紧邻标题(h1-h4)前后 -> 整块删除；否则 -> <p class="sprt"><img/></p>
    "ornament_max_bytes": 51200,
    "drop_images": [],
}

# ---------- 基础 ----------

def list_files(d):
    return sorted(f for f in glob.glob(os.path.join(d, "*.xhtml")) if not f.endswith(".bak"))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")   # 统一 LF

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def strip_attr(tag, attr):
    """从单个标签字符串中去掉某属性"""
    return re.sub(r'\s+%s="[^"]*"' % attr, "", tag, count=1)

def img_keep_src_alt(img):
    src = re.search(r'src="([^"]*)"', img)
    alt = re.search(r'alt="([^"]*)"', img)
    return '<img src="%s" alt="%s"/>' % (src.group(1) if src else "", alt.group(1) if alt else "")

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*(?:stylesheet|page_styles)\.css"[^>]*/>[ \t]*\n?', "", c)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c

def step_body_tag(c, name, ctx):
    n = len(re.findall(r'<body class="[^"]*">', c))
    ctx["body"] += n
    return re.sub(r'<body class="[^"]*">', "<body>", c)

def step_footnotes(c, name, ctx):
    asides = []

    def aside_repl(m):
        fid, inner = m.group(1), m.group(2)
        li = re.search(r"<li[^>]*>(.*?)</li>", inner, re.S)
        text = li.group(1) if li else inner
        text = re.sub(r"</?span[^>]*>", "", text)     # 去 span，保留 <i> 等
        asides.append((fid, text.strip()))
        return ""

    c = re.sub(r'<aside epub:type="footnote" id="([^"]+)">(.*?)</aside>\n?', aside_repl, c, flags=re.S)
    pool = [{"id": a, "text": t, "used": False} for a, t in asides]

    noteref_re = re.compile(
        r'<sup[^>]*><a epub:type="noteref" href="#([^"]+)">\s*'
        r'<img[^>]*?alt="([^"]*)"[^>]*?/>\s*</a></sup>')
    used_out = {}

    def noteref_repl(m):
        fid, alt = m.group(1), m.group(2)
        au = html.unescape(alt).strip()
        cands = [a for a in pool if not a["used"] and a["id"] == fid]
        pick = next((a for a in cands if html.unescape(a["text"]).strip() == au), None)
        if pick is None and cands:
            pick = cands[0]
        if pick is None:
            raise RuntimeError("%s: noteref #%s 找不到对应 aside (alt=%s...)" % (name, fid, alt[:30]))
        pick["used"] = True
        n = len(ctx["fnotes"]) + 1
        k = used_out.get(fid, 0) + 1
        used_out[fid] = k
        oid = fid if k == 1 else "%s-%d" % (fid, k)
        ctx["fnotes"].append((n, oid, pick["text"]))
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%d]</a></sup>' % (oid, n, n)

    c = noteref_re.sub(noteref_repl, c)
    leftover = [a["id"] for a in pool if not a["used"]]
    if leftover:
        raise RuntimeError("%s: 未被引用的 aside: %s" % (name, leftover[:5]))
    return c

def step_figures(c, name, ctx):
    """插图 / 装饰图处理。

    装饰图（尺寸小于 ornament_max_bytes 或列在 drop_images）：
      紧邻标题(h1-h4)前后 -> 整块删除；否则 -> <p class="sprt"><img/></p>
    其余 -> <div class="chatu">（后随 calibre23 说明时并入 <p class="caption">）
    """
    d = ctx.get("dir", "")
    fig_re = re.compile(
        r'<div class="%s">\s*(<img[^>]*?/>)\s*</div>'
        r'(?:\s*\n\s*<p class="calibre7"><span class="%s">(.*?)</span></p>)?' % (
            CONFIG["fig_div"], CONFIG["quote_span"]), re.S)

    def is_ornament(img):
        m = re.search(r'src="[^"]*/([^/"]+)"', img)
        base = m.group(1) if m else ""
        if base in (CONFIG.get("drop_images") or []):
            return True
        sm = re.search(r'src="([^"]*)"', img)
        if not sm:
            return False
        p = os.path.normpath(os.path.join(d, sm.group(1)))
        if not os.path.exists(p):
            return False
        return os.path.getsize(p) < CONFIG.get("ornament_max_bytes", 0)

    def repl(m):
        img, cap = m.group(1), m.group(2)
        if is_ornament(img):
            adj = (bool(re.search(r"</h[1-4]>\s*(?:</div>\s*|<div[^>]*>\s*)*$", c[:m.start()]))
                   or bool(re.match(r"\s*(?:<div[^>]*>\s*)*<h[1-4][^>]*>", c[m.end():])))
            if adj:
                ctx["drop_orn"] += 1
                return ""
            ctx["sprt"] += 1
            out = '<p class="sprt">%s</p>' % img_keep_src_alt(img)
            if cap is not None:
                out += '\n<p class="caption">%s</p>' % cap
            return out
        ctx["chatu"] += 1
        out = '<div class="chatu">\n<p class="image">%s</p>\n' % img_keep_src_alt(img)
        if cap is not None:
            out += '<p class="caption">%s</p>\n' % cap
        return out + "</div>"

    c = fig_re.sub(repl, c)

    # 仅含一图的包裹 div（扉页）
    pat2 = re.compile(r'<div id="[^"]*" class="%s">\s*(<img[^>]*?/>)\s*</div>' % CONFIG["wrapper_div"], re.S)

    def repl2(m):
        img = m.group(1)
        if is_ornament(img):
            ctx["drop_orn"] += 1
            return ""
        ctx["chatu"] += 1
        return '<div class="chatu">\n<p class="image">%s</p>\n</div>' % img_keep_src_alt(img)

    c = pat2.sub(repl2, c)
    return c

def step_headings(c, name, ctx):
    h3 = re.escape(CONFIG["h3_span"])
    h4 = "|".join(re.escape(x) for x in CONFIG["h4_spans"])
    pat = re.compile(r'<p class="calibre7"><span(?: id="([^"]*)")? class="(%s|%s)">(.*?)</span></p>' % (
        h3, h4), re.S)

    def repl(m):
        sid, cls, body = m.group(1), m.group(2), m.group(3)
        body = re.sub(r"</?b>", "", body)
        tag = "h3" if cls == CONFIG["h3_span"] else "h4"
        ctx["headings"] += 1
        return "<%s%s>%s</%s>" % (tag, ' id="%s"' % sid if sid else "", body, tag)

    return pat.sub(repl, c)

def step_quotes(c, name, ctx):
    q = re.escape(CONFIG["quote_span"])
    pat = re.compile(r'<p class="calibre7"><span class="%s">(.*?)</span></p>' % q, re.S)
    ms = list(pat.finditer(c))
    if not ms:
        return c
    groups, cur = [], [ms[0]]
    for prev, m in zip(ms, ms[1:]):
        if c[prev.end():m.start()].strip() == "":
            cur.append(m)
        else:
            groups.append(cur)
            cur = [m]
    groups.append(cur)
    for g in reversed(groups):
        start, end = g[0].start(), g[-1].end()
        block = "<blockquote>\n" + "\n".join(
            '<p class="bodytext">%s</p>' % m.group(1) for m in g) + "\n</blockquote>"
        c = c[:start] + block + c[end:]
        ctx["quotes"] += len(g)
    return c

def step_bodytext(c, name, ctx):
    for cls in CONFIG["body_span"]:
        pat = re.compile(r'<p class="calibre7"><span class="%s">(.*?)</span></p>' % re.escape(cls), re.S)
        n = len(pat.findall(c))
        c = pat.sub(lambda m: '<p class="bodytext">%s</p>' % m.group(1), c)
        ctx["bodytext"] += n
    return c

def step_italic(c, name, ctx):
    alts = "|".join(re.escape(x) for x in CONFIG["italic_spans"])
    pat = re.compile(r'<span class="(?:%s)">(.*?)</span>' % alts, re.S)
    ctx["italic"] += len(pat.findall(c))
    return pat.sub(r"\1", c)

def step_author_date(c, name, ctx):
    """正文底部署名/日期 -> <p class="right">，并在正文与署名之间加一个空行段"""
    for cls in (CONFIG["author_span"], CONFIG["date_span"]):
        c = re.sub(r'<p class="calibre7"><span class="%s">(.*?)</span></p>' % re.escape(cls),
                   r'<p class="right">\1</p>', c, flags=re.S)
    i = c.find('<p class="right">')
    if i > 0:
        before = c[:i].rstrip()
        if before.endswith("</p>") and not before.endswith('<p class="bodytext"><br/></p>'):
            c = c[:i] + '<p class="bodytext"><br/></p>\n' + c[i:]
            ctx["signature"] += 1
    return c

def step_strip_spans(c, name, ctx):
    """清除残余的 calibre span（含嵌套，如引文里的 <span class="calibre10">髙</span>）"""
    pat = re.compile(r'<span(?: id="([^"]*)")? class="calibre[^"]*">((?:(?!<span).)*?)</span>', re.S)
    n = 0
    while True:
        c, k = pat.subn(
            lambda m: ('<span id="%s">%s</span>' % (m.group(1), m.group(2))) if m.group(1) else m.group(2), c)
        n += k
        if not k:
            break
    ctx["spans"] += n
    return c

def step_h1(c, name, ctx):
    title = (re.search(r"<title>(.*?)</title>", c, re.S) or [None, ""])[1].strip()
    title_attr = title.replace("&", "&amp;").replace('"', "&quot;")

    # 图片 h1：加 title 属性、去 class
    def repl_img(m):
        attrs, img = m.group(1), m.group(2)
        attrs = re.sub(r'\s+class="[^"]*"', "", attrs)
        ctx["h1_img"] += 1
        return '<h1%s title="%s">\n\t%s</h1>' % (attrs, title_attr, img_keep_src_alt(img))

    c = re.sub(r"<h1([^>]*)>\s*(<img[^>]*?/>)\s*</h1>", repl_img, c, flags=re.S)

    # 文字 h1：去 span/b、去 class，保留 id
    def repl_txt(m):
        sid, body = m.group(1), m.group(2)
        ctx["h1_txt"] += 1
        return "<h1%s>%s</h1>" % (' id="%s"' % sid if sid else "", body.strip())

    c = re.sub(r'<h1[^>]*>\s*<span(?: id="([^"]*)")? class="calibre(?:5|25)">\s*<b>(.*?)</b>\s*</span>\s*</h1>',
               repl_txt, c, flags=re.S)
    return c

def step_unwrap(c, name, ctx):
    open_re = re.compile(r'<div[^>]*\bclass="%s"[^>]*>' % re.escape(CONFIG["wrapper_div"]))
    token_re = re.compile(r"<div\b[^>]*>|</div>")
    while True:
        m = open_re.search(c)
        if not m:
            break
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = token_re.search(c, j)
            if not m2:
                raise RuntimeError("%s: div 不配对" % name)
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end()
            close = m2
        start, after = m.start(), m.end()
        if c[after:after + 1] == "\n":
            after += 1
        cs, ce = close.start(), close.end()
        if c[cs - 1:cs] == "\n" and c[ce:ce + 1] in ("", "\n"):
            cs -= 1
        c = c[:start] + c[after:cs] + c[ce:]
        ctx["unwrap"] += 1
    return c

def step_join_multiline(c, name, ctx):
    """段内断行合并：标签前的断行直接连接（脚注标记 <sup> 等），其余以空格连接"""
    def repl(m):
        open_tag, inner = m.group(1), m.group(2)
        if "\n" not in inner:
            return m.group(0)
        ctx["join"] += 1
        inner = re.sub(r"\n[ \t]*(?=<)", "", inner)
        inner = re.sub(r"\n[ \t]*", " ", inner)
        return open_tag + inner + "</p>"
    return re.sub(r"(<p\b[^>]*>)(.*?)</p>", repl, c, flags=re.S)

def step_tidy(c, name, ctx):
    """清理 head 与 body 中因删除元素产生的空行（源文件正文本身无空行）"""
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        head = re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0))
        c = c[:hm.start()] + head + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        head_part, body = c[:i], c[i:]
        n = len(re.findall(r"^[ \t]*\n", body, re.M))
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)   # 删除空行
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)  # 行首缩进
        ctx["blank"] += n
        c = head_part + body
    return c

def step_append_fnotes(c, name, ctx):
    if not ctx["fnotes"]:
        return c
    head = "<hr/>\n" if CONFIG["hr"] else ""
    block = head + "\n".join(
        '<p class="fnote" id="%s"><a href="#noteref-%d">[%d]</a> %s</p>' % (oid, n, n, txt)
        for n, oid, txt in ctx["fnotes"]) + "\n"
    return c.replace("</body>", block + "</body>")

STEPS = [("css", step_css), ("body_tag", step_body_tag), ("footnotes", step_footnotes),
         ("headings", step_headings), ("figures", step_figures), ("quotes", step_quotes),
         ("bodytext", step_bodytext), ("italic", step_italic),
         ("author_date", step_author_date), ("h1", step_h1),
         ("strip_spans", step_strip_spans), ("unwrap", step_unwrap),
         ("join", step_join_multiline), ("tidy", step_tidy), ("append", step_append_fnotes)]

# ---------- 校验 ----------

def verify_content(c, name, d):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], info
    if "<aside" in c or "duokan-footnote" in c:
        probs.append("残留 duokan 脚注")
    if "epub-footnote" in c:
        probs.append("残留脚注图标 img")
    if re.search(r'class="calibre', c):
        probs.append("残留 calibre 类")
    if re.search(r'<body[^>]*class=', c):
        probs.append("body 仍有 class")
    if re.search(r'href="[^"]*(?:stylesheet|page_styles)\.css"', c):
        probs.append("残留 calibre css 链接")
    if 'href="%s"' % CONFIG["css_href"] not in c:
        probs.append("缺少 styles.css 链接")
    if re.search(r"<span style=", c):
        probs.append("残留内联样式 span")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    for src in re.findall(r'<img[^>]*?src="([^"]+)"', c):
        if not os.path.exists(os.path.normpath(os.path.join(d, src))):
            probs.append("图片不存在 %s" % src)
    nums = [int(x) for x in re.findall(r'id="noteref-(\d+)"', c)]
    if nums != list(range(1, len(nums) + 1)):
        probs.append("noteref 编号不连续")
    fn = len(re.findall(r'<p class="fnote"', c))
    if fn != len(nums):
        probs.append("fnote(%d) != noteref(%d)" % (fn, len(nums)))
    if (fn > 0) != (len(re.findall(r"<hr/>", c)) == 1):
        probs.append("hr 与脚注列表不一致")
    info.append("chatu=%d fnote=%d h3=%d h4=%d" % (
        len(re.findall(r'<div class="chatu">', c)), fn,
        len(re.findall(r"<h3", c)), len(re.findall(r"<h4", c))))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    L = []
    def w(s=""):
        L.append(s)
    w("# analyze(calibre/duokan): %s" % d)
    files = list_files(d)
    import collections
    span = collections.Counter(); div = collections.Counter(); tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        a = len(re.findall(r'<aside epub:type="footnote"', c))
        n = len(re.findall(r'epub:type="noteref"', c))
        f = len(re.findall(r'<div class="%s">' % CONFIG["fig_div"], c))
        h1img = len(re.findall(r"<h1[^>]*>\s*<img", c, re.S))
        h1txt = len(re.findall(r"<h1[^>]*>\s*<span", c, re.S))
        sp = collections.Counter(re.findall(r'<span(?: id="[^"]*")? class="([^"]+)"', c))
        for k, v in sp.items():
            span[k] += v
        for k, v in collections.Counter(re.findall(r'<div[^>]*class="([^"]+)"', c)).items():
            div[k] += v
        tot["aside"] += a; tot["nref"] += n; tot["fig"] += f
        w("%-16s title=%-22s h1img=%d h1txt=%d aside=%-3d nref=%-3d fig=%-2d span=%s" % (
            name, (re.search(r"<title>(.*?)</title>", c, re.S) or [None, "?"])[1][:22],
            h1img, h1txt, a, n, f,
            ",".join("%s x%d" % (k, v) for k, v in sp.most_common(6))))
    w()
    w("== 汇总: files=%d aside=%d noteref=%d fig=%d" % (len(files), tot["aside"], tot["nref"], tot["fig"]))
    w("== span 类合计: %s" % ", ".join("%s x%d" % (k, v) for k, v in span.most_common()))
    w("== div 类合计: %s" % ", ".join("%s x%d" % (k, v) for k, v in div.most_common()))
    # 图片尺寸（判断装饰图）
    used = collections.Counter()
    for fp in files:
        for src in re.findall(r'<img[^>]*?src="([^"]+)"', read(fp)):
            used[src] += 1
    w("== 引用图片（尺寸小/重复多者多为装饰图 -> ornament_max_bytes / drop_images）:")
    for src, n in sorted(used.items(), key=lambda x: os.path.getsize(os.path.normpath(os.path.join(d, x[0])))
                         if os.path.exists(os.path.normpath(os.path.join(d, x[0]))) else 0):
        p = os.path.normpath(os.path.join(d, src))
        sz = os.path.getsize(p) if os.path.exists(p) else -1
        w("   x%-3d %8d  %s" % (n, sz, src))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def process(d, dry=False):
    files = list_files(d)
    if not files:
        print("!! 未找到 *.xhtml")
        sys.exit(1)
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
        ctx = {"dir": d, "body": 0, "fnotes": [], "chatu": 0, "headings": 0, "quotes": 0,
               "bodytext": 0, "italic": 0, "h1_img": 0, "h1_txt": 0, "unwrap": 0,
               "join": 0, "spans": 0, "blank": 0, "drop_orn": 0, "sprt": 0, "signature": 0}
        for sname, fn in STEPS:
            c = fn(c, name, ctx)
        probs, info = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s chatu=%-2d orn=%-2d sprt=%-2d fnote=%-3d h3=%-2d h4=%-2d quote=%-3d bodytext=%-3d italic=%-3d h1=%d/%d unwrap=%-2d join=%-2d" % (
            name, ctx["chatu"], ctx["drop_orn"], ctx["sprt"], len(ctx["fnotes"]),
            len(re.findall(r"<h3", c)), len(re.findall(r"<h4", c)),
            ctx["quotes"], ctx["bodytext"], ctx["italic"],
            ctx["h1_img"], ctx["h1_txt"], ctx["unwrap"], ctx["join"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(d):
    ok = True
    for fp in list_files(d):
        name = os.path.basename(fp)
        probs, info = verify_content(read(fp), name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-16s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="calibre+duokan 源 xhtml 清洗")
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
        analyze(d, getattr(a, "out", None))
    elif a.cmd == "process":
        process(d, dry=a.dry_run)
    else:
        verify_dir(d)

if __name__ == "__main__":
    main()
