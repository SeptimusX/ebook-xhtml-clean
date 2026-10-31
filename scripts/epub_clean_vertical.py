#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_vertical.py — 竖排 EPUB3（vrtl/hltr + tcy + noteref/footnote）转横排清洗

适用特征（源文件）:
  <html class="vrtl|hltr" xml:lang="zh-TW" lang="zh-TW">
  <link href="../Styles/style-standard.css"/> + style-advance.css + book-style.css
  <body class="bodymatter" epub:type="bodymatter">
  正文 <p>（无 class）、<p id="fp">
  标题 <h1 id="toc_index_N"><span class="tcy">9.</span><br/> 标题<br/> <small>副题</small></h1>
  <span class="tcy">数字</span>（縦中横，1096 处）
  题词 <p class="kfont">…</p> + <p class="kfont text-right">──落款</p>
  年表 <p class="t4 kfont"><b>秦朝</b><br/>（…年）</p>
  分隔 <p class="sep"><img src="../Images/sep.jpg"/></p>
  题图 <img src="…" class="full"/>
  尾注 <a id="fnref_N" href="#fn_N" rel="footnote" class="noteref" epub:type="noteref" role="doc-noteref">N</a>
       <div class="footnotes" epub:type="footnotes"><hr/>
         <div id="fn_N" class="footnote" epub:type="footnote" role="doc-footnote">
           <p><span class="tcy">N</span>注文&#160;<a href="#fnref_N" role="doc-backlink">↩</a></p></div>…</div>
  整页图版 <body><svg viewBox="0 0 1444 2048"><image xlink:href="../Images/NNN.jpg"/><title>图注</title></svg></body>

用户口径（2026-10-31 确认）:
  · **改成横排**：去掉 html 上的 vrtl/hltr 与 body 的 bodymatter；span.tcy 去壳留数字
  · **整页图版保留 <svg><image>**，只清掉外层多余类/属性

映射:
  css -> styles.css
  <p> -> <p class="bodytext">（保留 id）
  h1: span.tcy -> span.subtitle；<small> -> <span class="subtitle">
  kfont: 章首题词整块 -> <blockquote class="intro">（落款 p.right）；其余 -> <blockquote>
  t4 -> p.bodytext（保留 <b>）
  sep -> p.sprt
  img.full -> div.chatu
  尾注 -> 标准 <sup><a noteref>[N]</a></sup> + <hr/> + <p class="fnote" id="fn_N">…</p>
  收尾 -> postprocess()（XML 声明/NBSP/○→〇/chatu 去重/chatu 间 sprt…）

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import postprocess, ensure_styles

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:style-standard|style-advance|book-style|stylesheet|style\d*)\.css",
    "skip_files": ("cover.xhtml",),
}

# ---------- 基础 ----------

def list_files(d):
    out = []
    for pat in ("*.xhtml", "*.html"):
        out += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    def key(p):
        b = os.path.basename(p)
        m = re.match(r"bodymatter_(\d+)_(\d+)", b)
        if m:
            return (0, int(m.group(1)), int(m.group(2)))
        return (1, b)
    return sorted(set(out), key=key)

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def img_keep(img):
    src = re.search(r'src="([^"]*)"', img)
    alt = re.search(r'alt="([^"]*)"', img)
    return '<img src="%s" alt="%s"/>' % (src.group(1) if src else "", alt.group(1) if alt else "")

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c, n = re.subn(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    ctx["css"] += n
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1<link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c

def step_layout(c, name, ctx):
    # 改横排：去掉 html 的 vrtl/hltr 与 body 的 bodymatter 类
    c, n1 = re.subn(r'<html([^>]*?)\s+class="(?:vrtl|hltr)"', r"<html\1", c)
    c, n2 = re.subn(r'<body([^>]*?)\s+class="bodymatter[^"]*"', r"<body\1", c)
    c = re.sub(r'<body([^>]*?)\s+epub:type="bodymatter"', r"<body\1", c)
    ctx["layout"] += n1 + n2
    return c

def step_footnotes(c, name, ctx):
    notes = []

    def note(m):
        fid, num, text = m.group(1), m.group(2), m.group(3)
        back = re.search(r'href="#([^"]+)"', m.group(0))
        notes.append((fid, num, text, back.group(1) if back else None))
        return ""

    # 整个 footnotes 块先抽出来
    def block(m):
        inner = m.group(1)
        inner = re.sub(r"<hr\s*/?>", "", inner)
        inner = re.sub(
            r'<div id="([^"]+)" class="footnote"[^>]*>\s*<p>\s*<span class="tcy">(\d+)</span>(.*?)</p>\s*</div>',
            note, inner, flags=re.S)
        return inner
    c = re.sub(r'<div class="footnotes"[^>]*>\s*(.*?)\s*</div>\s*(?=</body>)', block, c, flags=re.S)

    if not notes:
        return c

    # 正文注号
    def ref(m):
        ctx["refs"] += 1
        fid, nid, num = m.group(1), m.group(2), m.group(3)
        return '<sup><a epub:type="noteref" href="#%s" id="%s">[%s]</a></sup>' % (nid, fid, num)
    c = re.sub(r'<a id="(fnref_\d+)" href="#(fn_\d+)"[^>]*class="[^"]*noteref[^"]*"[^>]*>(\d+)</a>', ref, c)

    lines = []
    for fid, num, text, backref in notes:
        text = re.sub(r'<a[^>]*role="doc-backlink"[^>]*>.*?</a>', "", text, flags=re.S)
        text = re.sub(r'&#160;|\u00a0', " ", text).strip()
        ctx["fnotes"] += 1
        target = backref or ("fnref_%s" % fid.split("_")[-1])
        lines.append('<p class="fnote" id="%s"><a href="#%s">[%s]</a> %s</p>' % (
            fid, target, num, text))
    return c.replace("</body>", "<hr/>\n" + "\n".join(lines) + "\n</body>")

KQ = re.compile(r'<p class="kfont( text-right)?">(.*?)</p>', re.S)

def step_quotes(c, name, ctx):
    body_start = c.find("<body")
    # 源码里已有的章首 <blockquote>（紧跟 h1）也标成 intro
    c, n0 = re.subn(r'(</h1>\s*)<blockquote>', r'\1<blockquote class="intro">', c)
    ctx["intro"] += n0
    ms = list(KQ.finditer(c))
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
        before = c[body_start:g[0].start()] if body_start >= 0 else ""
        is_intro = "<p" not in before
        parts = []
        for m in g:
            inner = m.group(2).strip()
            if m.group(1):           # text-right 落款
                parts.append('<p class="right">%s</p>' % inner)
            else:
                parts.append('<p class="bodytext">%s</p>' % inner)
        cls = ' class="intro"' if is_intro else ""
        c = c[:g[0].start()] + "<blockquote%s>\n%s\n</blockquote>" % (cls, "\n".join(parts)) + c[g[-1].end():]
        ctx["bq"] += 1
    return c

def step_headings(c, name, ctx):
    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        ctx["heads"] += 1
        inner = re.sub(r'<span class="tcy">(.*?)</span>', r'<span class="subtitle">\1</span>', inner, flags=re.S)
        inner = re.sub(r'<small>(.*?)</small>', r'<span class="subtitle">\1</span>', inner, flags=re.S)
        inner = re.sub(r"\s+", " ", inner).strip()
        return "<h1%s>%s</h1>" % (attrs, inner)
    c = re.sub(r"<h1([^>]*)>(.*?)</h1>", repl, c, flags=re.S)
    return c

def step_misc(c, name, ctx):
    # 内联 <style>（含 conmi/flex 的竖排声明）与包装 div
    c, ns = re.subn(r'[ \t]*<style\b[^>]*>.*?</style>[ \t]*\n?', "", c, flags=re.S)
    # 固定版式的 viewport 声明（转横排后必须去掉，否则阅读器仍按固定页宽排版）
    c = re.sub(r'[ \t]*<meta[^>]*name="viewport"[^>]*/>[ \t]*\n?', "", c)
    for cls in ("conmi", "flex"):
        while True:
            m = re.search(r'<div class="%s[^"]*">' % cls, c)
            if not m:
                break
            depth, i = 0, m.end()
            while i < len(c):
                if c.startswith("<div", i):
                    depth += 1; i += 4
                elif c.startswith("</div>", i):
                    if depth == 0:
                        break
                    depth -= 1; i += 6
                else:
                    i += 1
            if i >= len(c):
                break
            c = c[:m.start()] + c[m.end():i] + c[i + 6:]
    ctx["style"] = ctx.get("style", 0) + ns
    # 年表 / 说明段
    c, n1 = re.subn(r'<p class="t4[^"]*">', '<p class="bodytext">', c)
    # 分隔图
    c, n2 = re.subn(r'<p class="sep">', '<p class="sprt">', c)
    # 题图
    def full(m):
        ctx["chatu"] += 1
        return '<div class="chatu">\n<p class="image">%s</p>\n</div>' % img_keep(m.group(1))
    c, n3 = re.subn(r'<img([^>]*?class="[^"]*\bfull\b[^"]*"[^>]*?)/>', full, c)
    ctx["misc"] += n1 + n2 + n3
    return c

def step_tcy(c, name, ctx):
    # 改横排后縦中横失去意义：去壳留数字
    pat = re.compile(r'<span class="tcy">((?:(?!<span).)*?)</span>', re.S)
    while True:
        c, k = pat.subn(r"\1", c)
        ctx["tcy"] += k
        if not k:
            break
    return c

def step_body(c, name, ctx):
    c, n = re.subn(r"<p>", '<p class="bodytext">', c)
    c = re.sub(r'<p id="([^"]+)">', r'<p class="bodytext" id="\1">', c)
    ctx["bodytext"] += n
    # 仅含 svg 的整页图版：保留 svg，去掉 body 上的 epub:type 已处理；再把 svg 包进 chatu
    return c

def step_plates(c, name, ctx):
    # <body>\s*<svg ...>...</svg>\s*</body> -> 保留 svg（按要求），仅规范缩进
    if re.search(r"<body>\s*<svg\b", c):
        ctx["plate"] += 1
    return c

STEPS = [("css", step_css), ("layout", step_layout), ("footnotes", step_footnotes),
         ("quotes", step_quotes), ("headings", step_headings), ("misc", step_misc),
         ("tcy", step_tcy), ("body", step_body), ("plates", step_plates)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], []
    for pat, msg in [
        (r'class="(?:vrtl|hltr|bodymatter|tcy|kfont|sep|t4|full|conmi|flex)"', "残留旧 class"),
        (r"<style\b", "残留内联 style"),
        (r'class="footnotes?"', "残留旧脚注 class"),
        (r'class="[^"]*noteref[^"]*"', "残留旧 noteref class"),
        (r'rel="footnote"|role="doc-', "残留 role/rel"),
        (r'href="[^"]*Styles?/', "残留旧 css 链接"),
        (r"\sstyle=\"", "残留内联 style"),
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
    info.append("bodytext=%d fnote=%d chatu=%d bq=%d svg=%d" % (
        len(re.findall(r'class="bodytext"', c)), nfn,
        len(re.findall(r'<div class="chatu">', c)),
        len(re.findall(r"<blockquote", c)), c.count("<svg")))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = ["# analyze(vertical EPUB3): %s" % d, ""]
    files = [f for f in list_files(d) if os.path.basename(f) not in CONFIG["skip_files"]]
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        cl = collections.Counter(re.findall(r'class="([^"]*)"', c))
        tot["para"] += len(re.findall(r"<p[ >]", c))
        tot["tcy"] += cl.get("tcy", 0)
        tot["note"] += len(re.findall(r'class="[^"]*noteref', c))
        tot["kfont"] += cl.get("kfont", 0)
        tot["svg"] += c.count("<svg")
        L.append("%-24s 段=%-4d tcy=%-4d 注=%-3d kfont=%-2d svg=%-2d h1=%-2d | %s" % (
            name, len(re.findall(r"<p[ >]", c)), cl.get("tcy", 0),
            len(re.findall(r'class="[^"]*noteref', c)), cl.get("kfont", 0), c.count("<svg"),
            c.count("<h1"), ", ".join("%s x%d" % kv for kv in cl.most_common(3))))
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
    ensure_styles(d)
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
        if name in CONFIG["skip_files"]:
            write(os.path.join(outdir, name) if dry else fp, c)
            print("%-24s 跳过（nav/cover）" % name)
            continue
        ctx = dict.fromkeys(["css", "layout", "refs", "fnotes", "bq", "heads",
                             "misc", "tcy", "bodytext", "plate", "chatu", "intro", "style"], 0)
        if name == "nav.xhtml":
            # 目录页只做：去竖排类、去 tcy 壳、换 css（保留其 nav 结构）
            for sname in ("css", "layout", "tcy"):
                c = dict(STEPS)[sname](c, name, ctx)
            write(os.path.join(outdir, name) if dry else fp, c)
            print("%-24s nav 轻处理（去 vrtl/tcy）" % name)
            continue
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
            c = postprocess(c)
        except Exception as e:
            ok = False
            print("%-24s FAIL: %s" % (name, e))
            continue
        probs, _ = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-24s bodytext=%-4d tcy=%-4d ref=%-3d 注=%-3d 引文=%-2d 图=%-2d 图版=%d" % (
            name, ctx["bodytext"], ctx["tcy"], ctx["refs"], ctx["fnotes"],
            ctx["bq"], ctx["misc"], ctx["plate"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(d):
    ok = True
    for fp in list_files(d):
        name = os.path.basename(fp)
        if name in CONFIG["skip_files"] or name == "nav.xhtml":
            print("%-24s SKIP" % name)
            continue
        probs, info = verify_content(read(fp), name, d)
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-24s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="竖排 EPUB3 转横排清洗")
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
