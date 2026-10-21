#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_kindle_calibre.py — Kindle（AZW3）经 calibre 转码的源 xhtml 清洗

适用特征（源文件）:
  <body class="calibre">；<p id="fileposNNNN"> 锚点；标题/图/正文全靠组合类：
    <p class="calibre_4"><span class="calibre1"><span class="bold"><span class="calibre_5">标题</span></span></span></p>
    <p class="calibre_4"><img src="images/NNNNN.jpg" class="calibre_NN"/></p>            ← 图
    <p class="calibre_7"><span class="calibre_18">正文…</span></p>                        ← 正文（几乎无 h 标签）
    <p class="calibre_13">——作者，《书名》</p>                                           ← 引文落款
    <p class="calibre_9"><a href="file#fileposN">目录项</a></p>                           ← 书内目录
    <div class="calibre_14"> </div>（空）/ <div class="mbp_pagebreak" id="calibre_pb_N">   ← 分页符
  脚注：正文 <sup class="calibre7"><small class="calibre8"><img src="images/NNNNN.jpg" class="calibre_19"/></small></sup>
        （图标为统一的「注」圆圈图，**不含数字**；4 个文件名多为同一张图）
        另有少量文字 <sup>[N]</sup>；注文 <ol class="calibre_15|17"><li value="1" class="calibre_16">注文</li></ol>（value 恒为 1）

映射:
  css -> styles.css；<body> 去 class
  标题：每个文件第一个「带 bold 的 p.calibre_4」-> <h1>；若其后紧跟第二个较短标题且首条是章级标签
        （第N章/导言/后记/附录/参考文献/…）-> 合并为 <h1><span class="subtitle">第1章</span><br/>章名</h1>；其余 -> <h2>
  图：含 <img> 的 p.calibre_4|p.calibre_ -> <div class="chatu"><p class="image"><img/></p><p class="caption">图N …</p></div>
      （紧随的 p.calibre_7 若以「图」开头则作 caption）
  脚注：图标 sup -> <sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>（每文件=每章从 1 重排，按出现顺序）；
        文字 sup 里的纯数字保留 [N]，其余（0 / , / 、/ 。 等标点残渣）拆掉 sup 还原正文；
        注文 ol/li（value 恒为 1）全部收集，行内位置清掉，章末统一 <hr/> + <p class="fnote" id="foot-K">（1..M 重排）
  正文 p.calibre_7 -> p.bodytext；p.calibre_13 -> p.right；p.calibre_9 -> p.toc1；其余 p -> bodytext
  span.calibre_18（整段字体/缩进壳）/ calibre1/2/5/6/8 -> 解包；span.bold -> <b>；span.italic -> <i>
  div.calibre_14（空）/ div.mbp_pagebreak -> 删除
  href 里 .html -> .xhtml；文件 .html -> .xhtml；<title> 取自 h1

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

from epub_clean_common import postprocess, ensure_styles

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:stylesheet\.css|page_styles\d*\.css|style\d+\.css)",
    "chapter_re": r"^(?:第[0-9一二三四五六七八九十百]+章|导言|前言|序言|引子|后记|附录|参考文献|出版后记|索引|版权信息|图表样式说明)",
}

def list_files(d):
    files = []
    for pat in ("*.html", "*.xhtml"):
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

def text_of(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + CONFIG["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
        ctx["css"] += 1
    return c

def step_body(c, name, ctx):
    ctx["body"] += len(re.findall(r'<body[^>]*\bclass="', c))
    c = re.sub(r'<body([^>]*?)\s*class="[^"]*"\s*([^>]*)>', r'<body\1\2>', c)
    return c

def step_clean_divs(c, name, ctx):
    """先清掉空 div.calibre_14 / 分页符，否则标题之间隔着空 div，章号+章名合并不上"""
    n = len(re.findall(r'<div class="calibre_14">', c)) + len(re.findall(r'<div class="mbp_pagebreak"', c))
    c = re.sub(r'<div class="calibre_14">\s*</div>\s*', "", c)
    c = re.sub(r'<div class="mbp_pagebreak"[^>]*>\s*</div>\s*', "", c)
    c = re.sub(r'<div class="mbp_pagebreak"[^>]*/>\s*', "", c)
    ctx["kill"] += n
    return c

def step_cover(c, name, ctx):
    """calibre 封面页：内联 <style>（@page/body 居中等）-> body.cover 类"""
    if 'calibre:cover' not in c:
        return c
    n = len(re.findall(r'<style\b', c))
    c = re.sub(r'[ \t]*<style\b[^>]*>.*?</style>[ \t]*\n?', '', c, flags=re.S)
    c = re.sub(r'<body(\s[^>]*)?>',
               lambda m: '<body class="cover"%s>' % (m.group(1) or ''), c, count=1)
    ctx["cover"] += n
    return c

def step_headings(c, name, ctx):
    """p.calibre_4 带 bold -> 标题；首条 h1（章级标签合并下一条）"""
    pat = re.compile(r'<p class="calibre_4">(.*?)</p>', re.S)
    hs = [m for m in pat.finditer(c) if '<img' not in m.group(1) and 'bold' in m.group(1)]
    if not hs:
        return c
    # 从后往前替换，避免位置漂移
    plan = []
    for i, m in enumerate(hs):
        t = text_of(m.group(1))
        if i == 0:
            nxt = None
            if len(hs) > 1:
                gap = re.sub(r'<p class="calibre_7">\s*</p>|<[^>]+>|\s+', "", c[m.end():hs[1].start()])
                if gap == "":
                    nxt = hs[1]
            t2 = text_of(nxt.group(1)) if nxt else ""
            if nxt is not None and re.match(CONFIG["chapter_re"], t) and len(t) <= 16 and len(t2) > len(t) and not re.match(CONFIG["chapter_re"], t2):
                h1txt, endpos = t2, nxt.end()
                skiplist = []
                if len(hs) > 2:
                    nxt2 = hs[2]
                    gap2 = re.sub(r'<p class="calibre_7">\s*</p>|<[^>]+>|\s+', "", c[nxt.end():nxt2.start()])
                    t3 = text_of(nxt2.group(1))
                    if gap2 == "" and re.search(r"[，—（(]", t3) and not re.match(CONFIG["chapter_re"], t3):
                        h1txt = t2 + "<br/>" + t3
                        endpos = nxt2.end()
                        skiplist.append(id(nxt2))
                plan.append((m.start(), endpos,
                             '<h1><span class="subtitle">%s</span><br/>%s</h1>' % (t, h1txt)))
                ctx["h1"] += 1
                ctx["skip"].add(id(nxt))
                for x in skiplist:
                    ctx["skip"].add(x)
                continue
            plan.append((m.start(), m.end(), "<h1>%s</h1>" % t))
            ctx["h1"] += 1
            continue
        if getattr(ctx, "skip", None) and id(m) in ctx.get("skip", set()):
            continue
        if id(m) in ctx.get("skip", set()):
            continue
        plan.append((m.start(), m.end(), "<h2>%s</h2>" % t))
        ctx["h2"] += 1
    skip = ctx.get("skip", set())
    for (a, b, rep) in sorted(plan, key=lambda x: -x[0]):
        c = c[:a] + rep + c[b:]
    return c

def step_figures(c, name, ctx):
    """含 img 的 p.calibre_4 / p.calibre_ -> chatu（+ 后续「图N」段作图注）"""
    pat = re.compile(r'<p class="calibre_4?">\s*(<img[^>]*/>)\s*(?:<span[^>]*>\s*</span>)?\s*</p>', re.S)
    def repl(m):
        ctx["chatu"] += 1
        src = re.search(r'src="([^"]*)"', m.group(1))
        out = '<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>' % (src.group(1) if src else "")
        # 紧随的正文段若以「图」开头 -> caption
        rest = c[m.end():]
        mm = re.match(r'\s*<p class="calibre_7">(.*?)</p>', rest, re.S)
        if mm and text_of(mm.group(1)).startswith("图"):
            cap = mm.group(1)
            out += "\n<p class=\"caption\">%s</p>" % cap.strip()
            ctx["caption"] += 1
            return out + "\n</div>", mm.end()
        return out + "\n</div>", 0
    out = []
    pos = 0
    for m in pat.finditer(c):
        if m.start() < pos:
            continue
        out.append(c[pos:m.start()])
        html, extra = repl(m)
        out.append(html)
        pos = m.end() + extra
    out.append(c[pos:])
    return "".join(out)

def step_footnotes(c, name, ctx):
    # 0) 本文件是否有注文：没有注文时，文字 sup 是排版残渣（表格/数字上标），一律原样解包
    has_notes = bool(re.search(r'<ol class="calibre_1[57]">', c))
    # 1) 图标 sup -> [K]
    seq = [0]
    def icon(m):
        seq[0] += 1
        ctx["notes"] += 1
        return '<sup><a epub:type="noteref" href="#foot-%d" id="back-%d">[%d]</a></sup>' % (seq[0], seq[0], seq[0])
    c = re.sub(r'<sup class="calibre7">\s*<small class="calibre8">\s*<img src="[^"]*"[^>]*/>\s*</small>\s*</sup>', icon, c)
    # 2) 文字 sup：有注文时纯数字保留 [N]，其余拆掉；无注文时一律解包原样保留
    def tsup(m):
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if has_notes and re.fullmatch(r"\d{1,4}", t):
            ctx["textref"] += 1
            return '<sup><span class="ref">[%s]</span></sup>' % t
        ctx["supjunk"] += 1
        return t
    c = re.sub(r'<sup class="calibre7">(.*?)</sup>', tsup, c, flags=re.S)
    # 3) 收集注文
    notes = []
    def li(m):
        t = text_of(m.group(1))
        if t:
            notes.append(t)
        return ""
    c = re.sub(r'<ol class="calibre_1[57]">\s*<li value="\d+" class="calibre_16">(.*?)</li>\s*</ol>', li, c, flags=re.S)
    c = re.sub(r'<ol class="calibre_1[57]">.*?</ol>', "", c, flags=re.S)
    if notes:
        ctx["fnote_out"] = notes
    return c

def step_append(c, name, ctx):
    notes = ctx.get("fnote_out") or []
    if not notes:
        return c
    lines = ['<p class="fnote" id="foot-%d"><a href="#back-%d">[%d]</a> %s</p>' % (i + 1, i + 1, i + 1, t)
             for i, t in enumerate(notes)]
    block = "<hr/>\n" + "\n".join(lines) + "\n"
    return c.replace("</body>", block + "</body>")

def step_ns(c, name, ctx):
    if "epub:type=" in c and "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>", r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
        ctx["ns"] += 1
    return c

def step_paras(c, name, ctx):
    # 空 filepos 锚点段 / 空 div / 分页符
    c = re.sub(r'<div class="calibre_14">\s*</div>\s*', "", c)
    c = re.sub(r'<div class="mbp_pagebreak"[^>]*>\s*</div>\s*', "", c)
    c = re.sub(r'<div class="mbp_pagebreak"[^>]*/>\s*', "", c)
    # 书内目录
    c = re.sub(r'<p class="calibre_9">', '<p class="toc1">', c)
    # 落款
    c = re.sub(r'<p class="calibre_13">', '<p class="right">', c)
    # 正文（含各类残余）
    def body(m):
        ctx["paras"] += 1
        return '<p class="bodytext">%s</p>' % m.group(1).strip()
    c = re.sub(r'<p class="calibre_7">(.*?)</p>', body, c, flags=re.S)
    # 残余 p.calibre*（含 id 在前的空 filepos 锚点）-> bodytext，保留 id
    def leftover(m):
        attrs = (m.group(1) or "") + (m.group(2) or "")
        idm = re.search(r'\bid="([^"]*)"', attrs)
        return '<p class="bodytext"%s>%s</p>' % (
            (' id="%s"' % idm.group(1)) if idm else "", m.group(3).strip())
    c = re.sub(r'<p\b([^>]*?)class="calibre[^"]*"([^>]*)>(.*?)</p>', leftover, c, flags=re.S)
    c = re.sub(r'<p class="bodytext">\s*</p>\s*', "", c)
    # 书内目录项（整段只有一个指向其它 xhtml 的链接）-> toc1，须在正文转换之后
    c = re.sub(r'<p class="bodytext">(\s*<a\b[^>]*href="[^"]*index_split_[^"]*"[^>]*>.*?</a>\s*)</p>',
               r'<p class="toc1">\1</p>', c, flags=re.S)
    ctx["left"] += len(re.findall(r'<p class="calibre_', c))
    return c

_SENT = re.compile(r"<span\b[^>]*>|</span>")

def _unwrap_span(c, cls_re, open_tag=None, close_tag=None):
    """深度计数解包/替换指定 class 的 span（可处理嵌套）"""
    pat = re.compile(r'<span\b[^>]*class="(?:%s)"[^>]*>' % cls_re)
    guard = 0
    while True:
        m = pat.search(c)
        if not m or guard > 200000:
            break
        guard += 1
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = _SENT.search(c, j)
            if not m2:
                break
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end()
            close = m2
        if not close:
            break
        inner = c[m.end():close.start()]
        c = c[:m.start()] + ((open_tag + inner + close_tag) if open_tag else inner) + c[close.end():]
    return c

def step_spans(c, name, ctx):
    c = _unwrap_span(c, r"bold", "<b>", "</b>")
    c = _unwrap_span(c, r"italic", "<i>", "</i>")
    for cls in (r"calibre_18", r"calibre[_\d]+|calibre\d+"):
        c = _unwrap_span(c, cls)
    c = re.sub(r"</?small\b[^>]*>", "", c)
    ctx["span_left"] += len(re.findall(r"<span\b", c))
    # 只清 classless 的 <span>（语义类 subtitle/kai/ref 等保留）
    c = re.sub(r"<span></span>", "", c)
    return c

def step_misc(c, name, ctx):
    # 清空标签（无内容、无 id/name 的链接等）
    c = re.sub(r'<a\b(?![^>]*\b(?:id|name)=)[^>]*>\s*</a>', "", c)
    c = re.sub(r'<b>\s*</b>|<i>\s*</i>', "", c)
    c = re.sub(r'<span>\s*</span>', "", c)
    ctx["href"] += len(re.findall(r'href="[^"]*\.html', c))
    c = re.sub(r'(href="[^"#]*?)\.html', r'\1.xhtml', c)
    return c

def step_tidy(c, name, ctx):
    c = re.sub(r"[ \t]+/>", "/>", c)
    c = re.sub(r"[ \t]+>", ">", c)
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

def step_title(c, name, ctx):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", c, re.S)
    if m:
        t = text_of(m.group(1)) or "正文"
        c, n = re.subn(r"<title>.*?</title>", "<title>%s</title>" % t, c, flags=re.S)
        ctx["title"] += n
    return c

STEPS = [("css", step_css), ("body", step_body), ("cover", step_cover), ("clean_divs", step_clean_divs), ("headings", step_headings),
         ("figures", step_figures), ("footnotes", step_footnotes), ("ns", step_ns), ("paras", step_paras),
         ("spans", step_spans), ("misc", step_misc), ("title", step_title),
         ("tidy", step_tidy), ("append", step_append)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    for pat, msg in [
        (r'class="calibre', "残留源 class"),
        (r'<div class="mbp_pagebreak"', "残留分页符"),
        (r'href="[^"]*stylesheet\.css"', "残留旧 css 链接"),
    ]:
        if re.search(pat, c):
            probs.append(msg)
    if ('href="%s"' % CONFIG["css_href"]) not in c:
        probs.append("缺少 %s 链接" % CONFIG["css_href"])
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    return probs

def analyze(dirpath, out=None):
    import collections
    L = ["# analyze(kindle-calibre): %s" % dirpath, ""]
    L.append("files=%d" % len(list_files(dirpath)))
    sig = collections.Counter()
    for fp in list_files(dirpath):
        c = read(fp)
        for m in re.finditer(r'<(\w+)\b([^>]*)>', c):
            cm = re.search(r'class="([^"]*)"', m.group(2))
            sig['%s .%s' % (m.group(1), cm.group(1) if cm else '(#)')] += 1
    L.append("== element.class: %s" % ", ".join("%s x%d" % kv for kv in sig.most_common(20)))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep); print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def process(dirpath, dry=False):
    _st = ensure_styles(dirpath)
    if _st not in ("same", "copied"):
        print("styles.css: %s" % _st)
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.html/*.xhtml"); sys.exit(1)
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
        ctx = dict.fromkeys(["css", "body", "h1", "h2", "chatu", "caption", "notes", "fnote_out",
                             "textref", "supjunk", "ns", "span_left", "cover", "kill", "paras", "left", "href", "title"], 0)
        ctx["fnote_out"] = []
        ctx["skip"] = set()
        for s, fn in STEPS:
            c = fn(c, name, ctx)
        c = postprocess(c)
        probs = verify_content(c, name, dirpath)
        if probs:
            ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs))); continue
        write(os.path.join(outdir, name) if dry else fp, c)
        if not dry and name.endswith(".html"):
            newp = fp[:-5] + ".xhtml"
            if os.path.exists(newp):
                os.remove(newp)
            os.rename(fp, newp)
        print("%-24s h1=%-2d h2=%-3d 图=%-3d 注=%-3d 注文=%-3d 文字ref=%-2d 残sup=%-2d 删=%-2d 段=%-4d href=%d" % (
            name, ctx["h1"], ctx["h2"], ctx["chatu"], ctx["notes"], len(ctx["fnote_out"]),
            ctx["textref"], ctx["supjunk"], ctx["kill"], ctx["paras"], ctx["href"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(dirpath):
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, dirpath)
        if probs:
            ok = False; print("%-24s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-24s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="Kindle→calibre 源 xhtml 清洗")
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
