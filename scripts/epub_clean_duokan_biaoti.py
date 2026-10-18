#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_duokan_biaoti.py — 多看(duokan)原生 xhtml 清洗（neiwen/biaoti 命名变体）

识别特征:
  <html xmlns="http://www.w3.org/1999/xhtml">（无 xml:lang）
  <link type="text/css" rel="stylesheet" href="../styles/fonts.css"/> + page_styles.css + stylesheet.css
  正文 <p><span class="neiwen">…</span></p>（变体 neiwen2 / neiwen2_1 / neiwen3 / neiwen4 / neiwen5 / neiwen6）
  标题 <h1><span class="biaoti1">第X章<br/><span class="biaoti2">副题</span></span></h1>、
       <h2><span class="biaoti3">一</span></h2>、<h2><span class="biaoti5">1.1 …</span></h2>
  插图 <div class="duokan-image-single"><img/><p class="duokan-image-maintitle">…</p>
       <p class="duokan-image-subtitle">…</p></div>
  注释 <a class="duokan-footnote" href="#foN" id="forefN"><img src="../images/note.png"/></a>
       文末 <div><hr class="xian"/></div><ol class="duokan-footnote-content">
            <li class="duokan-footnote-item" id="foN"><p class="footnote-content">
            <a href="#forefN" style="…">[N]</a> 注文</p></li></ol>

处理（顺序有依赖）:
  1) css：fonts.css / page_styles.css / stylesheet.css → 同目录 styles.css
  2) 插图：duokan-image-single → <div class="chatu">（img + 主标题 caption + 副标题 caption，保留链接/id）
  3) 标题：biaoti1(+biaoti2) → <h1>…<br/><span class="subtitle">…</span></h1>；
           biaoti3 / biaoti5 / list_of_ill / banquan / neiwen6 的 span 去掉（标签保留）
  4) 引文：<p><span class="neiwen2">…</span></p> → <blockquote><p class="bodytext">…</p></blockquote>
           （连续合并；内部 neiwen2_1 去标签）
  5) 正文：neiwen / neiwen3 / neiwen5 → <p class="bodytext">；neiwen4（——落款）→ <p class="right">
  6) 注释：触发标记 → <sup><a epub:type="noteref" href="#foN" id="noteref-K">[N]</a></sup>；
           文末 <ol> → 章末 <hr/> + <p class="fnote" id="foN"><a href="#noteref-K">[N]</a> 注文</p>
  7) 收尾：<hr class="xian"/> → <hr/>；删除 <p class="whitespace">&#160;</p> 空段与空 <div>

子命令: analyze / process / verify
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import postprocess, ensure_styles

CONFIG = {
    "css_href": "styles.css",
    "drop_css_hrefs": ["../styles/fonts.css", "../styles/page_styles.css", "../styles/stylesheet.css"],
    "bodytext_class": "bodytext",
    "body_from": ["neiwen", "neiwen3", "neiwen5"],   # -> bodytext（neiwen3 仅作兜底，正常情况下由 intro 规则处理）
    "intro_from": ["neiwen3"],                       # 章前摘要：紧随 h1 的那条 -> blockquote.intro > p.center
    "right_from": ["neiwen4"],                       # -> right（落款）
    "quote_from": ["neiwen2"],                       # -> blockquote
    "quote_inner": ["neiwen2_1"],                    # 引文内层，去标签
    "unwrap_in_heading": ["biaoti1", "biaoti2", "biaoti3", "biaoti5", "list_of_ill", "banquan", "neiwen6"],
    "hr": True,
}

# ---------- 基础 ----------

def list_files(d):
    out = []
    for pat in ("*.xhtml", "*.html"):
        out += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    return sorted(set(out))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def unwrap_span(c, cls):
    """去掉 <span class="cls">…</span> 的标签（最内层优先，处理嵌套）"""
    pat = re.compile(r'<span class="%s">((?:(?!<span).)*?)</span>' % re.escape(cls), re.S)
    n = 0
    while True:
        c, k = pat.subn(r"\1", c)
        n += k
        if not k:
            break
    return c, n

# ---------- 步骤 ----------

CSS_LINK = '<link href="%s" rel="stylesheet" type="text/css"/>' % CONFIG["css_href"]

def step_css(c, name, ctx):
    for href in CONFIG["drop_css_hrefs"]:
        c = re.sub(r'[ \t]*<link[^>]*href="%s"[^>]*/>[ \t]*\n?' % re.escape(href), "", c)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        m = re.search(r'([ \t]*)<style\b', c)
        if m:
            # 有内联 <style>（如封面）：styles.css 放其前，保证内联样式优先级更高
            c = c[:m.start(1)] + m.group(1) + CSS_LINK + "\n" + c[m.start(1):]
        else:
            c = re.sub(r"([ \t]*)</head>", r"\1  " + CSS_LINK + r"\n\1</head>", c, count=1)
    return c

IMG_RE = re.compile(
    r'<div class="duokan-image-single">\s*(<img[^>]*?/>)\s*'
    r'(?:<p class="duokan-image-maintitle">(.*?)</p>\s*)?'
    r'(?:<p class="duokan-image-subtitle">(.*?)</p>\s*)?</div>', re.S)

def step_images(c, name, ctx):
    def repl(m):
        img, main, sub = m.group(1), m.group(2), m.group(3)
        src = re.search(r'src="([^"]*)"', img)
        alt = re.search(r'alt="([^"]*)"', img)
        ctx["chatu"] += 1
        out = ('<div class="chatu">\n<p class="image"><img src="%s" alt="%s"/></p>\n' % (
            src.group(1) if src else "", alt.group(1) if alt else ""))
        if main:
            out += '<p class="caption">%s</p>\n' % main
        if sub:
            out += '<p class="caption">%s</p>\n' % sub
        return out + "</div>"

    return IMG_RE.sub(repl, c)

def step_headings(c, name, ctx):
    # biaoti1（章号行）+ biaoti2（书题行）-> 章号套 subtitle，书题作正文
    pat = re.compile(r'<span class="biaoti1">(.*?)<br/>\s*<span class="biaoti2">(.*?)</span>\s*</span>', re.S)
    c, n = pat.subn(r'<span class="subtitle">\1</span><br/>\2', c)
    ctx["subtitle"] += n
    for cls in CONFIG["unwrap_in_heading"]:
        c, k = unwrap_span(c, cls)
        ctx["head"] += k
    # 变体：类直接挂在标题标签上（<h2 class="biaoti5">…</h2>）
    for cls in CONFIG["unwrap_in_heading"]:
        c, k = re.subn(r'(<h[1-6])\s+class="%s"' % re.escape(cls), r"\1", c)
        ctx["head"] += k
    return c

def step_quotes(c, name, ctx):
    for cls in CONFIG["quote_inner"]:
        c, _ = unwrap_span(c, cls)
    pat = re.compile(r'<p><span class="(%s)">(.*?)</span></p>' % "|".join(map(re.escape, CONFIG["quote_from"])), re.S)
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
        lines = []
        for m in g:
            # 引文内不用 <br/> 分行：每个诗行/段落各自成 <p class="bodytext">
            for part in re.split(r'<br\s*/?>', m.group(2)):
                part = part.strip()
                if part:
                    lines.append('<p class="%s">%s</p>' % (CONFIG["bodytext_class"], part))
        block = "<blockquote>\n" + "\n".join(lines) + "\n</blockquote>"
        c = c[:start] + block + c[end:]
        ctx["bq"] += len(g)
    return c

def step_intro(c, name, ctx):
    """章标题单独成文件时，h1 之后的那条章前摘要 -> blockquote.intro > p.center"""
    pat = re.compile(r'(</h1>\s*)<p><span class="(%s)">(.*?)</span></p>' % "|".join(
        map(re.escape, CONFIG["intro_from"])), re.S)

    def repl(m):
        ctx["intro"] += 1
        return '%s<blockquote class="intro">\n<p class="center">%s</p>\n</blockquote>' % (
            m.group(1), m.group(3).strip())

    return pat.sub(repl, c)

def step_body(c, name, ctx):
    for cls in CONFIG["body_from"]:
        pat = re.compile(r'<p><span class="%s">(.*?)</span></p>' % re.escape(cls), re.S)
        n = len(pat.findall(c))
        c = pat.sub(lambda m: '<p class="%s">%s</p>' % (CONFIG["bodytext_class"], m.group(1)), c)
        ctx["bodytext"] += n
    for cls in CONFIG["right_from"]:
        pat = re.compile(r'<p><span class="%s">(.*?)</span></p>' % re.escape(cls), re.S)
        n = len(pat.findall(c))
        c = pat.sub(lambda m: '<p class="right">%s</p>' % m.group(1), c)
        ctx["right"] += n
    return c

TRIG_RE = re.compile(r'<a class="footnote-trigger"[^>]*></a>')
MARK_RE = re.compile(r'<a class="duokan-footnote" href="#([^"]+)" id="([^"]+)"><img[^>]*/></a>')
OL_RE = re.compile(r'([ \t]*<hr/>)?\s*<ol class="duokan-footnote-content">(.*?)</ol>', re.S)
LI_RE = re.compile(
    r'<li class="duokan-footnote-item" id="([^"]+)">\s*<p class="footnote-content">\s*'
    r'<a[^>]*href="#([^"]+)"[^>]*>\[(\d+)\]</a>(.*?)</p>\s*</li>', re.S)

def step_footnotes(c, name, ctx):
    c = TRIG_RE.sub("", c)                      # 空的 footnote-trigger（与 duokan-footnote 重复 id）
    if not MARK_RE.search(c):
        return c
    if "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>", r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
    note_num = {}                               # note_id -> [N]
    for note_id, _marker, num, _txt in LI_RE.findall(c):
        note_num[note_id] = int(num)

    seq = {"n": 0}

    def mark_repl(m):
        note_id, marker_id = m.group(1), m.group(2)
        seq["n"] += 1
        n = seq["n"]
        ctx["marks"] += 1
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%d]</a></sup>' % (note_id, n, n)

    c = MARK_RE.sub(mark_repl, c)

    def ol_repl(m):
        items = LI_RE.findall(m.group(2))
        lines = []
        for note_id, marker_id, num, text in items:
            n = note_num.get(note_id)
            lines.append('<p class="fnote" id="%s"><a href="#noteref-%d">[%s]</a>%s</p>' % (
                note_id, n, num, text.rstrip()))
            ctx["fnotes"] += 1
        head = "<hr/>\n" if CONFIG["hr"] else ""
        return head + "\n".join(lines)

    c = OL_RE.sub(ol_repl, c)
    return c

def step_hr(c, name, ctx):
    # <hr class="xian"/>（含 <div> 包裹）→ <hr/>
    c = re.sub(r'<div>\s*<hr class="xian"/>[\s]*</div>', "<hr/>", c)
    c, n = re.subn(r'<hr class="xian"\s*/>', "<hr/>", c)
    ctx["hr"] += n
    return c

def step_ws(c, name, ctx):
    n = len(re.findall(r'<p class="whitespace">[^<]*</p>\n?', c))
    c = re.sub(r'<p class="whitespace">[^<]*</p>\n?', "", c)
    ctx["ws"] += n
    return c

STEPS = [("css", step_css), ("images", step_images), ("headings", step_headings),
         ("quotes", step_quotes), ("intro", step_intro), ("body", step_body),
         ("hr", step_hr), ("footnotes", step_footnotes), ("ws", step_ws)]

# ---------- 校验 ----------

def verify_content(c, name, d):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        probs.append("XML 解析失败: %s" % e)
    for p, lbl in [("duokan-image", "残留插图div"), ("duokan-footnote", "残留注释标记"),
                   ("note.png", "残留note.png"), ('class="neiwen', "残留neiwen"),
                   ('class="biaoti', "残留biaoti"), ('class="xian"', "残留xian"),
                   ('class="whitespace"', "残留whitespace"), ("fonts.css", "旧css"),
                   ("page_styles.css", "旧css"), ("../styles/stylesheet.css", "旧css")]:
        if p in c:
            probs.append(lbl)
    if 'href="styles.css"' not in c:
        probs.append("缺少 styles.css 链接")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    nref = len(re.findall(r'id="noteref-(\d+)"', c))
    fn = len(re.findall(r'<p class="fnote"', c))
    if nref != fn:
        probs.append("noteref(%d) != fnote(%d)" % (nref, fn))
    nums = sorted(int(x) for x in re.findall(r'id="noteref-(\d+)"', c))
    if nums and nums != list(range(1, len(nums) + 1)):
        probs.append("noteref 编号不连续")
    info.append("chatu=%d fnote=%d intro=%d bodytext=%d" % (
        len(re.findall(r'<div class="chatu">', c)), fn,
        len(re.findall(r'<blockquote class="intro">', c)), len(re.findall(r'class="bodytext"', c))))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = []
    w = lambda s="": L.append(s)
    w("# analyze(duokan/neiwen): %s" % d)
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        cls = collections.Counter(re.findall(r'class="([^"]*)"', c))
        links = re.findall(r'href="([^"]*\.css)"', c)
        tot["mark"] += len(MARK_RE.findall(c))
        tot["img"] += len(IMG_RE.findall(c))
        w("%-16s 标记=%-3d 插图=%-3d h1=%-3d h2=%-3d h3=%-2d 关键类=%s" % (
            name, len(MARK_RE.findall(c)), len(IMG_RE.findall(c)),
            c.count("<h1"), c.count("<h2"), c.count("<h3"),
            ",".join("%s x%d" % (k, v) for k, v in cls.most_common(6))))
    w()
    w("== 汇总: files=%d 标记=%d 插图div=%d" % (len(files), tot["mark"], tot["img"]))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

def process(d, dry=False):
    _st = ensure_styles(dirpath)          # 先把 skill 内的 styles.css 放到目标目录
    if _st not in ("same", "copied"):
        print("styles.css: %s" % _st)
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
        ctx = {"chatu": 0, "subtitle": 0, "head": 0, "bq": 0, "intro": 0, "bodytext": 0,
               "right": 0, "marks": 0, "fnotes": 0, "ws": 0, "hr": 0}
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
        except Exception as e:
            ok = False
            print("%-16s FAIL: %s" % (name, e))
            continue
        c = postprocess(c)
        probs, info = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s chatu=%-2d 标记=%-3d 尾注=%-3d 引文=%-3d 摘要=%-2d bodytext=%-4d right=%-2d h去span=%-3d 空段=%-2d" % (
            name, ctx["chatu"], ctx["marks"], ctx["fnotes"], ctx["bq"], ctx["intro"],
            ctx["bodytext"], ctx["right"], ctx["head"], ctx["ws"]))
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
    ap = argparse.ArgumentParser(description="多看原生(neiwen/biaoti) xhtml 清洗")
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
