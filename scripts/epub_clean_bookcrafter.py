#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_bookcrafter.py — bookcrafter 生成版 xhtml 清洗（磨铁 / Z-Library 等）

源特征:
  <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">
  <link rel="stylesheet" type="text/css" href="../Styles/style.css"/>
  内联 <style>body p.bookcrafter-body-paragraph { text-indent: 2.00em !important; duokan-text-indent: … }</style>
  <h1 style="font-size: 1.45em; text-align: center; …">标题</h1>
  正文全部是 <p class="bookcrafter-body-paragraph">…</p>（无 span / img / br / blockquote）
  脚注是「纯文本编号」形式，无任何链接或锚点:
    正文引用：…“团块世代”  (1)  ，两人…
    章末尾注：<p class="bookcrafter-body-paragraph">(1) 　注文</p>（连续成块、编号 1..N）
  目录页 body-toc.xhtml：<div class="toc-list"><p><a href="chapterNNN.xhtml">标题</a></p>…</div>

处理:
  css  : 删 ../Styles/style.css 链接与全部内联 <style>，加同目录 styles.css
  h1   : 去内联 style
  正文 : p.bookcrafter-body-paragraph -> p.bodytext
  脚注 : 末尾 (N) 段 -> <hr/> + <p class="fnote" id="footnote-N"><a href="#noteref-N">[N]</a> 注文</p>
         正文 (N) -> <sup><a epub:type="noteref" href="#footnote-N" id="noteref-N">[N]</a></sup>
         （源里可能有无引用的「孤儿注」：仍保留为尾注，但不加回链，不走编号压缩）
  目录 : 解包 div.toc-list，<p> -> <p class="toc1">
  收尾 : 去行首缩进与空行

⚠ 源书 h1 可能是「正文1 / 正文 2 / …」这类占位标题；只要 TOC 与 h1 一致，就属源书本身，勿擅自改写。

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import strip_sprt_between_chatu

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:^|/)style\.css$",
    "para_class": "bookcrafter-body-paragraph",
    "bodytext_class": "bodytext",
    "toc_class": "toc1",
    # 生成工具留下的占位标题：「正文 28」->「28」（h1 / <title> / 目录项同步）
    "placeholder_title_re": r"^正文[ \t]*(\d+)$",
}

P_PARA = re.compile(r'<p class="%s">(.*?)</p>' % CONFIG["para_class"], re.S)
DEF_HEAD = re.compile(r'^\((\d+)\)[ \t\u3000]*(.*)$', re.S)
PLACEHOLDER = re.compile(CONFIG["placeholder_title_re"])


def plain_title(text):
    """占位标题归一化：返回纯数字，非占位标题返回 None"""
    m = PLACEHOLDER.match(text.strip())
    return m.group(1) if m else None

# ---------- 基础 ----------

def list_files(d):
    files = []
    for pat in ("*.xhtml", "*.html"):
        files += [f for f in glob.glob(os.path.join(d, pat)) if not f.endswith(".bak")]
    return sorted(set(files))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def _esc(m):
    return m.group(0)

# ---------- 步骤 ----------

def step_css(c, name, ctx):
    c, n1 = re.subn(r'[ \t]*<link[^>]*href="[^"]*(?:^|/)style\.css"[^>]*/>[ \t]*\n?', "", c)
    c, n2 = re.subn(r'[ \t]*<style\b[^>]*>.*?</style>[ \t]*\n?', "", c, flags=re.S)
    ctx["css"] += n1 + n2
    if 'href="%s"' % CONFIG["css_href"] not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % CONFIG["css_href"],
                   c, count=1)
    return c

def step_headings(c, name, ctx):
    def repl(m):
        ctx["h1"] += 1
        attrs = re.sub(r'\s+style="[^"]*"', "", m.group(1))
        text = m.group(2)
        t = plain_title(re.sub(r"<[^>]+>", "", text))
        if t:
            ctx["title"] += 1
            text = t
        return "<h1%s>%s</h1>" % (attrs, text)
    c = re.sub(r"<h1([^>]*)>(.*?)</h1>", repl, c, flags=re.S)

    def repl_title(m):
        t = plain_title(m.group(1))
        if t:
            return "<title>%s</title>" % t
        return m.group(0)
    c = re.sub(r"<title>(.*?)</title>", repl_title, c, flags=re.S)
    return c

def step_footnotes(c, name, ctx):
    """末尾 (N) 段 -> fnote；正文 (N) -> noteref。必须在 body 步骤之前。"""
    ps = list(P_PARA.finditer(c))
    defs = []
    for m in reversed(ps):
        dm = DEF_HEAD.match(m.group(1).strip())
        if not dm:
            break
        defs.append((m, int(dm.group(1)), re.sub(r'[ \t]*\n[ \t]*', "", dm.group(2)).strip()))
    defs.reverse()
    if not defs:
        return c

    nums = [k for _, k, _ in defs]
    if nums != list(range(1, len(nums) + 1)):
        raise RuntimeError("%s: 末尾尾注编号不连续 %s" % (name, nums))
    ctx["defs"] += len(defs)

    # 先删尾注段，剩下的 (N) 才是正文引用
    for m, _, _ in reversed(defs):
        c = c[:m.start()] + c[m.end():]

    known, used = set(nums), set()
    if "xmlns:epub" not in c:
        c = re.sub(r"<html\b([^>]*)>",
                   r'<html\1 xmlns:epub="http://www.idpf.org/2007/ops">', c, count=1)
    def rr(m):
        k = int(m.group(1))
        if k not in known:
            ctx["unmatched"] += 1
            return m.group(0)
        used.add(k)
        ctx["notes"] += 1
        return '<sup><a epub:type="noteref" href="#footnote-%d" id="noteref-%d">[%d]</a></sup>' % (k, k, k)
    c = re.sub(r'[ \t]*\((\d+)\)[ \t]*', rr, c)

    lines = []
    for _, k, text in defs:
        if k in used:
            back = '<a href="#noteref-%d">[%d]</a>' % (k, k)
        else:
            back = "[%d]" % k
            ctx["orphan"] += 1
        lines.append('<p class="fnote" id="footnote-%d">%s %s</p>' % (k, back, text))
    block = "<hr/>\n" + "\n".join(lines)
    i = c.rfind("</body>")
    c = c[:i].rstrip() + "\n" + block + "\n" + c[i:]
    return c

def step_toc(c, name, ctx):
    i = c.find('<div class="toc-list">')
    if i < 0:
        return c
    c = c[:i] + c[i + len('<div class="toc-list">'):]
    j = c.find("</div>", i)
    if j >= 0:
        c = c[:j] + c[j + 6:]

    def repl(m):
        text = m.group(2)
        t = plain_title(text)
        if t:
            ctx["title"] += 1
            text = t
        return '<p class="%s">%s%s%s</p>' % (CONFIG["toc_class"], m.group(1), text, m.group(3))

    c, n = re.subn(r"<p>(<a\b[^>]*>)(.*?)(</a>)</p>", repl, c, flags=re.S)
    ctx["toc"] += n
    return c

def step_body(c, name, ctx):
    n = c.count('class="%s"' % CONFIG["para_class"])
    c = c.replace('class="%s"' % CONFIG["para_class"], 'class="%s"' % CONFIG["bodytext_class"])
    ctx["bodytext"] += n
    return c

def step_tidy(c, name, ctx):
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        head = re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0))
        c = c[:hm.start()] + head + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"\n(?:[ \t]*\n)+", "\n", body)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        body = re.sub(r"\n{3,}", "\n\n", body)
        c = pre + body
    return c

STEPS = [("css", step_css), ("headings", step_headings), ("footnotes", step_footnotes),
         ("toc", step_toc), ("body", step_body), ("tidy", step_tidy)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], []
    for pat, msg in [
        (r'class="bookcrafter', "残留 bookcrafter 类"),
        (r'\sstyle="', "残留内联 style"),
        (r"<style\b", "残留内联 <style>"),
        (r'href="[^"]*Styles?/[^"]*\.css"', "残留旧 css 链接"),
        (r"toc-list", "残留 toc-list"),
        (r"<div\b", "残留 div"),
        (r"\(\d+\)", "残留 (N) 编号"),
        (r"<h1[^>]*>正文", "残留占位标题 h1"),
        (r"<title>正文", "残留占位 <title>"),
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
    refs = set(re.findall(r'id="noteref-(\d+)"', c))
    feet = set(re.findall(r'id="footnote-(\d+)"', c))
    if refs - feet:
        probs.append("有 ref 无注: %s" % sorted(refs - feet)[:3])
    info.append("bodytext=%d fnote=%d noteref=%d" % (
        len(re.findall(r'class="bodytext"', c)), len(feet), len(refs)))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = ["# analyze(bookcrafter): %s" % d, ""]
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        ps = list(P_PARA.finditer(c))
        defs = 0
        for m in reversed(ps):
            if DEF_HEAD.match(m.group(1).strip()):
                defs += 1
            else:
                break
        body = "".join(m.group(1) for m in ps[:len(ps) - defs]) if defs else "".join(m.group(1) for m in ps)
        refs = sorted(set(int(x) for x in re.findall(r"\((\d+)\)", body)))
        h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", c, re.S)
        tot["files"] += 1
        tot["paras"] += len(ps)
        tot["defs"] += defs
        tot["refs"] += len(refs)
        tot["toc"] += 1 if "toc-list" in c else 0
        L.append("%-20s 段=%-4d 尾注=%-2d 正文引用=%-2d csstyle=%-2d | %s" % (
            name, len(ps), defs, len(refs), c.count("<style"),
            re.sub(r"<[^>]+>", "", h1[0])[:22] if h1 else ""))
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
        ctx = dict.fromkeys(["css", "h1", "title", "notes", "defs", "orphan", "unmatched", "toc", "bodytext"], 0)
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
        except Exception as e:
            ok = False
            print("%-20s FAIL: %s" % (name, e))
            continue
        c = strip_sprt_between_chatu(c)
        probs, _ = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-20s bodytext=%-4d 尾注=%-2d 引用=%-2d 孤儿注=%-2d 目录项=%-2d 标题归一=%-2d h1=%-2d" % (
            name, ctx["bodytext"], ctx["defs"], ctx["notes"],
            ctx["orphan"], ctx["toc"], ctx["title"], ctx["h1"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(d):
    ok = True
    for fp in list_files(d):
        name = os.path.basename(fp)
        probs, info = verify_content(read(fp), name, d)
        if probs:
            ok = False
            print("%-20s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-20s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="bookcrafter 版 xhtml 清洗")
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
