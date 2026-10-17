#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_zhangyue.py — 掌阅（ZHANGYUE）+ SigilFootnoteUltimate 源 xhtml 清洗

适用特征（源文件）:
  已相当语义化：正文本就是 <p class="bodytext">
  <h1 class="text-title-1-c|text-title-1-r">章</h1>
  <div class="zhangyue-c80"><h2 class="text-title-2" style="padding-left: 3.5em;text-indent: -3.5em;" id="sigil_toc_id_N">节</h2></div>
  <h3 class="text-title-3" id="sigil_toc_id_N">小节</h3>
  文件内尾注（SigilFootnoteUltimate）:
    正文 <sup class=""><a href="#note_N" id="noteref_N">N</a></sup>
    文末 [注释]: <br/>+<pre><code><b>[注释]</b></code></pre> [+ <pre><code><span class="fangsong">尾注说明：</span></code></pre>]
                <p class="bodytext"><span class=""><a href="#noteref_N" id="note_N"> N</a></span> 注文</p>
  图 <div class="zhangyue-c"><img class="zhangyue-img" src/> [图题 <p class="bodytext-no">] [图注 <p class="img-note">] [<hr/>]</div>
  内联 style（署名 text-align:right、标题 hanging indent、cover 居中）
  css 链 ../Styles/Style0001.css（@font-face 见容/仿宋）+ ../Styles/jianrong.css（掌阅排版）

映射（统一到同目录 styles.css）:
  css -> styles.css；span.fangsong -> span.kai
  <br/>+<pre>[注释]</pre> -> <hr/> + <h2>注释</h2>
  <pre><code>尾注说明：</code></pre> -> <p class="sprt">尾注说明：</p>
  尾注 ref -> <sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>
  尾注注文 -> <p class="fnote" id="foot-K"><a href="#back-K">[K]</a> 注文</p>（每文件从 1 重排，阿拉伯）
  <h1 class="text-title-1-*"> -> <h1>；div.zhangyue-c80 解包 + h2.text-title-2 -> <h2 id>；h3.text-title-3 -> <h3 id>
  div.zhangyue-c -> <div class="chatu">（img -> <p class="image"><img/></p>；图题/图注 -> <p class="caption">，保留原序；块内 <hr/> 删除）
  style text-align:right -> class="right"；text-align:center -> class="center"；其余 style 丢弃
  p.bodytext-no（图块外）-> p.bodytext-noindent；cover 的居中 div -> <div class="center">（SVG 保留）

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import strip_sprt_between_chatu

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:Style\d+\.css|jianrong\.css|stylesheet\.css|page_styles\.css|style\d+\.css)",
    "foot_h2": "注释",
}

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

def flat(s):
    """折叠空白、去首尾，剥掉源 class（保留行内 span）"""
    s = re.sub(r"\s+class=\"(?:zhangyue|text-title|fangsong|bodytext-no)[^\"]*\"", "", s)
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

def step_spans(c, name, ctx):
    ctx["fangsong"] += len(re.findall(r'<span class="fangsong"', c))
    c = re.sub(r'<span class="fangsong"([^>]*)>', r'<span class="kai">', c)
    return c

def step_noteheads(c, name, ctx):
    # [注释] 段标题：<br/>* + <pre><code><b …>[注释]</b></code></pre> -> <hr/> + <h2>注释</h2>
    c, n1 = re.subn(r'(?:\s*<br/>)+\s*<pre><code>[^<]*<b[^>]*>\[注释\]</b></code></pre>\s*',
                    "<hr/>\n<h2>%s</h2>\n" % CONFIG["foot_h2"], c)
    ctx["foothead"] += n1
    # 「尾注说明：」pre -> <p class="sprt">
    c, n2 = re.subn(r'<pre><code>(.*?)</code></pre>',
                    lambda m: '<p class="sprt">%s</p>' % flat(m.group(1)), c, flags=re.S)
    ctx["foothead"] += n2
    return c

def step_footnotes(c, name, ctx):
    order, seq = [], {}
    ref = re.compile(r'<sup class=""><a href="#note_(\d+)" id="noteref_(\d+)">(\d+)</a></sup>')
    def rr(m):
        n = m.group(1)
        if n not in seq:
            order.append(n)
            seq[n] = len(order)
        k = seq[n]
        return '<sup><a epub:type="noteref" href="#foot-%d" id="back-%d">[%d]</a></sup>' % (k, k, k)
    c, nr = ref.subn(rr, c)
    ctx["notes"] += nr
    note = re.compile(r'<p class="bodytext"><span class=""><a href="#noteref_(\d+)" id="note_(\d+)">\s*(\d+)</a></span>\s*(.*?)</p>', re.S)
    def rn(m):
        k = seq.get(m.group(1))
        if k is None:
            ctx["orphan"] += 1
            return m.group(0)
        return '<p class="fnote" id="foot-%d"><a href="#back-%d">[%d]</a> %s</p>' % (k, k, k, flat(m.group(4)))
    c, nn = note.subn(rn, c)
    ctx["notes"] += nn
    return c

def step_figures(c, name, ctx):
    def inner(s):
        s = re.sub(r'<img\b[^>]*?src="([^"]*)"[^>]*/>',
                   lambda m: '<p class="image"><img src="%s" alt=""/></p>' % m.group(1), s)
        s = re.sub(r'<p class="bodytext-no"[^>]*>(.*?)</p>',
                   lambda m: '<p class="caption">%s</p>' % m.group(1).strip(), s, flags=re.S)
        s = re.sub(r'<p class="img-note"[^>]*>(.*?)</p>',
                   lambda m: '<p class="caption">%s</p>' % m.group(1).strip(), s, flags=re.S)
        s = re.sub(r'[ \t]*<hr/>[ \t]*\n?', "", s)
        return "\n".join(x for x in (y.strip() for y in s.split("\n")) if x)
    def repl(m):
        ctx["chatu"] += 1
        return '<div class="chatu">\n%s\n</div>' % inner(m.group(1))
    c = re.sub(r'<div class="zhangyue-c">(.*?)</div>', repl, c, flags=re.S)
    return c

def step_ns(c, name, ctx):
    # <sup><a epub:type="noteref"> 需要声明 epub 命名空间（源 <html> 未声明）
    if "epub:type=" in c and "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>", r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
        ctx["ns"] += 1
    return c

def unwrap_div(c, cls, name, ctx):
    """深度计数解包 <div class="cls">…</div>（可处理同名嵌套）"""
    pat = re.compile(r'<div\b[^>]*\bclass="%s"[^>]*>' % re.escape(cls))
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
    return unwrap_div(c, "zhangyue-c80", name, ctx)

def _head_repl(tag):
    def repl(m):
        idm = re.search(r'\bid="([^"]*)"', m.group(1))
        return '<%s%s>%s</%s>' % (tag, (' id="%s"' % idm.group(1)) if idm else "", m.group(2).strip(), tag)
    return repl

def step_headings(c, name, ctx):
    # 属性顺序无关：attr 里含 class 即可，id 原样保留（ncx 要用）
    c = re.sub(r'<h1\b([^>]*\bclass="text-title-1-[rc]"[^>]*)>(.*?)</h1>', _head_repl("h1"), c, flags=re.S)
    c = re.sub(r'<h2\b([^>]*\bclass="text-title-2"[^>]*)>(.*?)</h2>', _head_repl("h2"), c, flags=re.S)
    c = re.sub(r'<h3\b([^>]*\bclass="text-title-3"[^>]*)>(.*?)</h3>', _head_repl("h3"), c, flags=re.S)
    c = re.sub(r'<h4\b([^>]*\bclass="text-title-4"[^>]*)>(.*?)</h4>', _head_repl("h4"), c, flags=re.S)
    # 兜底：其余 text-title-*
    c = re.sub(r'<h([1-6])\b([^>]*\bclass="text-title-[^"]*"[^>]*)>(.*?)</h\1>',
               lambda m: "<h%s%s>%s</h%s>" % (m.group(1),
                                              (' id="%s"' % re.search(r'\bid="([^"]*)"', m.group(2)).group(1))
                                              if re.search(r'\bid="([^"]*)"', m.group(2)) else "",
                                              m.group(3).strip(), m.group(1)), c, flags=re.S)
    ctx["heads"] = len(re.findall(r"<h[123][ >]", c))
    return c

def step_styles(c, name, ctx):
    # 内联 style：right/center 映射到 class，其余丢弃
    def repl(m):
        tag, attrs, style = m.group(1), m.group(2), m.group(3)
        ctx["style"] += 1
        if "text-align" in style and "right" in style:
            cls = "right"
        elif "text-align" in style and "center" in style:
            cls = "center"
        else:
            cls = None
        rest = re.sub(r'\s*class="[^"]*"', "", attrs).strip()
        attr = (" " + rest if rest else "") + (' class="%s"' % cls if cls else "")
        return "<%s%s>" % (tag, attr)
    c = re.sub(r'<(\w+)([^>]*?)\s+style="([^"]*)"([^>]*)>', repl, c)
    # 图块外的 p.bodytext-no -> bodytext-noindent
    ctx["bno"] += len(re.findall(r'<p class="bodytext-no"', c))
    c = re.sub(r'<p class="bodytext-no">', '<p class="bodytext-noindent">', c)
    return c

def step_tidy(c, name, ctx):
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        head = re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0))
        c = c[:hm.start()] + head + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        c = pre + body
    return c

STEPS = [("css", step_css), ("spans", step_spans), ("noteheads", step_noteheads),
         ("footnotes", step_footnotes), ("ns", step_ns), ("figures", step_figures),
         ("headings", step_headings), ("unwrap", step_unwrap), ("styles", step_styles),
         ("tidy", step_tidy)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    for pat, msg in [
        (r'class="(?:text-title|zhangyue)', "残留源 class"),
        (r'class="bodytext-no"', "残留 p.bodytext-no"),
        (r'class="(?:fangsong|img-note)"', "残留源 span/p class"),
        (r'\sstyle="', "残留内联 style"),
        (r'\sclass=""', "空 class"),
        (r'id="(?:noteref|note)_', "残留 Sigil 脚注 id"),
        (r'href="[^"]*' + CONFIG["drop_css_re"] + r'"', "残留旧 css 链接"),
        (r'<pre>|<code>', "残留 pre/code"),
        (r'\[注释\]', "残留 [注释] 文本"),
    ]:
        if re.search(pat, c):
            probs.append(msg)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    # ref <-> note 配对
    refs = set(re.findall(r'epub:type="noteref" href="#(foot-\d+)"', c))
    feet = set(re.findall(r'<p class="fnote" id="(foot-\d+)"', c))
    if refs - feet:
        probs.append("有 ref 无对应注: %s" % sorted(refs - feet)[:3])
    if feet - refs:
        probs.append("有注无对应 ref: %s" % sorted(feet - refs)[:3])
    return probs

def analyze(dirpath, out=None):
    import collections
    L = ["# analyze(zhangyue): %s" % dirpath, ""]
    files = list_files(dirpath)
    sig = collections.Counter(); feat = collections.Counter()
    for fp in files:
        c = read(fp)
        for m in re.finditer(r'<(\w+)\b([^>]*)>', c):
            cm = re.search(r'class="([^"]*)"', m.group(2))
            sig['%s .%s' % (m.group(1), cm.group(1) if cm else '(#)')] += 1
        if 'id="noteref_' in c: feat['footnote-file'] += 1
        if '<pre>' in c: feat['pre/注释段'] += 1
        if 'zhangyue-img' in c: feat['figure-file'] += 1
        if 'style="' in c: feat['inline-style'] += 1
    L.append("files=%d" % len(files))
    L.append("== element.class: %s" % ", ".join("%s x%d" % kv for kv in sig.most_common(25)))
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
        ctx = dict.fromkeys(["css", "fangsong", "foothead", "notes", "chatu", "heads",
                             "style", "bno", "orphan", "ns", "unwrap"], 0)
        src_ids = set(re.findall(r'\bid="([^"]+)"', c))
        keep_ids = {i for i in src_ids if not i.startswith(("noteref_", "note_"))}
        for s, fn in STEPS:
            c = fn(c, name, ctx)
        c = strip_sprt_between_chatu(c)
        probs = verify_content(c, name, dirpath)
        lost = sorted(keep_ids - set(re.findall(r'\bid="([^"]+)"', c)))
        if lost:
            probs.append("丢失源 id: %s" % lost[:5])
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-20s fangsong=%-2d 注释头=%-2d 脚注=%-3d chatu=%-2d 标题=%-2d style=%-2d bno=%-2d" % (
            name, ctx["fangsong"], ctx["foothead"], ctx["notes"], ctx["chatu"], ctx["heads"],
            ctx["style"], ctx["bno"]))
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
    ap = argparse.ArgumentParser(description="掌阅源 xhtml 清洗")
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
