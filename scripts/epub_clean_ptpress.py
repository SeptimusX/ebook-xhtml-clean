#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_ptpress.py — 人民邮电出版社 / 得到电子版（p.content 系 class）EPUB xhtml 清洗

适用特征（源文件）:
  <html xml:lang="zh-hans">、<link href="../Styles/stylesheets.css">
  <h1 class="firstTitle" id="sigil_toc_id_N"><span class="xiao">第X章</span><br/>标题</h1>
  <p class="content">正文</p>、<p class="content_100..110"> 各类特殊段
  <div class="pic"><img src="…"/><p class="imgtitle1">图注</p></div>
  <span class="kt_104">楷体强调</span>、<span class="bold">/<span class="italic">、<span class="super">
  注释: 正文 <span class="super" id="refN"><a href="#annotN">[K]</a></span>
        文末 <hr/> 后 <p class="noindent" id="annotN"><a href="#refN">[K].</a>注文</p>

映射:
  p.content                -> <p class="bodytext">
  p.content_100/101/102    -> <h3>（术语/小结、必读书目、原理名 等小节标题）
  p.content_103/107        -> <p class="right">（译者署名/日期、—— 题词落款）
                              紧随引文 blockquote 的 content_107 → 并入该 blockquote（class="intro"）
  p.content_105            -> <blockquote><p class="bodytext">（连续段合并）
                              「小结」段内 / 章末最后一条 → 普通 <p class="bodytext">
  p.content_108            -> <p class="center">（括注）
                              紧跟在 </h1> 后的一条 → 并入 h1 作第二段副标题
  p.content_110            -> <p class="bodytext-noindent">（索引条目）
  p.imgtitle/imgtitle1/imgdescript -> chatu 的 <p class="caption">（多行 <br/> 合并）
  div.pic                  -> <div class="chatu"><p class="image"><img …/></p>…
  span.kt_104/kt_106       -> <span class="kai">
  <h1 class="firstTitle">  -> 去 class，保留 id；<span class="xiao">第X章</span> -> <span class="subtitle">
  span.super（剩余，数学上标）-> <sup>
  正文注释 <span class="super" id="refN">…  -> <sup><a epub:type="noteref" href="#annotN" id="refN">[K]</a></sup>
  文末尾注 <p class="noindent" id="annotN">… -> <p class="fnote" id="annotN"><a href="#refN">[K]</a> 注文
  css 链接 -> styles.css（删除 stylesheets.css）

子命令:
  analyze <dir> [-o REPORT]   结构普查（只读）
  process <dir> [--dry-run]   执行清洗（自动备份；--dry-run 输出到临时目录）
  verify  <dir>               独立校验
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:stylesheets|stylesheet|page_styles|style\d+)\.css",
    "bodytext_from": "content",
    "h3_from": ["content_100", "content_101", "content_102"],
    "right_from": ["content_103", "content_107"],
    "quote_from": ["content_105"],
    "center_from": ["content_108"],
    "noindent_from": ["content_110"],
    "caption_from": ["imgtitle", "imgtitle1", "imgdescript"],
    "fig_div": "pic",
    "kai_spans": ["kt_104", "kt_106"],
}

def list_files(d):
    return sorted(f for f in glob.glob(os.path.join(d, "*.xhtml")) if not f.endswith(".bak"))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

# ---------- 步骤 ----------

def step_css(c, name, cfg, ctx):
    c = re.sub(r'(?s)[ \t]*<style[^>]*>.*?</style>[ \t]*\n?', "", c)   # 去内联 CSS
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + cfg["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if ('href="%s"' % cfg["css_href"]) not in c:
        c = c.replace("</head>",
                      '<link rel="stylesheet" type="text/css" href="%s"/>\n</head>' % cfg["css_href"], 1)
        ctx["css"] += 1
    return c

def step_footnotes(c, name, cfg, ctx):
    marker = re.compile(r'<span class="super" id="(ref\d+)"><a href="#(annot\d+)">(\[\d+\])</a></span>')
    def mrepl(m):
        ctx["markers"] += 1
        return '<sup><a epub:type="noteref" href="#%s" id="%s">%s</a></sup>' % (m.group(2), m.group(1), m.group(3))
    c = marker.sub(mrepl, c)
    note = re.compile(r'<p class="noindent" id="(annot\d+)"><a href="#(ref\d+)">(\[\d+\])\.?</a>\s*(.*?)</p>', re.S)
    def nrepl(m):
        ctx["fnotes"].append(m.group(1))
        return '<p class="fnote" id="%s"><a href="#%s">%s</a> %s</p>' % (m.group(1), m.group(2), m.group(3), m.group(4).strip())
    return note.sub(nrepl, c)

def step_figures(c, name, cfg, ctx):
    capcls = "|".join(re.escape(x) for x in cfg["caption_from"])
    pat = re.compile(r'<div class="%s(?:_\d+)?"[^>]*>(.*?)</div>' % cfg["fig_div"], re.S)
    def repl(m):
        block = m.group(1)
        im = re.search(r'<img[^>]*src="([^"]*)"', block)
        if not im:
            return m.group(0)
        cap = [re.sub(r"\s+", " ", x).strip()
               for x in re.findall(r'<p class="(?:%s)">(.*?)</p>' % capcls, block, re.S)]
        ctx["chatu"] += 1
        out = '<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>' % im.group(1)
        if cap:
            out += '\n<p class="caption">%s</p>' % "<br/>".join(cap)
        return out + "\n</div>"
    return pat.sub(repl, c)

def step_quotes(c, name, cfg, ctx):
    qc = "|".join(re.escape(x) for x in cfg["quote_from"])
    para = r'<p class="(?:%s)">(.*?)</p>' % qc
    run = re.compile(r'(?:%s\s*)+' % para, re.S)
    summ = c.rfind('>小结<')          # 小结段内的引文不包 blockquote
    matches = list(run.finditer(c))
    last_start = matches[-1].start() if matches else -1
    def repl(m):
        items = re.findall(para, m.group(0), re.S)
        out = "\n".join('<p class="bodytext">%s</p>' % x.strip() for x in items)
        in_summary = summ >= 0 and m.start() > summ
        # 章末最后一条 content_105（其后不再有正文段落）→ 普通正文
        at_end = m.start() == last_start and not re.search(r'<p class="content', c[m.end():])
        if in_summary or at_end:
            ctx["quotes_summary"] += len(items)
            return out
        ctx["quotes"] += len(items)
        return "<blockquote>\n" + out + "\n</blockquote>"
    return run.sub(repl, c)

def step_summary(c, name, cfg, ctx):
    """小结段内不应有 blockquote：拆掉（兼容已生成的旧输出）"""
    i = c.rfind('>小结<')
    if i < 0:
        return c
    head, tail = c[:i], c[i:]
    n = len(re.findall(r'<blockquote>', tail))
    if n:
        tail = re.sub(r'<blockquote>\s*', '', tail)
        tail = re.sub(r'\s*</blockquote>', '', tail)
    ctx["summary_unwrap"] += n
    return head + tail

def step_headings(c, name, cfg, ctx):
    hc = "|".join(re.escape(x) for x in cfg["h3_from"])
    pat = re.compile(r'<p class="(?:%s)">(.*?)</p>' % hc, re.S)
    ctx["h3"] += len(pat.findall(c))
    return pat.sub(lambda m: "<h3>%s</h3>" % m.group(1).strip(), c)

def step_right(c, name, cfg, ctx):
    rc = "|".join(re.escape(x) for x in cfg["right_from"])
    pat = re.compile(r'<p class="(?:%s)">(.*?)</p>' % rc, re.S)
    ctx["right"] += len(pat.findall(c))
    return pat.sub(lambda m: '<p class="right">%s</p>' % m.group(1).strip(), c)

def step_intro_sig(c, name, cfg, ctx):
    """引文 blockquote 后紧跟的 ——落款(right) 并进 blockquote，并把 blockquote 标为 class="intro" """
    pat = re.compile(r'(?s)<blockquote>(.*?)</blockquote>\s*<p class="right">(.*?)</p>')
    def repl(m):
        ctx["intro_sig"] += 1
        return '<blockquote class="intro">\n%s\n<p class="right">%s</p></blockquote>' % (
            m.group(1).strip(), m.group(2).strip())
    return pat.sub(repl, c)

def step_center(c, name, cfg, ctx):
    cc = "|".join(re.escape(x) for x in cfg["center_from"])
    pat = re.compile(r'<p class="(?:%s)">(.*?)</p>' % cc, re.S)
    ctx["center"] += len(pat.findall(c))
    return pat.sub(lambda m: '<p class="center">%s</p>' % m.group(1).strip(), c)

def step_noindent(c, name, cfg, ctx):
    nc = "|".join(re.escape(x) for x in cfg["noindent_from"])
    pat = re.compile(r'<p class="(?:%s)">(.*?)</p>' % nc, re.S)
    ctx["noindent"] += len(pat.findall(c))
    return pat.sub(lambda m: '<p class="bodytext-noindent">%s</p>' % m.group(1).strip(), c)

def step_bodytext(c, name, cfg, ctx):
    pat = re.compile(r'<p class="%s">' % re.escape(cfg["bodytext_from"]))
    ctx["bodytext"] += len(pat.findall(c))
    return pat.sub('<p class="bodytext">', c)

def step_kai(c, name, cfg, ctx):
    kc = "|".join(re.escape(x) for x in cfg["kai_spans"])
    pat = re.compile(r'<span class="(?:%s)">' % kc)
    ctx["kai"] += len(pat.findall(c))
    return pat.sub('<span class="kai">', c)

def step_h1(c, name, cfg, ctx):
    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        attrs = re.sub(r'\s+class="[^"]*"', "", attrs)
        inner = re.sub(r'<span class="xiao">(.*?)</span>', r'<span class="subtitle">\1</span>', inner, flags=re.S)
        if 'class="subtitle"' in inner:
            ctx["h1_sub"] += 1
        return "<h1%s>%s</h1>" % (attrs, inner.strip())
    c = re.sub(r"<h1([^>]*)>(.*?)</h1>", repl, c, flags=re.S)
    # h1 后紧跟的 <p class="center">（content_108 括注）→ 并入 h1 作第二段副标题
    def sub(m):
        ctx["h1_sub2"] += 1
        return '%s<br/><span class="subtitle">%s</span></h1>' % (m.group(1), m.group(2).strip())
    return re.sub(r'(?s)(<h1[^>]*>(?:(?!</h1>).)*)</h1>[ \t]*\n?[ \t]*<p class="center">(.*?)</p>',
                  sub, c)

def step_super(c, name, cfg, ctx):
    pat = re.compile(r'<span class="super">(.*?)</span>', re.S)
    ctx["sup"] += len(pat.findall(c))
    return pat.sub(r'<sup>\1</sup>', c)

def step_tidy(c, name, cfg, ctx):
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

STEP_ORDER = ["css", "footnotes", "figures", "quotes", "summary", "headings", "right",
              "intro_sig", "center", "noindent", "bodytext", "kai", "h1", "super", "tidy"]
BUILTIN = {"css": step_css, "footnotes": step_footnotes, "figures": step_figures,
           "quotes": step_quotes, "summary": step_summary, "headings": step_headings,
           "right": step_right, "intro_sig": step_intro_sig, "center": step_center,
           "noindent": step_noindent, "bodytext": step_bodytext, "kai": step_kai,
           "h1": step_h1, "super": step_super, "tidy": step_tidy}

# ---------- 校验 ----------

def verify_content(c, name, cfg, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], info
    resid = [cfg["bodytext_from"]] + cfg["h3_from"] + cfg["right_from"] + cfg["quote_from"] + \
            cfg["center_from"] + cfg["noindent_from"] + cfg["caption_from"] + cfg["kai_spans"]
    for cls in resid:
        if re.search(r'class="%s(?=[\s"])' % re.escape(cls), c):
            probs.append("残留 class=%s" % cls)
    if re.search(r'<div class="%s(?:_\d+)?"' % cfg["fig_div"], c):
        probs.append("残留插图 div")
    if re.search(r'class="super"', c):
        probs.append("残留 span.super")
    if re.search(r'href="[^"]*' + cfg["drop_css_re"] + r'"', c):
        probs.append("残留旧 css 链接")
    if "<style" in c:
        probs.append("残留内联 style")
    if ('href="%s"' % cfg["css_href"]) not in c and "</head>" in c:
        probs.append("缺少 css 链接")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for href in re.findall(r'href="#([^"]+)"', c):
        if href not in ids:
            probs.append("悬空链接 #%s" % href)
    for src in re.findall(r'<img[^>]*src="([^"]+)"', c):
        if not os.path.exists(os.path.normpath(os.path.join(dirpath, src))):
            probs.append("图片不存在 %s" % src)
    mk = len(re.findall(r'<sup><a epub:type="noteref"', c))
    fn = len(re.findall(r'<p class="fnote" id="annot\d+">', c))
    if mk != fn:
        probs.append("注释标记(%d) != 尾注(%d)" % (mk, fn))
    if re.search(r'</blockquote>\s*<p class="right">', c):
        probs.append("落款未并入 blockquote")
    info.append("fnote=%d chatu=%d h3=%d right=%d quote=%d" % (
        fn, c.count('class="chatu"'), len(re.findall(r"<h3", c)),
        c.count('class="right"'), len(re.findall(r"<blockquote", c))))
    return probs, info

# ---------- analyze ----------

def analyze(dirpath, out=None):
    L = []
    def w(s=""):
        L.append(s)
    files = list_files(dirpath)
    w("# analyze(ptpress/得到): %s" % dirpath)
    w("文件=%d" % len(files))
    if not files:
        return _emit(L, out)
    tot = dict(bodytext=0, h3=0, right=0, quote=0, center=0, noindent=0, cap=0, fig=0, kai=0, marker=0, fnote=0, super=0)
    def count(c, cls, exact=False):
        return len(re.findall(r'class="%s"' % re.escape(cls), c)) if exact else len(re.findall(r'class="%s(?=[\s"])' % re.escape(cls), c))
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        b = count(c, "content", exact=True)
        h3 = sum(count(c, x) for x in ("content_100", "content_101", "content_102"))
        rt = sum(count(c, x) for x in ("content_103", "content_107"))
        q = count(c, "content_105")
        ce = count(c, "content_108")
        ni = count(c, "content_110")
        cap = sum(count(c, x) for x in ("imgtitle", "imgtitle1", "imgdescript"))
        fg = len(re.findall(r'<div class="pic(?:_\d+)?"', c))
        ka = sum(count(c, x) for x in ("kt_104", "kt_106"))
        mk = len(re.findall(r'<span class="super" id="ref\d+"><a href="#annot\d+">', c))
        fn = len(re.findall(r'<p class="noindent" id="annot\d+">', c))
        su = len(re.findall(r'<span class="super">', c))
        w("%-18s body=%-4d h3=%-3d right=%-2d quote=%-3d center=%-2d noindent=%-2d cap=%-2d fig=%-2d kai=%-4d marker=%-2d fnote=%-2d super=%d %s" % (
            name, b, h3, rt, q, ce, ni, cap, fg, ka, mk, fn, su, "OK" if mk == fn else "!! marker/fnote 不等"))
        for k, v in (("bodytext", b), ("h3", h3), ("right", rt), ("quote", q), ("center", ce),
                     ("noindent", ni), ("cap", cap), ("fig", fg), ("kai", ka), ("marker", mk), ("fnote", fn), ("super", su)):
            tot[k] += v
    w("== 汇总: bodytext=%d h3=%d right=%d quote=%d center=%d noindent=%d 图注=%d 插图=%d kai=%d 标记=%d 尾注=%d super=%d" % (
        tot["bodytext"], tot["h3"], tot["right"], tot["quote"], tot["center"],
        tot["noindent"], tot["cap"], tot["fig"], tot["kai"], tot["marker"], tot["fnote"], tot["super"]))
    w("== 默认规则: content->bodytext、content_100/101/102->h3、103/107->right、105->blockquote、108->center、")
    w("   110->bodytext-noindent、imgtitle*->caption、pic->chatu、kt_104/106->kai、super(残留)->sup、注释->fnote[N]、css->styles.css")
    return _emit(L, out)

def _emit(L, out):
    rep = "\n".join(L) + "\n"
    if out:
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

# ---------- process / verify ----------

def process(dirpath, dry=False):
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml")
        sys.exit(1)
    import html as _html
    def text(c):
        c = re.sub(r'(?s)<[^>]+>', '', c)
        c = _html.unescape(c)
        return re.sub(r'\s+', '', c)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(dirpath)), stamp))
    backup_dir = os.path.join(base, "out") if dry else base
    os.makedirs(backup_dir, exist_ok=True)
    print("备份/输出目录: %s" % backup_dir)
    all_ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(backup_dir, name))
        ctx = dict(css=0, markers=0, fnotes=[], chatu=0, quotes=0, quotes_summary=0,
                   summary_unwrap=0, h3=0, right=0, intro_sig=0,
                   center=0, noindent=0, bodytext=0, kai=0, h1_sub=0, h1_sub2=0, sup=0, blank=0)
        for s in STEP_ORDER:
            c = BUILTIN[s](c, name, CONFIG, ctx)
        probs, info = verify_content(c, name, CONFIG, dirpath)
        if probs:
            all_ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(backup_dir, name) if dry else fp, c)
        print("%-18s marker=%-2d fnote=%-2d chatu=%-2d h3=%-2d right=%-2d quote=%-3d sum=%-3d introSig=%-2d h1sub2=%-2d center=%-2d noindent=%-3d body=%-4d kai=%-4d super=%-2d" % (
            name, ctx["markers"], len(ctx["fnotes"]), ctx["chatu"], ctx["h3"], ctx["right"],
            ctx["quotes"], ctx["quotes_summary"], ctx["intro_sig"] + ctx["summary_unwrap"],
            ctx["h1_sub2"], ctx["center"], ctx["noindent"], ctx["bodytext"], ctx["kai"], ctx["sup"]))
    print("RESULT:", "OK" if all_ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if all_ok else 1)

def verify_dir(dirpath):
    files = list_files(dirpath)
    allids = {os.path.basename(f): set(re.findall(r'\bid="([^"]+)"', read(f))) for f in files}
    all_ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs, info = verify_content(c, name, CONFIG, dirpath)
        for href in re.findall(r'href="([^"]+\.xhtml#[^"]+)"', c):
            fn, frag = href.split("#", 1)
            if fn in allids and frag not in allids[fn]:
                probs.append("跨文件悬空 %s" % href)
        if probs:
            all_ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-18s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)

def main():
    ap = argparse.ArgumentParser(description="人民邮电/得到 xhtml 清洗")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("analyze", "process", "verify"):
        sp = sub.add_parser(n)
        sp.add_argument("dir")
        if n == "analyze":
            sp.add_argument("-o", "--out")
        if n == "process":
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
