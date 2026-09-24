#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_duokan.py — 多看(duokan) 原生导出 xhtml 清洗（图片式注释标记变体）

识别特征:
  <html … xml:lang="zh-CN" …>（常无 xmlns:epub）
  <link href="../Styles/stylesheet.css" …/>（+ ../Styles/oxenfont.css）
  <h1 class="chapter-title1"> / <h2 class="chapter-title2" id="sigil_toc_id_N">
  <p class="text">正文</p>
  正文注释标记（图片式）:
    <a class="duokan-footnote" href="#a_X_Y" id="c_X_Y"><img alt="注释N" class="duokan-footnote" src="../Images/note.png"/></a>
  文末注释列表:
    <ol class="duokan-footnote-content">
      <li class="duokan-footnote-item" id="a_X_Y"><p class="footnote-text">
        <a class="duokan-footnote-link" href="#c_X_Y">注文</a>​​​​​</p></li>
      …
    </ol>

处理:
  1) css 链接（stylesheet.css / oxenfont.css）→ styles.css
  2) <p class="text"> → <p class="bodytext">
  3) <h2 class="chapter-title2"> → <h3 class="chapter-title2">（保留 id）
  4) 正文图片式注释标记 → <sup><a epub:type="noteref" href="#a_X_Y" id="noteref-N">[N]</a></sup>
     （必要时补 xmlns:epub 声明）
  5) 文末 <ol> 注释列表 → <hr/> + <p class="fnote" id="a_X_Y"><a href="#noteref-N">[N]</a> 注文</p>
     编号每文件从 1 开始，双向回链

子命令: analyze / process / verify （同其他 profile）
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_hrefs": ["../Styles/stylesheet.css", "../Styles/oxenfont.css"],
    "body_class_from": ["text"],        # p.text -> p.bodytext
    "bodytext_class": "bodytext",
    "heading_map": {"h2": "h3"},        # chapter-title2 的 h2 -> h3
    "quote_class": "quote",             # <p class="quote"> -> bodytext（blockquote 内的引文段）
    "signature_class": "signature",     # <p class="signature"> -> right（署名/出处行）
    "signature_to": "right",
    "signature_spacer_prefixes": ["（原载于"],  # 这些前缀的署名行前加一个空行段
    "hr": True,
}

MARK_RE = re.compile(
    r'<a class="duokan-footnote" href="#([^"]+)" id="([^"]+)"><img[^>]*/></a>')
OL_RE = re.compile(r'<ol class="duokan-footnote-content">(.*?)</ol>', re.S)
LI_RE = re.compile(
    r'<li class="duokan-footnote-item" id="([^"]+)"><p class="footnote-[^"]*">\s*'
    r'<a class="duokan-footnote-link" href="#([^"]+)">(.*?)</a>[\u200b\s]*</p></li>', re.S)

# ---------- 基础 ----------

def list_files(d):
    return sorted(f for f in glob.glob(os.path.join(d, "*.xhtml")) if not f.endswith(".bak"))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    for href in CONFIG["drop_css_hrefs"]:
        c = re.sub(r'[ \t]*<link[^>]*href="%s"[^>]*/>[ \t]*\n?' % re.escape(href), "", c)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c

def step_bodytext(c, name, ctx):
    for cls in CONFIG["body_class_from"]:
        n = len(re.findall(r'class="%s(?=[\s"])' % re.escape(cls), c))
        c = re.sub(r'class="%s(?=[\s"])' % re.escape(cls), 'class="%s' % CONFIG["bodytext_class"], c)
        ctx["bodytext"] += n
    return c

def step_headings(c, name, ctx):
    for old, new in CONFIG["heading_map"].items():
        pat = re.compile(r'<%s(\b[^>]*class="chapter-title2"[^>]*)>' % old)
        n = len(pat.findall(c))
        c = pat.sub(lambda m: "<%s%s>" % (new, m.group(1)), c)
        pat2 = re.compile(r'</%s>' % old)
        c = pat2.sub("</%s>" % new, c)
        ctx["headings"] += n
    return c

def step_quote_signature(c, name, ctx):
    """blockquote 内的 <p class="quote"> -> bodytext；<p class="signature"> -> right
    （「（原载于…」这类出处行前插入一个空行段）"""
    qc = CONFIG.get("quote_class")
    if qc:
        n = len(re.findall(r'<p class="%s"' % re.escape(qc), c))
        c = c.replace('<p class="%s">' % qc, '<p class="%s">' % CONFIG["bodytext_class"])
        ctx["quote"] += n
    sc = CONFIG.get("signature_class")
    if sc:
        for pref in CONFIG.get("signature_spacer_prefixes") or []:
            spacer = '<p class="%s"><br/></p>' % CONFIG["bodytext_class"]
            pat = re.compile(r'<p class="%s">%s' % (re.escape(sc), re.escape(pref)))

            def add(m):
                if c[:m.start()].rstrip().endswith(spacer):
                    return m.group(0)
                ctx["spacer"] += 1
                return spacer + "\n" + m.group(0)

            c = pat.sub(add, c)
        n = len(re.findall(r'<p class="%s"' % re.escape(sc), c))
        c = c.replace('<p class="%s">' % sc, '<p class="%s">' % CONFIG["signature_to"])
        ctx["sign"] += n
    return c

def step_footnotes(c, name, ctx):
    if not MARK_RE.search(c):
        return c
    if "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>",
                   r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)

    href2n, mark_ids = {}, {}

    def mark_repl(m):
        note_id, marker_id = m.group(1), m.group(2)
        n = len(href2n) + 1
        href2n[note_id] = n
        mark_ids[marker_id] = n
        ctx["marks"] += 1
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%d]</a></sup>' % (note_id, n, n)

    c = MARK_RE.sub(mark_repl, c)

    def ol_repl(m):
        items = LI_RE.findall(m.group(1))
        lines = []
        for note_id, marker_id, text in items:
            n = href2n.get(note_id) or mark_ids.get(marker_id)
            if n is None:
                raise RuntimeError("%s: 注释 %s 找不到对应正文标记" % (name, note_id))
            text = re.sub(r"[\u200b]+", "", text).strip()
            lines.append('<p class="fnote" id="%s"><a href="#noteref-%d">[%d]</a> %s</p>' % (
                note_id, n, n, text))
            ctx["fnotes"] += 1
        if len(items) != len(href2n):
            raise RuntimeError("%s: 注释条目 %d 与正文标记 %d 数量不符" % (name, len(items), len(href2n)))
        head = "<hr/>\n" if CONFIG["hr"] else ""
        return head + "\n".join(lines)

    c = OL_RE.sub(ol_repl, c)
    return c

STEPS = [("css", step_css), ("bodytext", step_bodytext), ("headings", step_headings),
         ("quote_signature", step_quote_signature), ("footnotes", step_footnotes)]

# ---------- 校验 ----------

def verify_content(c, name, d):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        probs.append("XML 解析失败: %s" % e)
    if "duokan-footnote" in c or "note.png" in c or "footnote-text" in c:
        probs.append("残留多看注释标记")
    if CONFIG.get("quote_class") and ('<p class="%s">' % CONFIG["quote_class"]) in c:
        probs.append("残留 quote 类")
    if CONFIG.get("signature_class") and ('<p class="%s">' % CONFIG["signature_class"]) in c:
        probs.append("残留 signature 类")
    if re.search(r'class="%s(?=[\s"])' % "|".join(re.escape(x) for x in CONFIG["body_class_from"]), c):
        probs.append("残留旧正文类")
    for href in CONFIG["drop_css_hrefs"]:
        if href in c:
            probs.append("残留 %s" % href)
    if 'href="%s"' % CONFIG["css_href"] not in c:
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
    if fn and c.count("<hr/>") != 1:
        probs.append("hr 数量异常")
    info.append("标记=%d 尾注=%d bodytext=%d h3=%d" % (
        nref, fn, len(re.findall(r'class="bodytext"', c)), len(re.findall(r"<h3", c))))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = []
    w = lambda s="": L.append(s)
    w("# analyze(duokan native): %s" % d)
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        mk = len(MARK_RE.findall(c))
        ol = len(OL_RE.findall(c))
        pt = len(re.findall(r'<p class="text"', c))
        h2 = len(re.findall(r'<h2[^>]*class="chapter-title2"', c))
        links = re.findall(r'<link[^>]*href="([^"]+)"', c)
        tot["mark"] += mk; tot["text"] += pt; tot["h2"] += h2
        w("%-16s 标记=%-3d ol=%-2d p.text=%-4d h2.ct2=%-3d css=%s" % (name, mk, ol, pt, h2, links))
    w()
    w("== 汇总: files=%d 标记=%d p.text=%d h2.chapter-title2=%d" % (
        len(files), tot["mark"], tot["text"], tot["h2"]))
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
        ctx = {"marks": 0, "fnotes": 0, "bodytext": 0, "headings": 0, "quote": 0, "sign": 0, "spacer": 0}
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
        except Exception as e:
            ok = False
            print("%-16s FAIL: %s" % (name, e))
            continue
        probs, info = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s 标记=%-3d 尾注=%-3d bodytext=%-4d h3=%-3d OK" % (
            name, ctx["marks"], ctx["fnotes"], ctx["bodytext"], ctx["headings"]))
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
    ap = argparse.ArgumentParser(description="多看原生 xhtml 清洗（图片式注释标记）")
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
