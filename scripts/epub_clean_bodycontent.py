#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_bodycontent.py — bodyContent/文景（上海人民出版社·世纪文景）版 xhtml 清洗

适用特征（源文件）:
  <html xmlns="…" xml:lang="zh-cn">
  <link href="../Styles/stylesheet.css"/> + <link href="../Styles/stylesheet-1.css"/>
  标题（语义标签已就位，只挂 class + isbn 锚点）:
    <h1 class="chaptertitle-c" id="isbn9787208164253_1_1">第一章　死亡</h1>
    <h1 class="parttitle-c">第一部　灵魂信仰</h1>
    <h1 class="prefacetitle-c">导论 / 目　录</h1>
    <h1 class="backtitle-c">附录：北欧神话的来源</h1>
    <h3 class="txtheading-1-c">节</h3>、<h4 class="txtheading-2-c">小节</h4>
  正文 <p class="bodyContent-1">、变体 bodyContent-1-top / -top-2 / -1-c、
       noindent-copyContent-1(-top/-topbot)、hang-bodyContent-1（译名对照表逐行）
  楷体引文 <p class="bodyContent-2-kaiti"> / -kaiti-top-4 / -kaiti-top
  脚注（**跨文件**，锚点成对）:
    正文 ref   <a href="part0023.xhtml#jz_1_319" id="jzyy_1_319"><sup>(11)</sup></a>
    注文       <p class="fnContent-1"><a href="part0018.xhtml#jzyy_1_234" id="jz_1_234">(1)</a> 注文</p>
    （注文集中在少数「注释文件」里，ref 可跨文件；每章编号连续，故沿用源编号不重排）
  图 <div class="chatu_img|chatu_img-l-9|title_img"><img class="pic-img*" src/></div>
  目录 <p class="contents-1|2|3"><a href="…">…</a></p>（三级；styles.css 只有 toc1/toc2）

映射:
  css    -> styles.css（删 stylesheet.css / stylesheet-1.css）
  标题   -> 去 class、保留 h1/h3/h4 原层级与 id
  正文   -> <p class="bodytext">
  楷体   -> <blockquote>（连续段合并，块内每段 <p class="bodytext">）
  脚注   -> ref:  <sup><a epub:type="noteref" href="[file]#jz_X" id="jzyy_X">[N]</a></sup>
            注文: <p class="fnote" id="jz_X"><a href="[file]#jzyy_X">[N]</a> 注文</p>
            （保留源编号与跨文件 href；源已自带 <hr/> 分隔，不动）
  图     -> <div class="chatu"><p class="image"><img src alt/></p></div>
  目录   -> contents-1 -> p.toc1、contents-2 -> p.toc2、contents-3 删除（只留前两级）
  span.songti / span.space -> 去标签（宋体为默认）
  img 的 class/width/height   -> 只留 src/alt

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import strip_sprt_between_chatu

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:stylesheet(?:-1)?|style)\.css",
    "bodytext_class": "bodytext",
    "body_classes": [
        "bodyContent-1", "bodyContent-1-top", "bodyContent-1-top-2", "bodyContent-1-c",
        "noindent-copyContent-1", "noindent-copyContent-1-top", "noindent-copyContent-1-topbot",
        "hang-bodyContent-1",
    ],
    "quote_classes": ["bodyContent-2-kaiti", "bodyContent-2-kaiti-top-4", "bodyContent-2-kaiti-top"],
    "heading_classes": ["chaptertitle-c", "parttitle-c", "prefacetitle-c",
                        "backtitle-c", "backtitle-c-2", "txtheading-1-c", "txtheading-2-c"],
    "toc_map": {"contents-1": "toc1", "contents-2": "toc2"},
    "drop_toc": ["contents-3"],
    "unwrap_spans": ["songti", "space"],
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

FIG_RE = re.compile(r'<div class="(?:chatu_img|chatu_img-l-9|title_img)"[^>]*>\s*(<img[^>]*/>)\s*</div>', re.S)

def step_figures(c, name, ctx):
    def repl(m):
        img = m.group(1)
        src = re.search(r'src="([^"]*)"', img)
        alt = re.search(r'alt="([^"]*)"', img)
        ctx["chatu"] += 1
        return ('<div class="chatu">\n<p class="image"><img src="%s" alt="%s"/></p>\n</div>'
                % (src.group(1) if src else "", alt.group(1) if alt else ""))
    return FIG_RE.sub(repl, c)

REF_RE = re.compile(r'<a href="([^"]*)#jz_([^"#]+)" id="jzyy_([^"]+)"><sup>\((\d+)\)</sup></a>')
FN_RE = re.compile(r'<p class="fnContent-1"><a href="([^"]*)#jzyy_([^"#]+)" id="jz_([^"]+)">'
                   r'\((\d+)\)</a>\s*(.*?)</p>', re.S)

def step_footnotes(c, name, ctx):
    if not (REF_RE.search(c) or FN_RE.search(c)):
        return c
    c = _ens_epub(c)

    def rr(m):
        ctx["notes"] += 1
        return '<sup><a epub:type="noteref" href="%s#jz_%s" id="jzyy_%s">[%s]</a></sup>' % (
            m.group(1), m.group(2), m.group(3), m.group(4))
    c = REF_RE.sub(rr, c)

    def rn(m):
        ctx["fnotes"] += 1
        return '<p class="fnote" id="jz_%s"><a href="%s#jzyy_%s">[%s]</a> %s</p>' % (
            m.group(3), m.group(1), m.group(2), m.group(4), m.group(5).strip())
    c = FN_RE.sub(rn, c)
    return c

QUOTE_RE = re.compile(r'<p class="(?:%s)">(.*?)</p>' % "|".join(
    re.escape(x) for x in CONFIG["quote_classes"]), re.S)

def step_quotes(c, name, ctx):
    ms = list(QUOTE_RE.finditer(c))
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

def step_headings(c, name, ctx):
    def repl(m):
        tag, attrs = m.group(1), m.group(2)
        cm = re.search(r'\s+class="([^"]*)"', attrs)
        if not cm or cm.group(1) not in CONFIG["heading_classes"]:
            return m.group(0)
        ctx["heads"] += 1
        return "<%s%s>" % (tag, re.sub(r'\s+class="[^"]*"', "", attrs))
    return re.sub(r"<(h[1-6])([^>]*)>", repl, c)

def step_toc(c, name, ctx):
    for cls in CONFIG["drop_toc"]:
        c, n = re.subn(r'<p class="%s">.*?</p>\n?' % re.escape(cls), "", c, flags=re.S)
        ctx["tocdrop"] += n
    for src, dst in CONFIG["toc_map"].items():
        c, n = re.subn(r'<p class="%s">' % re.escape(src), '<p class="%s">' % dst, c)
        ctx["toc"] += n
    return c

def step_body(c, name, ctx):
    for cls in CONFIG["body_classes"]:
        c, n = re.subn(r'<p class="%s">' % re.escape(cls), '<p class="%s">' % CONFIG["bodytext_class"], c)
        ctx["bodytext"] += n
    return c

def step_spans(c, name, ctx):
    for cls in CONFIG["unwrap_spans"]:
        pat = re.compile(r'<span class="%s">((?:(?!<span).)*?)</span>' % re.escape(cls), re.S)
        while True:
            c, k = pat.subn(r"\1", c)
            ctx["span"] += k
            if not k:
                break
    return c

def step_imgs(c, name, ctx):
    def repl(m):
        src = re.search(r'src="([^"]*)"', m.group(0))
        alt = re.search(r'alt="([^"]*)"', m.group(0))
        ctx["img"] += 1
        return '<img src="%s" alt="%s"/>' % (src.group(1) if src else "", alt.group(1) if alt else "")
    return re.sub(r"<img\b[^>]*/>", repl, c)

def step_tidy(c, name, ctx):
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"\n(?:[ \t]*\n)+", "\n", body)
        c = pre + body
    return c

STEPS = [("css", step_css), ("figures", step_figures), ("footnotes", step_footnotes),
         ("quotes", step_quotes), ("headings", step_headings), ("toc", step_toc),
         ("body", step_body), ("spans", step_spans), ("imgs", step_imgs), ("tidy", step_tidy)]

# ---------- 校验 ----------

RESIDUAL = [
    (r'class="(?:bodyContent|fnContent|noindent-copyContent|hang-bodyContent)', "残留正文/注文源 class"),
    (r'class="(?:chaptertitle|parttitle|prefacetitle|backtitle|txtheading)', "残留标题源 class"),
    (r'class="contents-', "残留目录源 class"),
    (r'class="(?:chatu_img|title_img|pic-img)', "残留图片源 class"),
    (r"<style\b", "残留内联 <style>"),
    (r'href="[^"]*Styles?/(?:stylesheet|style)', "残留旧 css 链接"),
    (r"<sup>\(", "残留纯文本注号"),
]

def verify_content(c, name, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], []
    for pat, msg in RESIDUAL:
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
    info.append("bodytext=%d fnote=%d noteref=%d chatu=%d" % (
        len(re.findall(r'class="bodytext"', c)), len(re.findall(r'<p class="fnote"', c)),
        len(re.findall(r'epub:type="noteref"', c)), len(re.findall(r'<div class="chatu">', c))))
    return probs, info

def verify_cross(d):
    """跨文件锚点校验：每个 file#anchor 目标必须存在实体 id"""
    ids = {}
    files = list_files(d)
    for fp in files:
        ids[os.path.basename(fp)] = set(re.findall(r'\bid="([^"]+)"', read(fp)))
    probs = []
    refs = feets = 0
    for fp in files:
        c = read(fp)
        for tgt in re.findall(r'href="([^"#]*)#([^"]+)"', c):
            f = tgt[0] or os.path.basename(fp)
            if f not in ids:
                probs.append("%s: 指向不存在的文件 %s" % (os.path.basename(fp), f))
            elif tgt[1] not in ids[f]:
                probs.append("%s: 悬空锚点 %s#%s" % (os.path.basename(fp), f, tgt[1]))
        refs += len(re.findall(r'epub:type="noteref"', c))
        feets += len(re.findall(r'<p class="fnote"', c))
    if refs != feets:
        probs.append("noteref(%d) != fnote(%d)" % (refs, feets))
    return probs, refs, feets

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = ["# analyze(bodyContent/文景): %s" % d, ""]
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        h = collections.Counter("%s.%s" % (t, cl) for t, cl in
                                re.findall(r"<(h[1-6])[^>]*class=\"([^\"]*)\"", c))
        tot["ref"] += len(REF_RE.findall(c))
        tot["fn"] += len(FN_RE.findall(c))
        tot["img"] += len(FIG_RE.findall(c))
        L.append("%-16s 正文=%-4d 楷体=%-4d 注文=%-3d ref=%-3d 图=%-2d | %s" % (
            name,
            len(re.findall(r'class="(?:bodyContent-1|noindent-copyContent|hang-bodyContent)', c)),
            len(re.findall(r'class="bodyContent-2-kaiti', c)),
            len(FN_RE.findall(c)), len(REF_RE.findall(c)), len(FIG_RE.findall(c)),
            ", ".join("%s x%d" % kv for kv in h.most_common(3))))
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
        ctx = dict.fromkeys(["css", "chatu", "notes", "fnotes", "bq", "heads",
                             "toc", "tocdrop", "bodytext", "span", "img"], 0)
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
        except Exception as e:
            ok = False
            print("%-16s FAIL: %s" % (name, e))
            continue
        c = strip_sprt_between_chatu(c)
        probs, _ = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s bodytext=%-4d 引文=%-4d ref=%-3d 注文=%-3d chatu=%-2d 标题=%-3d 目录=%-2d(删%d)" % (
            name, ctx["bodytext"], ctx["bq"], ctx["notes"], ctx["fnotes"],
            ctx["chatu"], ctx["heads"], ctx["toc"], ctx["tocdrop"]))
    if ok:
        xprobs, refs, feets = verify_cross(outdir if dry else d)
        if xprobs:
            ok = False
            print("!! 跨文件校验失败:")
            for p in xprobs[:8]:
                print("   ", p)
        else:
            print("跨文件校验: OK  noteref=%d fnote=%d" % (refs, feets))
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
    xprobs, refs, feets = verify_cross(d)
    if xprobs:
        ok = False
        for p in xprobs[:8]:
            print("   ", p)
    else:
        print("跨文件校验: OK  noteref=%d fnote=%d" % (refs, feets))
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="bodyContent/文景版 xhtml 清洗")
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
