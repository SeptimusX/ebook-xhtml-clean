#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_legacy.py — 旧成果（本 skill 早期输出）收尾：把旧约定升级到最新规则

识别特征（早期输出）:
  <html xml:lang="zh-cn">、<link href="../Styles/style0001.css"/>
  正文 <p class="content">
  目录 <p class="contents1|2"><a href="partNNNN.xhtml">…</a></p>
  图   <div class="picture"><img alt="figure_…"/>[<p class="imgIntro">图注</p>]</div>
  注   <sup><a id="chN" href="file#chN-back">[N]</a></sup>
       章末 <hr/> + <p class="fnotecontent"><a id="chN-back" href="file#chN">[N]</a>注文</p>
  题词 <blockquote><p>…</p><p class="inscribe">——某某</p></blockquote>
  版权页 <div class="copyright margin-left2">…</div>
  书名页 <div class="bookTitle"></div><div class="booksubname">书名</div><div class="author">…</div>
         <div class="publish"><img …/></div>
  章标题 h1 / 节 h2 / 小节 h3.sigil_not_in_toc

映射（升级到最新约定）:
  css      -> styles.css
  content  -> <p class="bodytext">
  目录     -> contents1 -> p.toc1、contents2 -> p.toc2
  图       -> <div class="chatu"><p class="image"><img/></p><p class="caption">…</p></div>
  注       -> ref:  <sup><a epub:type="noteref" href="#…" id="noteref-N">[N]</a></sup>
              注文: <p class="fnote" id="…-back"><a href="#noteref-N">[N]</a> 注文</p>
  题词     -> <blockquote class="intro">…<p class="right">——某某</p></blockquote>
  版权页   -> p.bodytext-noindent（内嵌 <hr/> 保留）
  书名页   -> <h1>书名</h1> + p.author + chatu
  收尾     -> 通用规则（NBSP/中英空格/逐字 i 合并/chatu 去重/chatu 间 sprt）

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import postprocess, ensure_styles

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:style\d*|stylesheet|page_styles|Style)\.css",
    "p_class": "content",
    "bodytext_class": "bodytext",
    "toc_map": {"contents1": "toc1", "contents2": "toc2"},
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

FIG_RE = re.compile(r'<div class="picture">\s*(<img[^>]*/>)\s*'
                    r'(?:<p class="imgIntro">(.*?)</p>\s*)?</div>', re.S)

def step_figures(c, name, ctx):
    def repl(m):
        img, cap = m.group(1), m.group(2)
        ctx["chatu"] += 1
        out = '<div class="chatu">\n<p class="image">%s</p>\n' % img_keep(img)
        if cap:
            out += '<p class="caption">%s</p>\n' % cap.strip()
        return out + "</div>"
    return FIG_RE.sub(repl, c)

REF_RE = re.compile(r'<sup><a id="([^"]*)" href="(?:[^"#]*)#([^"]*)">\[(\d+)\]</a></sup>')
FN_RE = re.compile(r'<p class="fnotecontent"><a id="([^"]*)" href="(?:[^"#]*)#([^"]*)">\[(\d+)\]</a>\s*(.*?)</p>', re.S)

def step_footnotes(c, name, ctx):
    if not (REF_RE.search(c) or FN_RE.search(c)):
        return c
    c = _ens_epub(c)
    seq = {}

    def rr(m):
        ctx["refs"] += 1
        n = len(seq) + 1
        seq[m.group(2)] = n          # 用回链目标 id 做键
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%s]</a></sup>' % (
            m.group(2), n, m.group(3))
    c = REF_RE.sub(rr, c)

    def rn(m):
        ctx["fnotes"] += 1
        n = seq.get(m.group(1))
        if n is None:
            ctx["orphan"] += 1
            return '<p class="fnote" id="%s">[%s] %s</p>' % (m.group(1), m.group(3), m.group(4).strip())
        return '<p class="fnote" id="%s"><a href="#noteref-%d">[%s]</a> %s</p>' % (
            m.group(1), n, m.group(3), m.group(4).strip())
    c = FN_RE.sub(rn, c)
    return c

def step_toc(c, name, ctx):
    for src, dst in CONFIG["toc_map"].items():
        c, n = re.subn(r'<p class="%s">' % re.escape(src), '<p class="%s">' % dst, c)
        ctx["toc"] += n
    return c

def step_blockquote(c, name, ctx):
    # 题词：<blockquote><p>…</p><p class="inscribe">——署名</p></blockquote>
    def repl(m):
        ctx["intro"] += 1
        inner = m.group(1)
        inner = re.sub(r'<p class="inscribe">(.*?)</p>', r'<p class="right">\1</p>', inner, flags=re.S)
        return '<blockquote class="intro">%s</blockquote>' % inner
    return re.sub(r'<blockquote>(.*?<p class="inscribe">.*?)</blockquote>', repl, c, flags=re.S)

def step_misc(c, name, ctx):
    # 章末落款（不在 blockquote 里的 inscribe）
    c, n_ins = re.subn(r'<p class="inscribe">', '<p class="right">', c)
    ctx["right"] = ctx.get("right", 0) + n_ins
    # 版权页里只有一条 <hr/> 的 div：直接输出 <hr/>
    c = re.sub(r'<div class="copyright[^"]*">\s*(<hr/>)\s*</div>', r'\1', c, flags=re.S)
    # 版权页 div -> p.bodytext-noindent
    c, n = re.subn(r'<div class="copyright[^"]*">(.*?)</div>',
                   lambda m: '<p class="bodytext-noindent">%s</p>' % m.group(1).strip(), c, flags=re.S)
    ctx["copyright"] += n
    # 书名页
    c = re.sub(r'<div class="bookTitle">\s*</div>\s*', "", c)
    c, n2 = re.subn(r'<div class="booksubname">(.*?)</div>', r'<h1>\1</h1>', c, flags=re.S)
    c = re.sub(r'<div class="author">(.*?)</div>', r'<p class="author">\1</p>', c, flags=re.S)
    c = re.sub(r'<div class="publish">\s*(<img[^>]*/>)\s*</div>',
               lambda m: '<div class="chatu">\n<p class="image">%s</p>\n</div>' % img_keep(m.group(1)),
               c, flags=re.S)
    ctx["title"] += n2
    return c

def step_body(c, name, ctx):
    c, n = re.subn(r'<p class="%s">' % re.escape(CONFIG["p_class"]),
                   '<p class="%s">' % CONFIG["bodytext_class"], c)
    ctx["bodytext"] += n
    # 裸 <p>（主要在 blockquote 里）
    c, n2 = re.subn(r"<p>", '<p class="%s">' % CONFIG["bodytext_class"], c)
    ctx["bodytext"] += n2
    return c

def step_tidy(c, name, ctx):
    # 仅剩的内联 style 去掉
    c = re.sub(r'\s+style="[^"]*"', "", c)
    # 兜底清残留旧类
    for cls in ["imgIntro", "fnotecontent", "picture", "contents1", "contents2", "inscribe",
                "copyright", "booksubname", "bookTitle", "publish", "margin-left2"]:
        c = re.sub(r'\s+class="[^"]*%s[^"]*"' % re.escape(cls), "", c)
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        body = re.sub(r"\n(?:[ \t]*\n)+", "\n", body)
        c = pre + body
    return c

STEPS = [("css", step_css), ("figures", step_figures), ("footnotes", step_footnotes),
         ("toc", step_toc), ("blockquote", step_blockquote), ("misc", step_misc),
         ("body", step_body), ("tidy", step_tidy)]

# ---------- 校验 ----------

def verify_content(c, name, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], []
    for pat, msg in [
        (r'class="(?:content|fnotecontent|picture|imgIntro|contents[12]|inscribe|copyright|bookTitle|booksubname|publish)"',
         "残留旧 class"),
        (r'class="[^"]*margin-left2', "残留 margin-left2"),
        (r"\sstyle=\"", "残留内联 style"),
        (r'href="[^"]*Styles?/', "残留旧 css 链接"),
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
    info.append("bodytext=%d fnote=%d chatu=%d toc=%d" % (
        len(re.findall(r'class="bodytext"', c)), nfn,
        len(re.findall(r'<div class="chatu">', c)), len(re.findall(r'class="toc[12]"', c))))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = ["# analyze(legacy 旧成果): %s" % d, ""]
    files = list_files(d)
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        cl = collections.Counter(re.findall(r'class="([^"]*)"', c))
        tot["content"] += cl.get("content", 0)
        tot["fnote"] += cl.get("fnotecontent", 0)
        tot["picture"] += cl.get("picture", 0)
        tot["toc"] += cl.get("contents1", 0) + cl.get("contents2", 0)
        L.append("%-16s content=%-4d 图=%-3d 注=%-3d 目录=%-3d h1=%-2d h2=%-2d h3=%-3d | %s" % (
            os.path.basename(fp), cl.get("content", 0), cl.get("picture", 0),
            cl.get("fnotecontent", 0), cl.get("contents1", 0) + cl.get("contents2", 0),
            c.count("<h1"), c.count("<h2"), c.count("<h3"),
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
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(base, name))
        ctx = dict.fromkeys(["css", "chatu", "refs", "fnotes", "orphan", "toc",
                             "intro", "copyright", "title", "bodytext"], 0)
        try:
            for sname, fn in STEPS:
                c = fn(c, name, ctx)
            c = postprocess(c)
        except Exception as e:
            ok = False
            print("%-16s FAIL: %s" % (name, e))
            continue
        probs, _ = verify_content(c, name, d)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s bodytext=%-4d 图=%-3d ref=%-3d 注=%-3d 目录=%-2d 题词=%-2d" % (
            name, ctx["bodytext"], ctx["chatu"], ctx["refs"], ctx["fnotes"],
            ctx["toc"], ctx["intro"]))
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
    ap = argparse.ArgumentParser(description="旧成果收尾：升级到最新约定")
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
