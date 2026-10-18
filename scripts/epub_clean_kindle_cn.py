#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_kindle_cn.py — Kindle-cn（亚马逊中国）+ calibre 混合源 xhtml 清洗

适用特征（源文件）:
  <html xml:lang="zh-CN">、<body class="calibre">、css 链 ../stylesheet.css + ../page_styles1.css
  <h1 class="kindle-cn-heading" id="calibre_pb_0">章</h1> / <h1 class="kindle-cn-toc-title">目錄</h1>
  <h2 class="kindle-cn-heading2"><a id="sec001" class="calibre6"></a> 第一節…</h2> / <h2 class="calibre7">…
  <h3 class="kindle-cn-heading3"> / <h4 class="kindle-cn-heading1">
  正文 <p class="calibre1"> / <p class="kindle-cn-para-2em-indent"> / <-no-indent> / <-no-indent1>
  诗句 <p class="kindle-cn-poem-left">（<br class="calibre4"/> 断行）、署名 <p class="kindle-cn-signature(1)">
  文件内尾注: 正文 <a id="chN-back" href="file#chN"><sup class="calibre5">[N]</sup></a>
              文末 <div class="empty"></div> + <p class="kindle-cn-para-no-indent">————(20×U+2014)</p>
              <p class="fnote"><a id="chN" href="file#chN-back">[N]</a> 注文</p>
  目录页 <div class="kindle-cn-toc-level(1)"><a class="calibre3" href="textNNNNN.html#secNNN">
  图片页 <div class="kindle-cn-bodycontent-div-alone"><img class="kindle-cn-bodycontent-image-alone">
  行内图 <img class="kindle-cn-inline-character|kindle-cn-inline-image" alt src>
  广告 <div class="chatu_img"><img src="../gaiword.png"/></div> + <p class="calibre8">求书文字</p>
  空 div <div class="calibre4"></div> / <div class="empty"></div>；<span class="kindle-cn-bold">

映射（统一到同目录 styles.css）:
  css -> styles.css；<body> 去 class；<html> 补 xmlns:epub
  广告块（chatu_img + gaiword + 求书 calibre8 段）整块删除
  目录 div.kindle-cn-toc-level -> div.toc1；toc-level1 -> div.toc2；a.calibre3 -> <a>
  标题去 class；h2 内嵌空锚 <a id="secNNN"> 的 id 提到 <h2 id="secNNN">
  正文 calibre1 / para-2em-indent -> bodytext；para-no-indent(1) -> bodytext-noindent
  p.kindle-cn-kai -> bodytext 内包 span.kai；署名 -> p.right
  诗句（连续 poem-left）-> <blockquote class="poem"><p class="bodytext">…</p>（末尾 <br/> 去掉）
  尾注: ref -> <sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>
        注文 -> <p class="fnote" id="foot-K"><a href="#back-K">[K]</a> 注文</p>（每文件从 1 重排）
        尾注前 div.empty + 20×— 段 -> <hr/>
  图片页 -> <div class="chatu"><p class="image"><img …/></p></div>
  行内图 -> <img src alt/>（保留；若存在 rare_map.json 则按表替换为字符）
  span.kindle-cn-bold -> <b>；br.calibre4 -> <br/>；span.calibre8 去 class（保留 lang）
  div.calibre4 / div.empty 删除；href 里 textNNNNN.html -> textNNNNN.xhtml；文件 .html -> .xhtml

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

def list_files(d):
    files = glob.glob(os.path.join(d, "*.html")) + glob.glob(os.path.join(d, "*.xhtml"))
    return sorted(set(files), key=lambda p: os.path.basename(p))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def flat(s):
    s = re.sub(r"\s+class=\"(?:calibre|kindle-cn)[^\"]*\"", "", s)
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

def step_ads(c, name, ctx):
    # 公众号广告块：<div class="chatu_img">…</div> + 紧随其后的求书段落（可能在 </body> 之后）
    def ad(m):
        ctx["ads"] += 1
        return ""
    c2 = re.sub(r'(?s)[ \t]*<div class="chatu_img"[^>]*>.*?</div>[ \t]*\n?', ad, c)
    # 其后连续以 calibre8 为 class 的求书段落
    c2, n2 = re.subn(r'(?s)(?:(?:[ \t]*<p class="calibre8"[^>]*>[^<]*</p>[ \t]*\n?))+', "", c2)
    ctx["ads"] += n2
    # 残留的 gaiword 引用（img/文字）
    c2, n3 = re.subn(r'[ \t]*<img[^>]*gaiword[^>]*/>[ \t]*\n?', "", c2)
    c2 = re.sub(r'[^\n]*gaiword[^\n]*\n?', "", c2)
    ctx["ads"] += n3
    # 空 div
    ctx["emptyd"] += len(re.findall(r'<div class="(?:calibre4|empty)"></div>', c2))
    c2 = re.sub(r'[ \t]*<div class="(?:calibre4|empty)"></div>[ \t]*\n?', "", c2)
    # 去掉 </body> 之后、</html> 之前的残留（已删干净则只剩空行）
    def tail(m):
        rest = re.sub(r"\s+", "", m.group(1))
        return "</body>" + ("\n" + m.group(1).strip() + "\n" if rest else "\n")
    c2 = re.sub(r"</body>(.*?)(?=</html>)", tail, c2, flags=re.S)
    return c2

def step_toc(c, name, ctx):
    ctx["toc"] += len(re.findall(r'class="kindle-cn-toc-level', c))
    c = re.sub(r'<div class="kindle-cn-toc-level">', '<div class="toc1">', c)
    c = re.sub(r'<div class="kindle-cn-toc-level1">', '<div class="toc2">', c)
    c = re.sub(r'<a([^>]*)class="calibre3"([^>]*)>', r'<a\1\2>', c)
    return c

def _head(tag):
    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        idm = re.search(r'\bid="([^"]*)"', attrs)
        aid = re.search(r'<a\b[^>]*\bid="([^"]*)"[^>]*>\s*</a>', inner)   # h2 内的空锚
        hid = aid.group(1) if aid else (idm.group(1) if idm else None)
        inner = re.sub(r'<a\b[^>]*>\s*</a>', "", inner).strip()
        return '<%s%s>%s</%s>' % (tag, (' id="%s"' % hid) if hid else "", inner, tag)
    return repl

def step_headings(c, name, ctx):
    c = re.sub(r'<h1\b([^>]*\bclass="kindle-cn-(?:heading|toc-title)"[^>]*)>(.*?)</h1>', _head("h1"), c, flags=re.S)
    c = re.sub(r'<h2\b([^>]*\bclass="kindle-cn-heading2"[^>]*)>(.*?)</h2>', _head("h2"), c, flags=re.S)
    c = re.sub(r'<h2\b([^>]*\bclass="calibre7"[^>]*)>(.*?)</h2>', _head("h2"), c, flags=re.S)
    c = re.sub(r'<h3\b([^>]*\bclass="kindle-cn-heading3"[^>]*)>(.*?)</h3>', _head("h3"), c, flags=re.S)
    c = re.sub(r'<h4\b([^>]*\bclass="kindle-cn-heading1"[^>]*)>(.*?)</h4>', _head("h4"), c, flags=re.S)
    ctx["heads"] = len(re.findall(r"<h[1-4][ >]", c))
    return c

def step_footnotes(c, name, ctx):
    # 尾注分隔：<div class="empty"></div> + 20×— 段 -> <hr/>
    c, ns = re.subn(r'(?s)[ \t]*<div class="empty"></div>[ \t]*\n?[ \t]*<p class="(?:kindle-cn-para-no-indent|calibre1)">\s*\u2014{6,}\s*</p>[ \t]*\n?',
                    "<hr/>\n", c)
    ctx["hr"] += ns

    def is_local(filepart):
        return filepart == "" or filepart == name or filepart[:-5] == name[:-5]

    def fixfile(filepart):
        return re.sub(r"\.html$", ".xhtml", filepart)

    # ref：<a id="chN-back" href="FILE#chN"><sup class="calibre5">[N]</sup></a>
    def ref(m):
        attrs, num = m.group(1), m.group(2)
        idm = re.search(r'\bid="ch(\d+)-back"', attrs)
        hm = re.search(r'href="([^"]*)"', attrs)
        n = idm.group(1) if idm else num
        filepart = hm.group(1).split("#")[0] if hm else ""
        href = ("#foot-%s" % n) if is_local(filepart) else (fixfile(filepart) + "#foot-" + n)
        ctx["notes"] += 1
        return '<sup><a epub:type="noteref" href="%s" id="back-%s">[%s]</a></sup>' % (href, n, n)
    c = re.sub(r'<a\b([^>]*\bid="ch\d+-back"[^>]*)>\s*<sup class="calibre5">\[(\d+)\]</sup>\s*</a>', ref, c, flags=re.S)

    # 注文：<p class="fnote"><a id="chN" href="FILE#chN-back">[N]</a> 注文</p>
    def note(m):
        attrs = m.group(1)
        idm = re.search(r'\bid="ch(\d+)"', attrs)
        hm = re.search(r'href="([^"]*)"', attrs)
        n = idm.group(1) if idm else m.group(2)
        filepart = hm.group(1).split("#")[0] if hm else ""
        href = ("#back-%s" % n) if is_local(filepart) else (fixfile(filepart) + "#back-" + n)
        return '<p class="fnote" id="foot-%s"><a href="%s">[%s]</a> %s</p>' % (n, href, n, flat(m.group(3)))
    c = re.sub(r'<p class="fnote">\s*<a\b([^>]*\bid="ch\d+"[^>]*)>\s*\[(\d+)\]\s*</a>\s*(.*?)</p>', note, c, flags=re.S)
    return c

def step_poem(c, name, ctx):
    pat = re.compile(r'<p class="kindle-cn-poem-left">(.*?)</p>', re.S)
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
        body = "\n".join('<p class="bodytext">%s</p>' % re.sub(r'<br\b[^>]*/>\s*$', "", x.group(1).strip())
                         for x in g)
        c = c[:g[0].start()] + '<blockquote class="poem">\n' + body + "\n</blockquote>" + c[g[-1].end():]
        ctx["poem"] += len(g)
    return c

def step_paras(c, name, ctx):
    def sw(cls_re, out):
        def repl(m):
            ctx["paras"] += 1
            return '<p class="%s">%s</p>' % (out, m.group(1).strip())
        return re.sub(r'<p class="(?:%s)"[^>]*>(.*?)</p>' % cls_re, repl, c, flags=re.S)
    c = sw(r"calibre1|kindle-cn-para-2em-indent", "bodytext")
    c = sw(r"kindle-cn-para-no-indent1|kindle-cn-para-no-indent", "bodytext-noindent")
    c = sw(r"kindle-cn-signature1|kindle-cn-signature", "right")
    # 楷体段
    c = re.sub(r'<p class="kindle-cn-kai"[^>]*>(.*?)</p>',
               lambda m: '<p class="bodytext"><span class="kai">%s</span></p>' % m.group(1).strip(), c, flags=re.S)
    return c

def step_figures(c, name, ctx):
    def repl(m):
        ctx["imgpage"] += 1
        attrs = m.group(2)
        src = re.search(r'src="([^"]*)"', attrs)
        alt = re.search(r'alt="([^"]*)"', attrs)
        return '<div class="chatu">\n<p class="image"><img src="%s" alt="%s"/></p>\n</div>' % (
            src.group(1) if src else "", alt.group(1) if alt else "")
    return re.sub(r'<div class="kindle-cn-bodycontent-div-alone">\s*'
                  r'(<img class="kindle-cn-bodycontent-image-alone"([^>]*)/>)\s*</div>', repl, c, flags=re.S)

def step_inline_imgs(c, name, ctx):
    rare = ctx.get("rare") or {}
    def repl(m):
        attrs = m.group(1)
        src = re.search(r'src="([^"]*)"', attrs)
        alt = re.search(r'alt="([^"]*)"', attrs)
        s = src.group(1) if src else ""
        if not s.startswith("Image"):
            return m.group(0)          # 非本书图片（如 gaiword 广告图）不动，交给 ads
        if s in rare:
            ctx["rare_hit"] += 1
            return rare[s]
        ctx["imgs"] += 1
        return '<img src="%s" alt="%s"/>' % (s, alt.group(1) if alt else "")
    return re.sub(r'<img\b([^>]*?)/>', repl, c)

def step_misc(c, name, ctx):
    c = re.sub(r'<span class="kindle-cn-bold">(.*?)</span>', r'<b>\1</b>', c, flags=re.S)
    c = re.sub(r'<br\b[^>]*class="calibre4"[^>]*/>', "<br/>", c)
    c = re.sub(r'<span class="calibre8"([^>]*)>', r'<span\1>', c)
    c = re.sub(r'<span([^>]*)class="calibre8"([^>]*)>', r'<span\1\2>', c)
    # href 里的 .html -> .xhtml
    ctx["hrefs"] += len(re.findall(r'href="[^"]*\.html', c))
    c = re.sub(r'(href="[^"#]*?)\.html', r'\1.xhtml', c)
    return c

def step_ns(c, name, ctx):
    if "epub:type=" in c and "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>", r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
        ctx["ns"] += 1
    return c

def step_body(c, name, ctx):
    ctx["body"] += len(re.findall(r'<body[^>]*\bclass="[^"]*"', c))
    c = re.sub(r'<body([^>]*?)\s*class="[^"]*"\s*([^>]*)>', r'<body\1\2>', c)
    return re.sub(r'<body\s*>', "<body>", c)

def step_tidy(c, name, ctx):
    c = re.sub(r"\s+>", ">", c)   # <a href="…" > -> <a href="…">
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

STEPS = [("css", step_css), ("toc", step_toc), ("headings", step_headings),
         ("footnotes", step_footnotes), ("poem", step_poem), ("paras", step_paras),
         ("figures", step_figures), ("inline_imgs", step_inline_imgs), ("misc", step_misc),
         ("ads", step_ads), ("body", step_body), ("ns", step_ns), ("tidy", step_tidy)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    for pat, msg in [
        (r'class="(?:calibre|kindle-cn|chatu_img|empty)', "残留源 class"),
        (r'gaiword', "残留 gaiword 广告"),
        (r'href="[^"]*\.html', "残留 .html 链接"),
        (r'id="ch\d', "残留 chN 脚注 id"),
    ]:
        if re.search(pat, c):
            probs.append(msg)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    # ref ↔ 注 配对：跨文件与源书悬空注不算错，仅在报告里提示
    refs = set(re.findall(r'epub:type="noteref" href="#(foot-\d+)"', c))
    feet = set(re.findall(r'<p class="fnote" id="(foot-\d+)"', c))
    if feet - refs:
        print("    提示 %s: 本篇有 %d 条注无本地 ref（可能是跨文件拆分）" % (name, len(feet - refs)))
    if refs - feet:
        print("    提示 %s: 本地 ref 无对应注（源书缺陷?）: %s" % (name, sorted(refs - feet)[:5]))
    return probs

def analyze(dirpath, out=None):
    import collections
    L = ["# analyze(kindle-cn): %s" % dirpath, ""]
    sig = collections.Counter(); feat = collections.Counter()
    files = list_files(dirpath)
    for fp in files:
        c = read(fp)
        for m in re.finditer(r'<(\w+)\b([^>]*)>', c):
            cm = re.search(r'class="([^"]*)"', m.group(2))
            sig['%s .%s' % (m.group(1), cm.group(1) if cm else '(#)')] += 1
        for k, pat in [("尾注 fnote", r'<p class="fnote"'), ("广告 chatu_img", r'chatu_img'),
                       ("生僻字图", r'kindle-cn-inline-character'), ("行内插图", r'kindle-cn-inline-image'),
                       ("目录", r'kindle-cn-toc-level'), ("图片页", r'bodycontent-div-alone')]:
            if re.search(pat, c): feat[k] += len(re.findall(pat, c))
    L.append("files=%d" % len(files))
    L.append("== element.class: %s" % ", ".join("%s x%d" % kv for kv in sig.most_common(30)))
    L.append("== feat: %s" % ", ".join("%s x%d" % kv for kv in feat.most_common()))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def load_rare(dirpath):
    p = os.path.join(dirpath, CONFIG["rare_map"])
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}

def process(dirpath, dry=False):
    _st = ensure_styles(dirpath)          # 先把 skill 内的 styles.css 放到目标目录
    if _st not in ("same", "copied"):
        print("styles.css: %s" % _st)
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.html/*.xhtml")
        sys.exit(1)
    rare = load_rare(dirpath)
    print("生僻字映射表: %s" % (("%d 条 %s" % (len(rare), CONFIG["rare_map"])) if rare else "无（跳过替换）"))
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
        keep = {i for i in src_ids if not re.search(r'(?:^ch\d+$|-back$|^noteref_|^note_)', i)}
        ctx = dict.fromkeys(["css", "ads", "emptyd", "toc", "heads", "hr", "notes", "orphan",
                             "poem", "paras", "imgpage", "imgs", "rare_hit", "hrefs", "ns", "body"], 0)
        ctx["rare"] = rare
        for s, fn in STEPS:
            c = fn(c, name, ctx)
        c = postprocess(c)
        probs = verify_content(c, name, dirpath)
        lost = sorted(keep - set(re.findall(r'\bid="([^"]+)"', c)))
        if lost:
            probs.append("丢失源 id: %s" % lost[:5])
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
            continue
        outp = os.path.join(outdir, name) if dry else fp
        write(outp, c)
        if not dry and name.endswith(".html"):
            newp = fp[:-5] + ".xhtml"
            if os.path.exists(newp):
                os.remove(newp)
            os.rename(fp, newp)
        print("%-24s ads=%-2d emptyd=%-2d toc=%-2d 标题=%-2d hr=%-2d 脚注=%-3d poem=%-2d 段=%-4d 图页=%-2d 行内图=%-3d rare替换=%-3d href=%d" % (
            name, ctx["ads"], ctx["emptyd"], ctx["toc"], ctx["heads"], ctx["hr"], ctx["notes"],
            ctx["poem"], ctx["paras"], ctx["imgpage"], ctx["imgs"], ctx["rare_hit"], ctx["hrefs"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(dirpath):
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, dirpath)
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-24s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="Kindle-cn 源 xhtml 清洗")
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
