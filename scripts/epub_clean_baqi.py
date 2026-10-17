#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_baqi.py — 八旗文化（繁中 InDesign 导出）xhtml 清洗

适用特征（源文件）:
  <html xmlns="…" xmlns:epub="…">（无 lang）、<link href="../Styles/Style.css"/>
  标题（title 属性重复全文；章号/副题是 display:block 的 span）:
    <h1 title="第一章 機械人與女巫──塔羅斯與美蒂亞">
      <span class="num">第一章</span>機械人與女巫<span class="num2">──塔羅斯與美蒂亞</span></h1>
    <h2 title="推薦序：…"><span class="num">推薦序</span>希臘神話的科技工藝想像</h2>
    <h3 class="h3 sigil_not_in_toc">節</h3>
  正文 <p>（**无 class**）；<p class="author">；<p class="noindent"><span class="kai">題詞</span></p>
  引文 <p class="kai">（楷体、藍色）
  分隔 <p class="sec">* * *</p>
  图 <div class="pic|pic-c"><img/><span class="caption">图说</span></div>（caption 是 span）
  脚注（章末 <ol>，带 border-top）:
    正文 <a class="footnote" href="#fnX-1" id="fX-1">[1]</a>
    章末 <ol class="footnote"><li id="fnX-1">注文<a href="#fX-1"><img class="pw" alt="back" src="../Images/back.png"/></a></li>…</ol>
    （`img.pw` 只是回链箭头，不是生僻字图）
  其它：<p class="ref">（參考書目，悬挂缩进）、<p class="title">+<p class="item">（名詞釋義）、
       <div class="boxend">（灰底专栏）、<div class="main">+<span class="book-title-main/original">（版權頁）
       <p><br/></p> 空段、<a id="section_N"> / <a id="_idTextAnchorNNN"> 空锚点

映射:
  css    -> styles.css
  标题   span.num -> <br/><span class="subtitle">；span.num2 -> <br/><span class="subtitle">；
         h3 只保留 sigil_not_in_toc 标记
  正文   <p> -> <p class="bodytext">
  kai    -> <blockquote>（连续段合并，块内 <p class="bodytext">）
  sec    -> <p class="sprt">
  图     -> <div class="chatu"><p class="image"><img/></p><p class="caption">…</p></div>
  脚注   ref -> <sup><a epub:type="noteref" href="#fnX-N" id="fX-N">[N]</a></sup>
         <ol.footnote> -> <hr/> + <p class="fnote" id="fnX-N"><a href="#fX-N">[N]</a> 注文</p>
  ref/item/title(名詞釋義) -> p.bodytext-noindent；author 保留；center 保留
  noindent -> p.bodytext-noindent
  div.boxend / div.main 解包；span.book-title-* 去标签
  <p><br/></p> -> 删除

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:Style|stylesheet|style|Copyright)\.css",
    "bodytext_class": "bodytext",
    "noindent_class": "bodytext-noindent",
    "sprt_class": "sprt",
}

# ---------- 基础 ----------

def list_files(d):
    files = []
    for pat in ("*.xhtml", "*.html"):
        files += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    def key(p):
        m = re.search(r"(\d+)", os.path.basename(p))
        return (0, int(m.group(1))) if m else (1, os.path.basename(p))
    return sorted(set(files), key=key)

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def _ens_epub(c):
    if "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>", r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
    return c

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c, n = re.subn(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    ctx["css"] += n
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c

FIG_RE = re.compile(r'<div class="pic(?:-c)?">\s*(<img[^>]*/>)\s*'
                    r'(?:<span class="caption">(.*?)</span>\s*)?</div>', re.S)

def step_figures(c, name, ctx):
    def repl(m):
        img, cap = m.group(1), m.group(2)
        src = re.search(r'src="([^"]*)"', img)
        alt = re.search(r'alt="([^"]*)"', img)
        ctx["chatu"] += 1
        out = '<div class="chatu">\n<p class="image"><img src="%s" alt="%s"/></p>\n' % (
            src.group(1) if src else "", alt.group(1) if alt else "")
        if cap:
            out += '<p class="caption">%s</p>\n' % cap.strip()
        return out + "</div>"
    return FIG_RE.sub(repl, c)

REF_RE = re.compile(r'<a class="footnote" href="#(fnX-\d+)" id="(fX-\d+)">\[(\d+)\]</a>')
OL_RE = re.compile(r'<ol class="footnote">(.*?)</ol>', re.S)
LI_RE = re.compile(r'<li id="(fnX-\d+)">(.*?)</li>', re.S)
BACK_RE = re.compile(r'<a href="#fX-\d+"><img class="pw"[^>]*/></a>\s*$')

def step_footnotes(c, name, ctx):
    if not REF_RE.search(c) and not OL_RE.search(c):
        return c
    c = _ens_epub(c)

    def rr(m):
        ctx["refs"] += 1
        return '<sup><a epub:type="noteref" href="#%s" id="%s">[%s]</a></sup>' % (
            m.group(1), m.group(2), m.group(3))
    c = REF_RE.sub(rr, c)

    def ol_repl(m):
        items = LI_RE.findall(m.group(1))
        lines = []
        for note_id, body in items:
            num = note_id.rsplit("-", 1)[-1]
            body = BACK_RE.sub("", body).strip()
            lines.append('<p class="fnote" id="%s"><a href="#fX-%s">[%s]</a> %s</p>' % (
                note_id, num, num, body))
            ctx["fnotes"] += 1
        return "<hr/>\n" + "\n".join(lines)
    c = OL_RE.sub(ol_repl, c)
    return c

KAI_RE = re.compile(r'<p class="kai">(.*?)</p>', re.S)
DKAI_RE = re.compile(r'<div class="kai">(.*?)</div>', re.S)

def step_quotes(c, name, ctx):
    body_start = c.find("<body")

    # 整块引文 <div class="kai">（内含多个 <p>，可能带 p.author 落款）
    def dk(m):
        before = c[body_start:m.start()] if body_start >= 0 else ""
        is_intro = "<p" not in before
        inner = re.sub(r"<p>", '<p class="%s">' % CONFIG["bodytext_class"], m.group(1))
        ctx["bq"] += 1
        return "<blockquote%s>\n%s\n</blockquote>" % (' class="intro"' if is_intro else "", inner.strip())
    c = DKAI_RE.sub(dk, c)

    ms = list(KAI_RE.finditer(c))
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
        block = "<blockquote>\n" + "\n".join(
            '<p class="%s">%s</p>' % (CONFIG["bodytext_class"], m.group(1).strip()) for m in g
        ) + "\n</blockquote>"
        c = c[:g[0].start()] + block + c[g[-1].end():]
        ctx["bq"] += len(g)
    return c

HEAD_NUM_RE = re.compile(r'<span class="num">(.*?)</span>')
HEAD_NUM2_RE = re.compile(r'<span class="num2">(.*?)</span>')

def step_headings(c, name, ctx):
    # 章号 / 副题（源 CSS 为 display:block）-> 独立行 + span.subtitle
    def repl(m):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        inner = HEAD_NUM_RE.sub(lambda x: '<span class="subtitle">%s</span><br/>' % x.group(1), inner)
        inner = HEAD_NUM2_RE.sub(lambda x: '<br/><span class="subtitle">%s</span>' % x.group(1), inner)
        ctx["heads"] += 1
        return "<%s%s>%s</%s>" % (tag, attrs, inner, tag)
    c = re.sub(r"<(h[12])([^>]*)>(.*?)</\1>", repl, c, flags=re.S)

    # h3：只去掉多余的 "h3" 类，保留 sigil_not_in_toc 标记
    def h3repl(m):
        attrs = re.sub(r'\s+class="h3 sigil_not_in_toc"', ' class="sigil_not_in_toc"', m.group(0))
        ctx["heads"] += 1
        return attrs
    c = re.sub(r"<h3[^>]*>", h3repl, c)
    return c

def step_misc(c, name, ctx):
    # 版權頁：<html class="vrtl"> 直排标记
    c, n0 = re.subn(r'(<html\b[^>]*?)\s+class="vrtl"', r"\1", c)
    ctx["unwrap"] += n0
    # 分隔符
    c, n = re.subn(r'<p class="sec">', '<p class="%s">' % CONFIG["sprt_class"], c)
    ctx["sprt"] += n
    # 悬挂缩进类：參考書目 / 名詞釋義
    for cls in ["ref", "item", "title"]:
        c, n = re.subn(r'<p class="%s">' % cls, '<p class="%s">' % CONFIG["noindent_class"], c)
        ctx["noindent"] += n
    c, n = re.subn(r'<p class="noindent">', '<p class="%s">' % CONFIG["noindent_class"], c)
    ctx["noindent"] += n
    # vrtl（版權頁直排標記）
    c, n = re.subn(r'<p class="vrtl">', "<p>", c)
    return c

def step_unwrap(c, name, ctx):
    # div.boxend / div.main 解包
    for cls in ["boxend", "main"]:
        while True:
            m = re.search(r'<div class="%s">' % cls, c)
            if not m:
                break
            depth, i = 0, m.end()
            while i < len(c):
                if c.startswith("<div", i):
                    depth += 1
                    i += 4
                elif c.startswith("</div>", i):
                    if depth == 0:
                        break
                    depth -= 1
                    i += 6
                else:
                    i += 1
            if i >= len(c):
                break
            c = c[:m.start()] + c[m.end():i] + c[i + 6:]
            ctx["unwrap"] += 1
    # 版權頁书名 span
    for cls in ["book-title-main", "book-title-original"]:
        pat = re.compile(r'<span class="%s">((?:(?!<span).)*?)</span>' % cls, re.S)
        while True:
            c, k = pat.subn(r"\1", c)
            ctx["unwrap"] += k
            if not k:
                break
    return c

def step_body(c, name, ctx):
    c, n = re.subn(r"<p>", '<p class="%s">' % CONFIG["bodytext_class"], c)
    ctx["bodytext"] += n
    return c

def step_tidy(c, name, ctx):
    c, n = re.subn(r'<p class="bodytext"><br/></p>\n?', "", c)
    ctx["empty"] += n
    c, n2 = re.subn(r'<p><br/></p>\n?', "", c)
    ctx["empty"] += n2
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"\n(?:[ \t]*\n)+", "\n", body)
        c = pre + body
    return c

STEPS = [("css", step_css), ("figures", step_figures), ("footnotes", step_footnotes),
         ("quotes", step_quotes), ("headings", step_headings), ("misc", step_misc),
         ("unwrap", step_unwrap), ("body", step_body), ("tidy", step_tidy)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], []
    for pat, msg in [
        (r'<p class="(?:kai|sec|ref|item|noindent)"', "残留源 p class"),
        (r'class="(?:pic|pic-c|boxend|main|vrtl|book-title|num2?)"', "残留源 class"),
        (r'<div class="pic', "残留图 div"),
        (r"<ol class=\"footnote\"", "残留注列表"),
        (r'class="pw"', "残留回链箭头"),
        (r'href="[^"]*Styles?/', "残留旧 css 链接"),
        (r"<p><br/></p>", "残留空段"),
        (r"<p>", "残留无 class 段"),
    ]:
        if re.search(pat, c):
            probs.append(msg)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    nref = len(re.findall(r'epub:type="noteref"', c))
    nfn = len(re.findall(r'<p class="fnote"', c))
    if nref != nfn:
        probs.append("noteref(%d) != fnote(%d)" % (nref, nfn))
    info.append("bodytext=%d fnote=%d chatu=%d bq=%d" % (
        len(re.findall(r'class="bodytext"', c)), nfn,
        len(re.findall(r'<div class="chatu">', c)), len(re.findall(r"<blockquote>", c))))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = ["# analyze(baqi/繁中InDesign): %s" % d, ""]
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        hs = collections.Counter("%s.%s" % (t, cl or "-") for t, cl in
                                 re.findall(r"<(h[1-6])[^>]*class=\"([^\"]*)\"?", c))
        r = len(REF_RE.findall(c))
        f = len(LI_RE.findall(c))
        tot["ref"] += r
        tot["fn"] += f
        tot["chatu"] += len(FIG_RE.findall(c))
        L.append("%-16s 段落=%-4d 图=%-3d ref=%-3d 注=%-3d | %s" % (
            name, c.count("<p>"), len(FIG_RE.findall(c)), r, f,
            ", ".join("%s x%d" % kv for kv in hs.most_common(3))))
    L.append("")
    L.append("== 汇总: " + ", ".join("%s=%d" % kv for kv in tot.most_common()))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def process(d, dry=False):
    files = list_files(d)
    if not files:
        print("!! 未找到 *.xhtml / *.html")
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
        ctx = dict.fromkeys(["css", "chatu", "refs", "fnotes", "bq", "heads",
                             "sprt", "noindent", "unwrap", "bodytext", "empty"], 0)
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
        except Exception as e:
            ok = False
            print("%-16s FAIL: %s" % (name, e))
            continue
        probs, _ = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s bodytext=%-4d 引文=%-3d ref=%-3d 注=%-3d chatu=%-3d sprt=%-2d 标题=%-2d 解包=%-2d" % (
            name, ctx["bodytext"], ctx["bq"], ctx["refs"], ctx["fnotes"],
            ctx["chatu"], ctx["sprt"], ctx["heads"], ctx["unwrap"]))
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
    ap = argparse.ArgumentParser(description="八旗文化（繁中 InDesign）xhtml 清洗")
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
