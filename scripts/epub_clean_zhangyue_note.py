#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_zhangyue_note.py — 掌阅 ZHANGYUE「行内图片注」版（profile AA）

适用特征（源文件）:
  <html xmlns="http://www.w3.org/1999/xhtml">（无 lang / 无 xmlns:epub）
  <link href="../Styles/wKgH…css"/>（哈希文件名）
  <body class="" style="">
    <div class="h5_mainbody"> … </div>                     每章外壳
    <div class="h5_mainbody_bg copyright-basemap"> … </div> 版权页
  <h1 class="text-title-1-c">上篇</h1>
  <h2 class="text-title-2-c0" id="sigil_toc_id_6"><span class="content-word-small">第一章</span><br/>章名</h2>
  <h3 class="text-title-3" id="sigil_toc_id_7">一 节名</h3>
  <p class="bodytext">正文</p>
  <p class="bodytext-kt-only-np">单段楷体引文</p>
  <p class="bodytext-kt-first-np">多段引文首段</p>
  <p class="bodytext-kt-np">…中段…</p>
  <p class="bodytext-kt-last-np">…末段…</p>
  <p class="preface-text">参考文献条目 / 后记正文</p>
  <p class="center">（以作者姓名拼音排序）</p>
  <p class="inscribed-right">王立新<br/>2007年3月于…</p>
  <span class="bold">…</span>
  <p class="copyright-text">书名：…<br/>作者：…</p>
  **行内图片注**（本书 904 条，符号图 + 注文写在属性里）:
  <img alt="" class="zhangyue-footnote" src="../Images/CmQ…png"
       zy-footnote="Bayless Manning, “Goals, Ideology and Foreign Policy”, …p.274."/>

映射:
  css -> styles.css；html 补 xmlns:epub 与 lang="zh-CN"
  解包 div.h5_mainbody / div.h5_mainbody_bg；<body …> -> <body>
  text-title-1-c -> h1；text-title-2-c / -2-c0 -> h2；text-title-3 -> h3（id 原样保留）
  span.content-word-small（篇/章号）-> span.subtitle
  引文组 bodytext-kt-(only|first|np|last)-np -> 一个 <blockquote><p class="bodytext">…
  p.preface-text -> p.bodytext；p.inscribed-right -> p.right；span.bold -> <b>
  版权页：h4.copyright-title -> h1，p.copyright-text(1) -> p.bodytext-noindent
  行内图片注 -> <sup><a epub:type="noteref" href="#foot-N" id="back-N">[N]</a></sup>
                + </body> 前 <hr/> + <p class="fnote" id="foot-N"><a href="#back-N">[N]</a> 注文</p>
                （每文件从 1 重排）
  收尾 -> postprocess()

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse
import datetime
import glob
import html
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from epub_clean_common import postprocess, ensure_styles

CONFIG = {
    "css_href": "styles.css",
    "css_drop_re": r'href="[^"]*(?:wKg[A-Za-z0-9]+|[Ss]tyles/[^"]*|stylesheet[^"]*)\.css"',
    "skip_files": (),
}


# ---------- 基础 ----------

def list_files(d):
    out = []
    for pat in ("*.xhtml", "*.html"):
        out += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]

    def key(p):
        m = re.search(r"(\d+)", os.path.basename(p))
        return (0, int(m.group(1))) if m else (1, os.path.basename(p))
    return sorted(set(out), key=key)


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c, n = re.subn(r'[ \t]*<link[^>]*%s[^>]*/>[ \t]*\n?' % CONFIG["css_drop_re"], "", c)
    ctx["css"] = ctx.get("css", 0) + n
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1<link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c


def step_html(c, name, ctx):
    """html 补 xmlns:epub / lang；body 去属性"""
    m = re.search(r"<html\b[^>]*>", c)
    if m:
        tag = m.group(0)
        new = tag
        if "xmlns:epub" not in new:
            new = new[:-1] + ' xmlns:epub="http://www.idpf.org/2007/ops">'
        if "xml:lang=" not in new:
            new = new[:-1] + ' xml:lang="zh-CN" lang="zh-CN">'
        if new != tag:
            c = c[:m.start()] + new + c[m.end():]
            ctx["html"] = ctx.get("html", 0) + 1
    c, n = re.subn(r"<body[^>]*>", "<body>", c)
    ctx["body_tag"] = ctx.get("body_tag", 0) + n
    return c


def _unwrap_div(c, cls_re, ctx, key):
    """按深度计数解包 <div class="…">…</div>"""
    pat = re.compile(r'<div[^>]*class="[^"]*(?:%s)[^"]*"[^>]*>' % cls_re)
    total = 0
    while True:
        m = pat.search(c)
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
        total += 1
    ctx[key] = ctx.get(key, 0) + total
    return c


def step_shell(c, name, ctx):
    c = _unwrap_div(c, r"h5_mainbody", ctx, "unwrap")
    return c


def _clean_head(inner):
    inner = re.sub(r"\s+", " ", inner).strip()
    inner = re.sub(r"\s*<br\s*/>\s*", "<br/>", inner)
    inner = re.sub(r">\s+", ">", inner)
    inner = re.sub(r"\s+<", "<", inner)
    return inner


def step_headings(c, name, ctx):
    def repl(m):
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        cls = re.search(r'class="([^"]*)"', attrs)
        if not cls:
            return m.group(0)
        v = cls.group(1)
        if v.startswith("text-title-1"):
            newlevel = "1"
        elif v.startswith("text-title-2"):
            newlevel = "2"
        elif v.startswith("text-title-3"):
            newlevel = "3"
        else:
            return m.group(0)
        keep = re.search(r'\bid="([^"]+)"', attrs)
        inner = re.sub(r'<span class="content-word-small">\s*(.*?)\s*</span>',
                       r'<span class="subtitle">\1</span>', inner, flags=re.S)
        inner = _clean_head(inner)
        ctx["heads"] = ctx.get("heads", 0) + 1
        return "<h%s%s>%s</h%s>" % (newlevel, ' id="%s"' % keep.group(1) if keep else "",
                                    inner, newlevel)
    c = re.sub(r"<h([1-6])([^>]*)>(.*?)</h\1>", repl, c, flags=re.S)

    # 源书把一条节标题拆成两个连续 h3（前一条以「：」结尾）：合并，保留后一个 id
    def merge(m):
        ida, ta, idb, tb = m.group(1), m.group(2).strip(), m.group(3), m.group(4).strip()
        if not ta.endswith(("：", ":")):
            return m.group(0)
        ctx["h3_join"] = ctx.get("h3_join", 0) + 1
        return "<h3%s>%s%s</h3>" % (' id="%s"' % idb if idb else "", ta, tb)
    c = re.sub(r'<h3(?:\s+id="([^"]*)")?>([^<]*)</h3>\s*'
               r'<h3(?:\s+id="([^"]*)")?>([^<]*)</h3>', merge, c)
    return c
def step_quotes(c, name, ctx):
    pat = re.compile(
        r'<p class="(?:bodytext-kt-(?:only|first|last)-np|bodytext-kt-np)">(.*?)</p>', re.S)
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
        parts = ["<p class=\"bodytext\">%s</p>" % _clean_head(m.group(1)) for m in g]
        block = "<blockquote>\n%s\n</blockquote>" % "\n".join(parts)
        c = c[:g[0].start()] + block + c[g[-1].end():]
        ctx["quotes"] = ctx.get("quotes", 0) + 1
        ctx["quote_paras"] = ctx.get("quote_paras", 0) + len(g)
    return c


IMG_NOTE = re.compile(r'<img\b[^>]*class="[^"]*\bzhangyue-footnote\b[^"]*"[^>]*/>', re.S)
ZY_ATTR = re.compile(r'zy-footnote="(.*?)"\s*/>', re.S)


def _note_text(raw):
    t = html.unescape(raw)
    t = re.sub(r"\s+", " ", t).strip()
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def step_notes(c, name, ctx):
    notes = []

    def repl(m):
        tag = m.group(0)
        z = ZY_ATTR.search(tag)
        notes.append(_note_text(z.group(1)) if z else "")
        k = len(notes)
        return '<sup><a epub:type="noteref" href="#foot-%d" id="back-%d">[%d]</a></sup>' % (k, k, k)

    c = IMG_NOTE.sub(repl, c)
    ctx["notes"] = ctx.get("notes", 0) + len(notes)
    if not notes:
        return c
    lines = ['<p class="fnote" id="foot-%d"><a href="#back-%d">[%d]</a> %s</p>' % (i + 1, i + 1, i + 1, t)
             for i, t in enumerate(notes)]
    c = c.replace("</body>", "<hr/>\n" + "\n".join(lines) + "\n</body>")
    return c


def step_body(c, name, ctx):
    c = re.sub(r'<p class="preface-text">(.*?)</p>',
               lambda m: '<p class="bodytext">%s</p>' % _clean_head(m.group(1)), c, flags=re.S)
    c = re.sub(r'<p class="inscribed-right">(.*?)</p>',
               lambda m: '<p class="right">%s</p>' % _clean_head(m.group(1)), c, flags=re.S)
    c = re.sub(r'<p class="copyright-text1?">(.*?)</p>',
               lambda m: '<p class="bodytext-noindent">%s</p>' % _clean_head(m.group(1)), c, flags=re.S)
    c = re.sub(r'<h4 class="copyright-title">\s*(.*?)\s*</h4>', r'<h1>\1</h1>', c, flags=re.S)
    c = re.sub(r'<span class="bold">(.*?)</span>', r'<b>\1</b>', c, flags=re.S)
    c = re.sub(r'<span class="content-word-small">\s*(.*?)\s*</span>', r'\1', c, flags=re.S)
    # 版权页封面图：整页图 -> chatu
    def cover(m):
        src = re.search(r'src="([^"]*)"', m.group(1))
        alt = re.search(r'alt="([^"]*)"', m.group(1))
        ctx["chatu"] = ctx.get("chatu", 0) + 1
        return ('<div class="chatu">\n<p class="image"><img src="%s" alt="%s"/></p>\n</div>' %
                (src.group(1) if src else "", alt.group(1) if alt else ""))
    c = re.sub(r'<div>\s*<img([^>]*?)/>\s*</div>',
               lambda m: cover(m), c, flags=re.S)
    return c


CJK = "\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"


def _squeeze_text(s):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?<=[%s])\s+(?=[%s])" % (CJK, CJK), "", s)
    return s


def _squeeze_html(h):
    parts = re.split(r"(<[^>]+>)", h)
    for i in range(0, len(parts), 2):
        parts[i] = _squeeze_text(parts[i])
    s = "".join(parts)
    s = re.sub(r"(?<=[%s])\s+(?=<)" % CJK, "", s)
    s = re.sub(r"(?<=>)\s+(?=[%s])" % CJK, "", s)
    s = re.sub(r"^ +| +$", "", s)
    return s


def step_tidy(c, name, ctx):
    # 段落内部：源文件每行都换行缩进，压成一行（汉字间不留空格，英文单词间留一个）
    def para(m):
        return "<p%s>%s</p>" % (m.group(1), _squeeze_html(m.group(2)))
    c = re.sub(r"<p\b([^>]*)>(.*?)</p>", para, c, flags=re.S)
    c = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", c)
    c = re.sub(r"[ \t]+\n", "\n", c)
    c = re.sub(r"<body>\s*\n+", "<body>\n", c)
    c = re.sub(r"\n+[ \t]*</body>", "\n</body>", c)
    return c


STEPS = [("css", step_css), ("html", step_html), ("shell", step_shell),
         ("headings", step_headings), ("quotes", step_quotes), ("notes", step_notes),
         ("body", step_body), ("tidy", step_tidy)]


# ---------- 校验 ----------

RESIDUAL = [
    (r'class="[^"]*text-title-', "残留 text-title-* class"),
    (r'class="[^"]*(?:zhangyue|content-word-small|bodytext-kt|preface-text|h5_mainbody|copyright|inscribed-right)[^"]*"',
     "残留源 class"),
    (r"zy-footnote=", "残留 zy-footnote 属性"),
    (r'<img[^>]*footnote', "残留注记图片"),
    (r'href="[^"]*/Styles/[^"]*"', "残留旧 css 链接"),
    (r'<p style=|style="', "残留内联 style"),
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
    nref = len(re.findall(r'epub:type="noteref"', c))
    nfn = len(re.findall(r'<p class="fnote"', c))
    if nref != nfn:
        probs.append("noteref(%d) != fnote(%d)" % (nref, nfn))
    info.append("bodytext=%d fnote=%d h1=%d h2=%d h3=%d bq=%d" % (
        len(re.findall(r'class="bodytext"', c)), nfn,
        len(re.findall(r"<h1", c)), len(re.findall(r"<h2", c)), len(re.findall(r"<h3", c)),
        len(re.findall(r"<blockquote", c))))
    return probs, info


# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = ["# analyze(zhangyue img-note): %s" % d, ""]
    tot = collections.Counter()
    for fp in list_files(d):
        c = read(fp)
        name = os.path.basename(fp)
        cl = collections.Counter(re.findall(r'class="([^"]*)"', c))
        n = {
            "note": len(IMG_NOTE.findall(c)),
            "h1": len(re.findall(r"<h1\b", c)),
            "h2": len(re.findall(r"<h2\b", c)),
            "h3": len(re.findall(r"<h3\b", c)),
            "kt": sum(v for k, v in cl.items() if k.startswith("bodytext-kt")),
            "body": cl.get("bodytext", 0),
            "pref": cl.get("preface-text", 0),
        }
        for k, v in n.items():
            tot[k] += v
        L.append("%-18s 注=%-3d body=%-3d kt=%-3d pref=%-3d h=%d/%d/%d | %s" % (
            name, n["note"], n["body"], n["kt"], n["pref"], n["h1"], n["h2"], n["h3"],
            ", ".join("%s x%d" % kv for kv in cl.most_common(3))))
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
    tn = 0
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        ctx = {}
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
            c = postprocess(c)
        except Exception as e:
            ok = False
            print("%-20s FAIL: %s" % (name, e))
            continue
        probs, _ = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        tn += ctx.get("notes", 0)
        print("%-20s 注=%-3d 引文组=%-2d/%-3d 标题=%d 头=%-2d 解包=%d" % (
            name, ctx.get("notes", 0), ctx.get("quotes", 0), ctx.get("quote_paras", 0),
            ctx.get("heads", 0), ctx.get("html", 0), ctx.get("unwrap", 0)))
    print("合计注:", tn)
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)


def verify_dir(d):
    ok = True
    tot = 0
    for fp in list_files(d):
        name = os.path.basename(fp)
        probs, info = verify_content(read(fp), name, d)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
        else:
            tot += info[0].count("fnote")
            print("%-20s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description="掌阅行内图片注（zy-footnote）清洗")
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
