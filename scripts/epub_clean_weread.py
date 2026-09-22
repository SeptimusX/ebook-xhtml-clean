#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_weread.py — 微信读书 / QQ阅读 导出 EPUB xhtml 清洗

识别特征（同时出现多数即可判定）:
  <section … class="readerChapterContent"><div data-wr-bd="1" data-wr-co="…">
  <span data-wr-id="layout" data-wr-co="…">文字</span>
  <span class="reader_footer_note js_readerFooterNote" data-wr-co="…" data-wr-footernote="注释"></span>
  <p class="content">…</p> / <p class="quotation">…</p>
  <link rel="stylesheet" href="styles/common.css" /> + 大段内联 <style>…</style>

处理顺序（依赖关系，不可乱）:
  1 头部：common.css + 内联 style → styles.css
  2 分隔符 *　*　* → <p class="sprt">
  3 脚注 span → 文中 <a class="ref" …><sup>[N]</sup></a> + 收集注释内容
  4 引文 p.quotation → blockquote > p.bodytext（连续合并；注释章例外）
  5 正文 p.content → p.bodytext
  6a 移除无 class 的 span   6b 移除 data-wr-co / data-wr-id   6c 拆 quotation-inline
  9 修补缺失的 </div></section>
  10 生成尾注块（符号注在前、数字注在后，组间空行；双向锚点），插到 </div></section> 前

子命令: analyze / process / verify （同其他 profile）
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_hrefs": ["styles/common.css"],
    "content_class": "content",              # -> bodytext（精确匹配，不碰 content-c 等）
    "quote_class": "quotation",              # -> blockquote > bodytext
    "bodytext_class": "bodytext",
    "separator_text": "*　*　*",
    "fnote_marker_class": "reader_footer_note",
    "drop_attrs": ["data-wr-co", "data-wr-id"],
    "notes_chapters": [],                    # 「注释章」文件名：quotation 只改 bodytext，不包 blockquote
    "drop_scripts": False,                   # 是否删除 <script …></script>
    "hr": True,
    "symbol_note_gap": True,                 # 符号注与数字注之间留一个空行
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

# ---------- 步骤 ----------

def step_head(c, name, ctx):
    for href in CONFIG["drop_css_hrefs"]:
        c = re.sub(r'[ \t]*<link[^>]*href="%s"[^>]*/>[ \t]*\n?' % re.escape(href), "", c)
    c = re.sub(r"[ \t]*<style\b[^>]*>.*?</style>[ \t]*\n?", "", c, flags=re.S)
    if CONFIG["drop_scripts"]:
        c = re.sub(r"[ \t]*<script\b[^>]*>.*?</script>[ \t]*\n?", "", c, flags=re.S)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link rel="stylesheet" href="%s" />\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c

def step_separator(c, name, ctx):
    sep = CONFIG["separator_text"]
    pat = re.compile(
        r'<p\b[^>]*class="(?:%s|%s)(?: force-page-break)?"[^>]*>\s*<span\b[^>]*>\s*%s\s*</span>\s*</p>' % (
            re.escape(CONFIG["content_class"]), re.escape(CONFIG["quote_class"]), re.escape(sep)), re.S)
    ctx["sprt"] += len(pat.findall(c))
    return pat.sub('<p class="sprt">%s</p>' % sep, c)

def step_footnotes(c, name, ctx):
    notes = []
    pat = re.compile(
        r'<span[^>]*class="[^"]*%s[^"]*"[^>]*data-wr-footernote="([^"]*)"[^>]*?(?:/>|>\s*</span>)' % (
            re.escape(CONFIG["fnote_marker_class"])), re.S)

    def repl(m):
        notes.append(m.group(1))
        k = len(notes)
        return '<a class="ref" href="#note_%d" id="noteref_%d"><sup>[%d]</sup></a>' % (k, k, k)

    c = pat.sub(repl, c)
    ctx["notes"] = notes
    ctx["fnote_left"] = len(re.findall(re.escape(CONFIG["fnote_marker_class"]), c))
    return c

def step_quotes(c, name, ctx):
    qc, bt = re.escape(CONFIG["quote_class"]), CONFIG["bodytext_class"]
    if name in (CONFIG.get("notes_chapters") or []):
        c = re.sub(r'class="%s(?=[\s"])' % qc, 'class="%s' % bt, c)
        ctx["notes_chapter"] += 1
        return c
    pat = re.compile(r'<p\b[^>]*class="%s( force-page-break)?"[^>]*>(.*?)</p>' % qc, re.S)
    c = pat.sub(lambda m: '<p class="%s%s" data-fromquote="1">%s</p>' % (bt, m.group(1) or "", m.group(2)), c)
    pat2 = re.compile(r'(?:<p class="%s[^"]*" data-fromquote="1">.*?</p>\s*)+' % re.escape(bt), re.S)

    def wrap(m):
        ctx["bq"] += 1
        return "<blockquote>\n" + m.group(0).rstrip() + "\n</blockquote>\n"

    c = pat2.sub(wrap, c)
    return c.replace(' data-fromquote="1"', "")

def step_bodytext(c, name, ctx):
    n = len(re.findall(r'class="%s(?=[\s"])' % re.escape(CONFIG["content_class"]), c))
    c = re.sub(r'class="%s(?=[\s"])' % re.escape(CONFIG["content_class"]),
               'class="%s' % CONFIG["bodytext_class"], c)
    ctx["bodytext"] += n
    return c

def step_strip_spans(c, name, ctx):
    """移除不含 class 的 span（微信读书的 layout 包裹）；平衡匹配以处理嵌套"""
    open_re = re.compile(r'<span\b(?![^>]*\bclass=)[^>]*>')
    token_re = re.compile(r"<span\b[^>]*>|</span>")
    n = 0
    while True:
        m = open_re.search(c)
        if not m:
            break
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = token_re.search(c, j)
            if not m2:
                break
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end()
            close = m2
        if close is None or depth:
            break
        c = c[:m.start()] + c[m.end():close.start()] + c[close.end():]
        n += 1
    ctx["spans"] += n
    return c

def step_drop_attrs(c, name, ctx):
    for a in CONFIG["drop_attrs"]:
        n = len(re.findall(r"\s+%s=" % re.escape(a), c))
        c = re.sub(r'\s+%s="[^"]*"' % re.escape(a), "", c)
        ctx["attrs"] += n
    return c

def step_quote_inline(c, name, ctx):
    """拆掉 quotation-inline span（blockquote 已接管引文样式）；组合类只去掉该类"""
    pat = re.compile(r'<span\b[^>]*class="quotation-inline"[^>]*>((?:(?!<span).)*?)</span>', re.S)
    while True:
        c, k = pat.subn(r"\1", c)
        if not k:
            break
    c = re.sub(r'class="([^"]*?)\s+quotation-inline(?=[\s"])', r'class="\1', c)
    c = re.sub(r'class="quotation-inline\s+([^"]*?)"', r'class="\1"', c)
    return c

def step_fix_structure(c, name, ctx):
    """补齐缺失的 </div></section>（按计数：div 与 section 各缺多少补多少）"""
    od, cd = len(re.findall(r"<div\b", c)), len(re.findall(r"</div>", c))
    os_, cs = len(re.findall(r"<section\b", c)), len(re.findall(r"</section>", c))
    if os_ <= cs:
        return c
    need = "</div>" * max(0, od - cd) + "</section>" * (os_ - cs)
    last = None
    for m in re.finditer(r"</div>", c):
        last = m
    if last is not None and od - cd == 0:
        c = c[:last.end()] + need + c[last.end():]
    else:
        c = re.sub(r"(\s*)(</body>)", "\n" + need + r"\1\2", c, count=1)
    ctx["fixed"] += 1
    return c

SYM_RE = re.compile(r"^\[([^\w\]]{1,4})\]", re.UNICODE)

def step_endnotes(c, name, ctx):
    notes = ctx.get("notes") or []
    if not notes:
        return c
    syms, nums = [], []
    for i, text in enumerate(notes, 1):
        t = text.strip()
        m = SYM_RE.match(t)
        if m:
            syms.append((i, m.group(1), t[m.end():].strip()))
        else:
            nums.append((i, t))
    mapping, lines_sym, lines_num = {}, [], []
    for k, (old, sym, txt) in enumerate(syms, 1):
        oid = "note_s%d" % k
        mapping[old] = '<a class="ref" href="#%s" id="noteref_s%d"><sup>[%s]</sup></a>' % (oid, k, sym)
        lines_sym.append('<p class="fnote" id="%s"><a href="#noteref_s%d">[%s]</a> %s</p>' % (oid, k, sym, txt))
    for k, (old, txt) in enumerate(nums, 1):
        oid = "note_%d" % k
        mapping[old] = '<a class="ref" href="#%s" id="noteref_%d"><sup>[%d]</sup></a>' % (oid, k, k)
        lines_num.append('<p class="fnote" id="%s"><a href="#noteref_%d">[%d]</a> %s</p>' % (oid, k, k, txt))
    for old, marker in mapping.items():
        c = c.replace('<a class="ref" href="#note_%d" id="noteref_%d"><sup>[%d]</sup></a>' % (old, old, old), marker)
    if not (lines_sym or lines_num):
        return c
    block = "<hr/>\n" if CONFIG["hr"] else ""
    if lines_sym:
        block += "\n".join(lines_sym) + "\n"
        if lines_num and CONFIG["symbol_note_gap"]:
            block += "\n"
    block += "\n".join(lines_num) + ("\n" if lines_num else "")
    anchor = "</div></section>" if "</div></section>" in c else "</body>"
    ctx["symbols"] = len(syms)
    return c.replace(anchor, block + anchor, 1)

STEPS = [("head", step_head), ("separator", step_separator), ("footnotes", step_footnotes),
         ("quotes", step_quotes), ("bodytext", step_bodytext), ("strip_spans", step_strip_spans),
         ("drop_attrs", step_drop_attrs), ("quote_inline", step_quote_inline),
         ("fix_structure", step_fix_structure), ("endnotes", step_endnotes)]

# ---------- 校验 ----------

def body_text(c):
    i = c.find("<body")
    s = c[i:] if i >= 0 else c
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", "", s)

def integrity(orig, result):
    """正文文本完整性：源(去脚注 span) 与 成果(去正文标记与尾注块) 去标签去空白后应相等"""
    o = re.sub(r'<span[^>]*%s[^>]*>(?:\s*</span>)?' % re.escape(CONFIG["fnote_marker_class"]), "", orig)
    r = re.sub(r'<a class="ref"[^>]*><sup>[^<]*</sup></a>', "", result)
    r = re.sub(r"<hr/>\s*(?:<p class=\"fnote\"[^>]*>.*?</p>\s*)+", "", r, flags=re.S)
    return body_text(o) == body_text(r)

def verify_content(c, name, d):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], info
    if CONFIG["fnote_marker_class"] in c:
        probs.append("残留脚注 span")
    if "<style" in c:
        probs.append("残留内联 style")
    for href in CONFIG["drop_css_hrefs"]:
        if href in c:
            probs.append("残留 %s" % href)
    if 'href="%s"' % CONFIG["css_href"] not in c:
        probs.append("缺少 styles.css 链接")
    for a in CONFIG["drop_attrs"]:
        if re.search(r"\s+%s=" % re.escape(a), c):
            probs.append("残留属性 %s" % a)
    if c.count("<blockquote>") != c.count("</blockquote>"):
        probs.append("blockquote 不配对")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    info.append("sprt=%d fnote=%d bq=%d" % (
        len(re.findall(r'<p class="sprt">', c)), len(re.findall(r'<p class="fnote"', c)),
        c.count("<blockquote>")))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = []
    w = lambda s="": L.append(s)   # noqa: E731
    w("# analyze(weread): %s" % d)
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        pc = collections.Counter(re.findall(r'<p\b[^>]*class="([^"]*)"', c))
        sc = collections.Counter(re.findall(r'<span\b[^>]*class="([^"]*)"', c))
        nf = len(re.findall(r"data-wr-footernote=", c))
        nsep = len(re.findall(re.escape(CONFIG["separator_text"]), c))
        raw = ("common.css" in c) or ("<style" in c)
        bad = []
        if "<section" in c and "</div></section>" not in c:
            bad.append("缺</div></section>")
        if "reader_footer_note" in c and nf == 0:
            bad.append("脚注span无footernote")
        # 注释章候选：quotation 内含锚点链接
        if re.search(r'<p[^>]*class="quotation[^"]*"[^>]*>(?:(?!</p>).)*?<a\s', c, re.S):
            bad.append("quotation含链接(疑注释章)")
        tot["fnote"] += nf; tot["sep"] += nsep
        w("%-18s raw=%-5s foot=%-4d sep=%-3d p:%s span:%s %s" % (
            name, raw, nf, nsep,
            ",".join("%s x%d" % (k, v) for k, v in pc.most_common(6)),
            ",".join("%s x%d" % (k, v) for k, v in sc.most_common(4)),
            ("  !! " + ",".join(bad)) if bad else ""))
    w()
    w("== 汇总: files=%d footernote=%d 分隔符=%d" % (len(files), tot["fnote"], tot["sep"]))
    w("== 注释章候选（写入 notes_chapters）: %s" % "见上 !! 标记")
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
        orig = read(fp)
        c = orig
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        ctx = collections_defaults()
        for sname, fn in STEPS:
            c = fn(c, name, ctx)
        probs, info = verify_content(c, name, d)
        if not integrity(orig, c):
            probs.append("正文文本完整性校验失败")
        if probs:
            ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-18s sprt=%-3d fnote=%-4d(sym%-3d) bq=%-3d bodytext=%-3d span=%-4d attr=%-4d %s" % (
            name, ctx["sprt"], len(ctx["notes"]), ctx["symbols"], ctx["bq"], ctx["bodytext"],
            ctx["spans"], ctx["attrs"], ("fix " if ctx["fixed"] else "")))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def collections_defaults():
    return {"notes": [], "sprt": 0, "bq": 0, "bodytext": 0, "spans": 0, "attrs": 0,
            "fixed": 0, "symbols": 0, "notes_chapter": 0, "fnote_left": 0}

def verify_dir(d):
    ok = True
    for fp in list_files(d):
        name = os.path.basename(fp)
        probs, info = verify_content(read(fp), name, d)
        if probs:
            ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-18s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="微信读书/QQ阅读 导出 xhtml 清洗")
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
