#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_calibre_diary.py — calibre 拆成单篇的日记体书（profile W）

识别特征（《伦敦日记》一类）:
  目录里上百个 index-1_split_*.html，每个文件一个 `<h2>`（日期），h1 是年份/单元
  `<body class="calibre">`、`<h1 class="calibre1" id="_1">`、`<h2 class="calibre4" id="712">`、
  `<p class="calibre2">`、`<hr class="calibre3"/>`、`stylesheet.css` + `page_styles.css`、
  `titlepage.xhtml`（内联 <style> + SVG 封面）、`toc.ncx` 每个文件一个 navPoint

处理:
  1) 按 h1 合并：一个 h1 一个 xhtml（h1 + 其下各 h2 + 正文），h1/h2 的 id 原样保留（ncx 靠它跳转）
  2) 封面组（h1「封面」，与封面图/扉页重复）整组删除
  3) 版权页（h1「版权页」）→ p.bodytext-noindent
  4) 作者照片（h1「作者照片」，`<p><img/>人名</p>`）→ div.chatu + caption
  5) 封底（h1「封底」，媒体书评）→ bodytext + p.right 落款 + 条间空行
  6) `<hr class="calibre3"/>` → `<hr/>` 保留；正文 → p.bodytext
  7) 重建 content.opf（manifest / spine / css / cover meta）与 toc.ncx（两级：h1 → h2）

子命令: analyze <dir> / process <dir> [--dry-run] / verify <dir>
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

SRC_RE = re.compile(r"^index-1_split_(\d+)\.html$")
DROP_GROUPS = {"封面"}


def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()


def text_of(c):
    c = re.sub(r"<head>.*?</head>", "", c, flags=re.S)
    c = re.sub(r"<[^>]+>", "", c)
    return re.sub(r"\s+", "", c)


def src_files(d):
    fs = []
    for f in os.listdir(d):
        m = SRC_RE.match(f)
        if m:
            fs.append((int(m.group(1)), f))
    return [os.path.join(d, f) for _n, f in sorted(fs)]


# ---------- 解析与分组 ----------

def parse(files):
    groups = []          # [ {h1: (id, text), items: [(h2|None, [blocks])]} ]
    cur = None
    for fp in files:
        c = read(fp)
        body = c[c.find("<body"):]
        body = re.sub(r"^<body[^>]*>", "", body)
        # 源里偶有把 <p 的 p 弄丢：`< class="calibre2">`
        body = body.replace('< class="calibre2">', '<p class="calibre2">')
        body = re.sub(r"</body>.*$", "", body, flags=re.S)
        # 源里偶有把 </p> 误写成 />（…退了出去。/> 紧跟下一个 <p>）
        # 源里偶有把 </p> 写成 </> 或 />（且前面是句末标点、紧跟下一个 <p>）
        body = re.sub(r"([。！？”』）])(?:</>|/>)(\s*)(?=<p\b)", r"\1</p>\2", body)
        h1 = re.search(r'<h1([^>]*)>(.*?)</h1>', body, re.S)
        h2 = re.search(r'<h2([^>]*)>(.*?)</h2>', body, re.S)
        if h1:
            hid = re.search(r'id="([^"]*)"', h1.group(1))
            cur = {"h1": (hid.group(1) if hid else "", plain(h1.group(2))), "items": []}
            groups.append(cur)
            body = body.replace(h1.group(0), "", 1)
        if h2:
            hid = re.search(r'id="([^"]*)"', h2.group(1))
            cur["items"].append({"h2": (hid.group(1) if hid else "", plain(h2.group(2))), "blocks": []})
            body = body.replace(h2.group(0), "", 1)
        if not cur["items"]:
            cur["items"].append({"h2": None, "blocks": []})
        blocks = cur["items"][-1]["blocks"]
        for m in re.finditer(r'<p[^>]*>(.*?)</p>|<hr[^>]*/>', body, re.S):
            if m.group(0).startswith("<hr"):
                blocks.append(("hr", None))
            else:
                blocks.append(("p", m.group(1)))
    return groups


# ---------- 各组渲染 ----------

def render_group(g, idx):
    title = g["h1"][1]
    hid = g["h1"][0]
    mode = "normal"
    if title == "版权页":
        mode = "copyright"
    elif title == "作者照片":
        mode = "photo"
    elif title == "扉页":
        mode = "titlepage"
    elif title == "封底":
        mode = "blurb"

    out = ['<h1%s>%s</h1>' % (' id="%s"' % hid if hid else "", title)]
    for it in g["items"]:
        if it["h2"]:
            out.append('<h2%s>%s</h2>' % (' id="%s"' % it["h2"][0] if it["h2"][0] else "", it["h2"][1]))
        prev_right = False
        for kind, txt in it["blocks"]:
            if kind == "hr":
                out.append("<hr/>")
                prev_right = False
                continue
            t = txt.strip()
            if mode == "photo":
                img = re.search(r'<img[^>]*src="([^"]+)"[^>]*/?>', t)
                cap = plain(re.sub(r'<img[^>]*/?>', "", t))
                if img:
                    out.append('<div class="chatu">\n<p class="image"><img src="%s" alt=""/></p>%s\n</div>'
                               % (img.group(1), ('\n<p class="caption">%s</p>' % cap) if cap else ""))
                    continue
                out.append('<p class="bodytext">%s</p>' % t)
                continue
            if mode == "titlepage":
                out.append('<p class="center">%s</p>' % t)
                continue
            if mode == "copyright":
                out.append('<p class="bodytext-noindent">%s</p>' % t)
                continue
            if mode == "blurb":
                p = plain(t)
                if p.startswith("——") and len(p) < 60:
                    out.append('<p class="right">%s</p>' % t)
                    prev_right = True
                    continue
                # 末条书评把「《某报》」直接接在段末：拆成正文 + 右对齐落款
                k = t.rfind("《")
                if len(p) > 60 and k > 0 and t.rstrip().endswith("》"):
                    if prev_right:
                        out.append('<p class="bodytext"><br/></p>')
                        prev_right = False
                    out.append('<p class="bodytext">%s</p>' % t[:k].strip())
                    out.append('<p class="right">%s</p>' % t[k:].strip())
                    prev_right = True
                    continue
                if prev_right:
                    out.append('<p class="bodytext"><br/></p>')
                    prev_right = False
                out.append('<p class="bodytext">%s</p>' % t)
                continue
            out.append('<p class="bodytext">%s</p>' % t)
    return "\n".join(out)


def process(d, dry=False):
    files = src_files(d)
    if not files:
        print("!! 未找到 index-1_split_*.html")
        return 1
    groups = parse(files)
    keep = [g for g in groups if g["h1"][1] not in DROP_GROUPS]
    print("源文件 %d，h1 组 %d，保留 %d 组（删除：%s）"
          % (len(files), len(groups), len(keep), ",".join(DROP_GROUPS)))

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(d)), stamp))
    outdir = os.path.join(base, "out") if dry else base
    os.makedirs(outdir, exist_ok=True)
    print("备份/输出目录:", outdir)

    book_title = ""
    o = read(os.path.join(d, "content.opf"))
    mt = re.search(r"<dc:title>(.*?)</dc:title>", o, re.S)
    if mt:
        book_title = plain(mt.group(1))

    docs = []          # (name, h1, [(h2id, h2text)], content)
    for i, g in enumerate(keep, 1):
        name = "part%02d.xhtml" % i
        body = render_group(g, i)
        doc = ('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh">\n'
               "<head>\n<title>%s</title>\n"
               '<link href="styles.css" rel="stylesheet" type="text/css"/>\n'
               "</head>\n<body>\n%s\n</body>\n</html>\n" % (g["h1"][1] or book_title, body))
        doc = postprocess(doc)
        docs.append((name, g["h1"], [(it["h2"][0], it["h2"][1]) for it in g["items"] if it["h2"]], doc))
        print("  %-14s <- %-26s %6d B" % (name, g["h1"][1][:24], len(doc.encode())))

    # 封面
    cover_src = os.path.join(d, "titlepage.xhtml")
    cover_doc = None
    if os.path.exists(cover_src):
        cc = read(cover_src)
        img = re.search(r'<image[^>]*xlink:href="([^"]+)"', cc)
        src = img.group(1) if img else "cover.jpeg"
        cover_doc = ('<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n<title>%s</title>\n'
                     '<link href="styles.css" rel="stylesheet" type="text/css"/>\n</head>\n'
                     '<body class="cover">\n<div><img src="%s" alt="封面"/></div>\n</body>\n</html>\n'
                     % (book_title or "封面", src))
        cover_doc = postprocess(cover_doc)

    if dry:
        for name, _h1, _h2s, doc in docs:
            write(os.path.join(outdir, name), doc)
        if cover_doc:
            write(os.path.join(outdir, "titlepage.xhtml"), cover_doc)
        print("RESULT: 预演完成（未改动原文件）")
        return 0

    # 备份并写回
    for fp in files + [cover_src]:
        if os.path.exists(fp):
            shutil.copy2(fp, os.path.join(base, os.path.basename(fp)))
    for name, _h1, _h2s, doc in docs:
        write(os.path.join(d, name), doc)
    if cover_doc:
        write(os.path.join(d, "titlepage.xhtml"), cover_doc)
    for fp in files:
        os.remove(fp)
    for css in ("stylesheet.css", "page_styles.css"):
        p = os.path.join(d, css)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(base, css))
            os.remove(p)
    print("styles.css:", ensure_styles(d))

    build_opf(d, docs, cover_doc is not None)
    build_ncx(d, docs, book_title)
    print("RESULT: OK")
    return 0


def build_opf(d, docs, has_cover):
    p = os.path.join(d, "content.opf")
    o = read(p)
    # 去掉旧的 xhtml / css manifest 项
    o = re.sub(r'\s*<item[^>]*media-type="application/xhtml\+xml"[^>]*/>', "", o)
    o = re.sub(r'\s*<item[^>]*media-type="text/css"[^>]*/>', "", o)
    # 新 xhtml 项
    items = []
    if has_cover:
        items.append('    <item href="titlepage.xhtml" id="titlepage" media-type="application/xhtml+xml"/>')
    for i, (name, _h1, _h2s, _doc) in enumerate(docs, 1):
        items.append('    <item href="%s" id="x%02d" media-type="application/xhtml+xml"/>' % (name, i))
    items.append('    <item href="styles.css" id="css" media-type="text/css"/>')
    o = o.replace("</manifest>", "\n".join(items) + "\n  </manifest>")
    # spine
    spine = []
    if has_cover:
        spine.append('    <itemref idref="titlepage"/>')
    for i in range(1, len(docs) + 1):
        spine.append('    <itemref idref="x%02d"/>' % i)
    o = re.sub(r"<spine([^>]*)>.*?</spine>",
               lambda m: "<spine%s>\n%s\n  </spine>" % (m.group(1), "\n".join(spine)), o, flags=re.S)
    write(p, o)
    print("opf: item=%d spine=%d" % (len(re.findall(r"<item\b", o)), len(re.findall(r"<itemref", o))))


def build_ncx(d, docs, book_title):
    uid = "urn:uuid:00000000-0000-0000-0000-000000000000"
    old = os.path.join(d, "toc.ncx")
    if os.path.exists(old):
        c = read(old)
        m = re.search(r'name="dtb:uid" content="([^"]+)"', c)
        if m:
            uid = m.group(1)
    total = sum(1 + len(h2s) for _n, _h1, h2s, _c in docs)
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="zh">',
             "  <head>",
             '    <meta content="%s" name="dtb:uid"/>' % uid,
             '    <meta content="2" name="dtb:depth"/>',
             '    <meta content="0" name="dtb:totalPageCount"/>',
             '    <meta content="0" name="dtb:maxPageNumber"/>',
             "  </head>",
             "  <docTitle><text>%s</text></docTitle>" % book_title,
             "  <navMap>"]
    n = 0
    for name, h1, h2s, _c in docs:
        n += 1
        lines.append('    <navPoint id="np%d" playOrder="%d">' % (n, n))
        lines.append("      <navLabel><text>%s</text></navLabel>" % h1[1])
        lines.append('      <content src="%s"/>' % name)
        for hid, text in h2s:
            n += 1
            lines.append('      <navPoint id="np%d" playOrder="%d">' % (n, n))
            lines.append("        <navLabel><text>%s</text></navLabel>" % text)
            lines.append('        <content src="%s#%s"/>' % (name, hid))
            lines.append("      </navPoint>")
        lines.append("    </navPoint>")
    lines += ["  </navMap>", "</ncx>", ""]
    write(old, "\n".join(lines))
    print("ncx: navPoint=%d（两级）" % total)


def verify_dir(d):
    ok = True
    files = sorted(glob.glob(os.path.join(d, "*.xhtml")))
    ids = {os.path.basename(f): set(re.findall(r'\bid="([^"]+)"', read(f))) for f in files}
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs = []
        try:
            ET.fromstring(c.encode("utf-8"))
        except ET.ParseError as e:
            probs.append("XML %s" % e)
        if 'class="calibre' in c:
            probs.append("残留 calibre class")
        for m in re.finditer(r'(?:href|src)="([^"]+)"', c):
            h = m.group(1)
            if h.startswith(("http", "mailto:")) or h == "styles.css":
                continue
            fn, _, frag = h.partition("#")
            p = os.path.normpath(os.path.join(d, fn))
            if not os.path.exists(p):
                probs.append("链接缺失 %s" % h)
            elif frag and frag not in ids.get(fn, set()):
                probs.append("锚点缺失 %s" % h)
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(sorted(set(probs)))))
        else:
            print("%-16s OK  %d B" % (name, len(c.encode())))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("analyze", "process", "verify"):
        sp = sub.add_parser(nm)
        sp.add_argument("dir")
        if nm == "process":
            sp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if a.cmd == "process":
        return process(d, dry=a.dry_run)
    if a.cmd == "verify":
        return verify_dir(d)
    files = src_files(d)
    print("源文件:", len(files))
    groups = parse(files)
    for g in groups:
        print("  %-30s h2=%d" % (g["h1"][1], sum(1 for it in g["items"] if it["h2"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
