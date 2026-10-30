#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_calibre_simple.py — calibre 导出的「简类号」社科书（profile V）

识别特征（社科文献·甲骨文一类的 calibre 转换稿）:
  <html xmlns="…" xml:lang="zh-CN"> + <link href="../Styles/style0001.css"/>
  正文 <p>（无 class）；引文/条文 <p class="block">；图 <p class="center"><img …/></p>(+<p class="img">图注</p>)
  题词 <p class="center1">…</p> + 落款 <p class="lk">——…</p>
  脚注：正文 <a id="wN"></a><a href="文件#mN"><sup>[N]</sup></a>
        章末 <hr/> + <p class="note"><a id="mN"></a><a href="文件#wN">[N]</a> 注文</p>
  书内目录 <ul><li><a href="partNNNN.xhtml#aNNN">…</a>（可嵌套）
  封面 cover_page.xhtml（内联 <style> + SVG <image>）、前折口/书名页/后折口/封底 为纯图页
  版权页（CIP 文字）独立一文件

映射:
  css → styles.css；<html> 补 xmlns:epub
  h1.front 空标题 → 删除；h1/h2 保留原 id（ncx 按它跳转）
  图（含图注）→ div.chatu；纯图页 → 单个 chatu；封面 → body.cover
  引用 <a id="wN"></a><a href="…#mN"><sup>[N]</sup></a> → <sup><a epub:type="noteref" href="#mN" id="wN">[N]</a></sup>
  注文 <p class="note"><a id="mN"></a><a href="…#wN">[N]</a> …</p> → <p class="fnote" id="mN"><a href="#wN">[N]</a> …</p>
  引文 <p class="block">（连续者）→ blockquote + p.bodytext
  题词（p.center1 + p.lk）→ blockquote.intro + p.right
  书内目录 ul/li → p.toc1 / p.toc2
  版权页（含「图书在版编目」）→ p.bodytext-noindent
  其余 <p> → p.bodytext；p.left → p.bodytext-noindent；
  非版权页里以「——」开头的短段（书评落款）→ p.right

子命令: analyze <dir> [-o REPORT] / process <dir> [--dry-run] / verify <dir>
"""
import argparse
import datetime
import glob
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from epub_clean_common import postprocess, ensure_styles

ALLOWED_CLASSES = {
    "bodytext", "bodytext-noindent", "fnote", "fnotel", "image", "caption",
    "chatu", "toutu", "center", "right", "left", "left2", "toc1", "toc2",
    "intro", "poem", "blockcenter", "menu", "sprt", "pgbrk", "cover",
    "date", "author", "box", "subtitle",
}


# ---------- 基础 ----------

def list_files(d):
    fs = []
    for pat in ("*.xhtml", "*.html"):
        fs += glob.glob(os.path.join(d, pat))
    def key(p):
        m = re.search(r"(\d+)", os.path.basename(p))
        return (0, int(m.group(1))) if m else (1, os.path.basename(p))
    return sorted(set(fs), key=key)


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def text_of(c):
    c = re.sub(r"<head>.*?</head>", "", c, flags=re.S)
    c = re.sub(r"<sup[^>]*>.*?</sup>", "", c, flags=re.S)
    c = re.sub(r"<a[^>]*>\[\d+\]</a>", "", c)
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", "", c).replace("\u25cb", "\u3007")


def role_of(name, c):
    if "<svg" in c and "<image" in c:
        return "cover"
    body = c[c.find("<body"):]
    if re.search(r"图书在版编目|CIP", body):
        return "colophon"
    if re.search(r'<ul[^>]*>\s*<li[^>]*>\s*<a href="part', body):
        return "toc"
    if '<p class="center1">' in body and '<p class="lk">' in body:
        return "epigraph"
    stripped = re.sub(r"<[^>]+>", "", body).strip()
    if "chatu-face" not in c and re.search(r'<p class="center">\s*<img[^>]*/>\s*</p>', body) \
            and not stripped.replace("　", "").strip():
        return "image"
    return "content"


# ---------- 正文清洗 ----------

RE_REF = re.compile(r'<a id="(w\d+)"></a><a href="[^"#]*#(m\d+)"><sup>(\[\d+\])</sup></a>')
RE_NOTE = re.compile(r'<p class="note"><a id="(m\d+)"></a><a href="[^"#]*#(w\d+)">(\[\d+\])</a>(.*?)</p>', re.S)
RE_FIG = re.compile(r'<p class="center">\s*<img([^>]*?)/>\s*</p>\s*(?:<p class="img">(.*?)</p>)?', re.S)
RE_BLOCKRUN = re.compile(r'(?:<p class="block">.*?</p>\s*)+', re.S)


def _fig(m):
    src = re.search(r'src="([^"]+)"', m.group(1)).group(1)
    cap = re.sub(r"<[^>]+>", "", m.group(2)).strip() if m.group(2) else ""
    out = ['<div class="chatu">', '<p class="image"><img src="%s" alt=""/></p>' % src]
    if cap:
        out.append('<p class="caption">%s</p>' % cap)
    out.append("</div>")
    return "\n".join(out)


def clean_content(c, name, role):
    body = c[c.find("<body"):]
    body = re.sub(r"^<body[^>]*>", "", body)
    body = re.sub(r"</body>.*$", "", body, flags=re.S)

    # 空标题
    body = re.sub(r'<h1[^>]*class="front"[^>]*>\s*</h1>\n?', "", body)
    body = re.sub(r'<h1[^>]*>\s*</h1>\n?', "", body)
    # h 标签只留 id
    def h_keep_id(m):
        tag, attrs, txt = m.group(1), m.group(2), m.group(3)
        hid = re.search(r'id="([^"]+)"', attrs)
        return "<%s%s>%s</%s>" % (tag, ' id="%s"' % hid.group(1) if hid else "", txt, tag)
    body = re.sub(r"<(h[12])([^>]*)>(.*?)</\1>", h_keep_id, body, flags=re.S)

    # 脚注引用 / 注文
    body = RE_REF.sub(
        lambda m: '<sup><a epub:type="noteref" href="#%s" id="%s">%s</a></sup>'
                  % (m.group(2), m.group(1), m.group(3)), body)
    body = RE_NOTE.sub(
        lambda m: '<p class="fnote" id="%s"><a href="#%s">%s</a>%s</p>'
                  % (m.group(1), m.group(2), m.group(3),
                     m.group(4) if m.group(4).startswith(" ") else " " + m.group(4).lstrip()), body)

    # 图 + 图注
    body = RE_FIG.sub(_fig, body)

    # 连续引文段
    def blockrun(m):
        ps = re.findall(r'<p class="block">(.*?)</p>', m.group(0), re.S)
        out = []
        for p in ps:
            txt = p.strip()
            plain = re.sub(r'<[^>]+>', '', txt).strip()
            cls = "right" if plain.startswith("——") and len(plain) < 120 else "bodytext"
            out.append('<p class="%s">%s</p>' % (cls, txt))
        return "<blockquote>\n" + "\n".join(out) + "\n</blockquote>\n"
    body = RE_BLOCKRUN.sub(blockrun, body)

    # 题词（center1 + lk）
    m = re.search(r'<p class="center1">(.*?)</p>\s*<p class="lk">(.*?)</p>', body, re.S)
    epigraph = None
    if m and role == "epigraph":
        epigraph = ('<blockquote class="intro">\n<p class="bodytext">%s</p>\n<p class="right">%s</p>\n</blockquote>'
                    % (m.group(1).strip(), m.group(2).strip()))
        body = body[:m.start()] + epigraph + body[m.end():]
        role = "content"

    # 目录页
    if role == "toc":
        def conv(inner, cls):
            out = []
            for m in re.finditer(r"<li[^>]*>(.*?)</li>", inner, re.S):
                item = m.group(1)
                link = re.search(r"<a[^>]*>.*?</a>", item, re.S)
                rest = item[link.end():].strip() if link else ""
                if link:
                    out.append('<p class="%s">%s</p>' % (cls, link.group(0).strip()))
                elif item.strip():
                    out.append('<p class="%s">%s</p>' % (cls, item.strip()))
                if rest:
                    out.append(rest)
            return "\n".join(out)

        # 先内层（此时内层不含 ul），再外层
        body = re.sub(r"<ul[^>]*>((?:(?!<ul).)*?)</ul>",
                      lambda m: conv(m.group(1), "toc2"), body, flags=re.S)
        body = re.sub(r"<ul[^>]*>((?:(?!<ul).)*?)</ul>",
                      lambda m: conv(m.group(1), "toc1"), body, flags=re.S)
        body = re.sub(r"\n{3,}", "\n\n", body)

    # 段落映射
    def pmap(m):
        attrs, txt = m.group(1), m.group(2)
        cm = re.search(r'class="([^"]*)"', attrs)
        cls = cm.group(1) if cm else ""
        if cls in ("fnote", "image", "caption", "toc1", "toc2"):
            return m.group(0)
        plain = re.sub(r"<[^>]+>", "", txt).strip()
        if not plain and "<img" not in txt:
            return ""
        if role == "colophon":
            return '<p class="bodytext-noindent">%s</p>' % txt
        if cls == "left":
            return '<p class="bodytext-noindent">%s</p>' % txt
        if cls in ("center1", "center", "lk"):
            return '<p class="center">%s</p>' % txt
        if plain.startswith("——") and len(plain) < 80:
            return '<p class="right">%s</p>' % txt
        return '<p class="bodytext">%s</p>' % txt
    body = re.sub(r"<p([^>]*)>(.*?)</p>", pmap, body, flags=re.S)

    # 清理
    body = re.sub(r'\s+style="[^"]*"', "", body)
    body = re.sub(r'<br\s*/>', "<br/>", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def process_file(fp):
    name = os.path.basename(fp)
    c = read(fp)
    role = role_of(name, c)
    title = ""
    mt = re.search(r"<title>(.*?)</title>", c, re.S)
    if mt:
        title = mt.group(1).strip()

    if role == "cover":
        img = re.search(r'<image[^>]*xlink:href="([^"]+)"', c)
        src = img.group(1) if img else "../Images/cover.jpg"
        body = '<div><img src="%s" alt="封面"/></div>' % src
        h = ('<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n<title>%s</title>\n'
             '<link href="styles.css" rel="stylesheet" type="text/css"/>\n</head>\n'
             '<body class="cover">\n%s\n</body>\n</html>\n' % (title, body))
        return h, role

    body = clean_content(c, name, role)
    lang = re.search(r'<html[^>]*?(xml:lang="[^"]*"|lang="[^"]*")[^>]*>', c)
    langattr = (" " + lang.group(1)) if lang else ""
    h = ('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"%s>\n'
         "<head>\n<title>%s</title>\n"
         '<link href="styles.css" rel="stylesheet" type="text/css"/>\n'
         "</head>\n<body>\n%s\n</body>\n</html>\n" % (langattr, title, body.strip()))
    return h, role


# ---------- 校验 ----------

def verify_content(c, name):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except ET.ParseError as e:
        return ["XML %s" % e], {}
    if 'class="note"' in c or 'class="block"' in c:
        probs.append("残留源 class")
    if re.search(r'<a id="w\d+"></a>', c):
        probs.append("残留空锚 a#w")
    refs = re.findall(r'epub:type="noteref" href="#(m\d+)" id="(w\d+)"', c)
    notes = re.findall(r'<p class="fnote" id="(m\d+)"><a href="#(w\d+)">', c)
    if len(refs) != len(notes):
        probs.append("noteref(%d) != fnote(%d)" % (len(refs), len(notes)))
    rmap = {m: w for m, w in refs}
    for m_id, w_id in notes:
        if rmap.get(m_id) != w_id:
            probs.append("注 %s 与引用 %s 不对应" % (m_id, w_id))
            break
    for cls in set(re.findall(r'class="([^"]+)"', c)):
        for one in cls.split():
            if one not in ALLOWED_CLASSES:
                probs.append("未知 class: %s" % one)
                break
    for m in re.finditer(r'<div class="chatu">(.*?)</div>', c, re.S):
        if "<img" not in m.group(1):
            probs.append("chatu 缺图")
            break
    info = {"chatu": len(re.findall(r'<div class="chatu">', c)),
            "fnote": len(notes), "h1": len(re.findall(r"<h1", c)),
            "h2": len(re.findall(r"<h2", c)), "toc": len(re.findall(r'class="toc', c)),
            "bq": len(re.findall(r"<blockquote", c))}
    return probs, info


def verify_dir(d):
    ok = True
    files = list_files(d)
    ids = {os.path.basename(f): set(re.findall(r'\bid="([^"]+)"', read(f))) for f in files}
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs, info = verify_content(c, name)
        for m in re.finditer(r'(?:href|src)="([^"]+)"', c):
            h = m.group(1)
            if h.startswith(("http", "mailto:")) or h == "styles.css":
                continue
            fn, _, frag = h.partition("#")
            if not fn:
                continue
            p = os.path.normpath(os.path.join(os.path.dirname(fp), fn))
            if not os.path.exists(p):
                probs.append("链接目标缺失 %s" % h)
            elif frag and frag not in ids.get(os.path.basename(p), set()):
                probs.append("锚点缺失 %s" % h)
        if probs:
            ok = False
            print("%-22s FAIL: %s" % (name, "; ".join(sorted(set(probs)))))
        else:
            print("%-22s OK  %s" % (name, " ".join("%s=%d" % kv for kv in sorted(info.items()))))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---------- analyze ----------

def analyze(d, out=None):
    files = list_files(d)
    L = ["目录: %s" % d, "xhtml: %d" % len(files)]
    for key, pat in (("p.note 注文", r'<p class="note">'), ("引用 a#w", r'<a id="w\d+"></a>'),
                     ("p.block 引文", r'<p class="block">'), ("p.center 图", r'<p class="center"><img'),
                     ("p.img 图注", r'<p class="img">'), ("p.center1", r'<p class="center1">'),
                     ("p.lk", r'<p class="lk">'), ("p.left", r'<p class="left">'),
                     ("h1.front 空", r'<h1[^>]*class="front"'),
                     ("ul 目录", r"<ul>")):
        L.append("  %-14s %d" % (key, sum(len(re.findall(pat, read(f))) for f in files)))
    L.append("roles: " + ", ".join("%s=%s" % (os.path.basename(f), role_of(os.path.basename(f), read(f)))
                                  for f in files if role_of(os.path.basename(f), read(f)) != "content"))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)
    return rep


# ---------- process ----------

def process(d, dry=False):
    files = list_files(d)
    if not files:
        print("!! 未找到 *.xhtml")
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录: %s" % outdir)
    ok = True
    results = {}
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        try:
            new, role = process_file(fp)
            new = postprocess(new)
        except Exception as e:
            ok = False
            print("%-22s FAIL: %s" % (name, e))
            continue
        probs, info = verify_content(new, name)
        if probs:
            ok = False
            print("%-22s FAIL: %s" % (name, "; ".join(probs)))
            continue
        a, b = text_of(c), text_of(new)
        if a != b:
            ok = False
            print("%-22s FAIL: 文本比对不一致（%d vs %d）" % (name, len(a), len(b)))
            continue
        results[name] = new
        print("%-22s %-8s chatu=%-2d fnote=%-3d h1=%d h2=%-2d toc=%-2d bq=%-2d" % (
            name, role, info["chatu"], info["fnote"], info["h1"], info["h2"], info["toc"], info["bq"]))
    if not ok:
        print("RESULT: FAIL（有文件未通过校验，未写回）")
        return 1
    if dry:
        for name, new in results.items():
            write(os.path.join(outdir, name), new)
        print("RESULT: 预演完成（未改动原文件）")
        return 0
    for fp in files:
        shutil.copy2(fp, os.path.join(base, os.path.basename(fp)))
    for name, new in results.items():
        write(os.path.join(d, name), new)
    print("styles.css: %s" % ensure_styles(d))
    print("RESULT: OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description="calibre 简类号社科书清洗")
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
        return 1
    if a.cmd == "analyze":
        analyze(d, getattr(a, "out", None))
        return 0
    if a.cmd == "process":
        return process(d, dry=a.dry_run)
    return verify_dir(d)


if __name__ == "__main__":
    sys.exit(main())
