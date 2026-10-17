#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_calibre.py — calibre(+多看 duokan) 源 EPUB xhtml 清洗（配置驱动）

适用的源样貌（类号因书而异，全部走 CONFIG / clean_config.json）:
  <body class="calibreN">、<div class="calibreN"> 包裹
  <p class="calibreN"><span [id] class="calibreM">正文</span></p>
  <p class="calibreN"><span class="calibreM">引文/诗句</span></p>（连续合并为 blockquote）
  插图 <div class="calibreN"><img .../></div>（+ 图注 span）；装饰图按尺寸/名单剔除
  标题 <p class="calibreN"><span class="calibreM">…</span></p> 或 <hN class="calibreM">…</hN>
  脚注 <aside epub:type="footnote" id="…"><ol class="duokan-footnote-content"><li …>注文</li></ol></aside>
       正文标记 <sup …><a epub:type="noteref" href="#…"><img … alt="…"/></a></sup>

配置：默认值见 DEFAULT_CONFIG；<dir>/clean_config.json 顶层键覆盖（-c 可另指）。
      analyze 会列出各文件的 p/span/div/hN 类号与图片尺寸，便于写配置。

子命令:
  analyze <dir> [-o REPORT]     结构普查（只读）
  process <dir> [--dry-run]     执行清洗（自动备份到 %TEMP%；--dry-run 输出到临时目录）
  verify  <dir>                 独立校验
"""
import argparse, datetime, glob, html, json, os, re, shutil, sys
import xml.etree.ElementTree as ET
from epub_clean_common import strip_sprt_between_chatu

DEFAULT_CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:style\d+|stylesheet|page_styles|fonts)\.css",
    "body_class": "calibre2",                    # 仅用于 analyze 提示；<body> 去 class 是通用行为
    "wrapper_div": "calibre3",                   # 解包该 div
    "p_para": "calibre7",                         # 段落容器 <p class="p_para">
    "body_spans": ["calibre10", "calibre26"],     # 正文 span
    "quote_spans": ["calibre23"],                 # 引文 span（连续合并 blockquote）
    "sig_span": None,                             # 引文后紧跟的落款 span -> 并入块内 <p class="right">
    "epigraph_class": "intro",                    # 章首题词（body 内本块前无 <p>/<h2>）的 blockquote class
    "poem_class": "poem",                         # 正文内带落款的引文 blockquote class（无落款则裸 blockquote）
    "lead_spans": [],                             # 整段逐字加粗 -> <p class="bodytext"><span><b>…</b></span></p>
    "head_map": {"calibre17": "h3", "calibre24": "h4", "calibre29": "h4"},  # {span/hN class: 目标标签}
    "h1_spans": ["calibre5", "calibre25"],        # <h1><span class="…"><b>…</b></span></h1> -> <h1>
    "fig_div": "calibre13",                       # 插图 div
    "caption_spans": ["calibre23"],               # 图后的图注 span（默认与 quote_spans 同——原第 2 套行为）
    "sub_span": None,                             # <sub class="…"> -> <sub>
    "italic_spans": ["calibre19", "calibre27", "calibre28"],   # 去掉 span 保留内容（<i> 保留）
    "author_span": "calibre21",                   # 正文底部署名 -> <p class="right">
    "date_span": "calibre22",                     # 正文底部日期 -> <p class="right">
    "bold_spans": [],                             # 逐字 <b class="…"> 去标签保留文字
    "cover_page": False,                          # <body><img/></body> -> <div class="chatu">
    "head_sub_relocate": {},                      # {标题class: 引导段class} 把误置于标题的 <sub> 数字挪到下一条
    "hr": True,
    "ornament_max_bytes": 51200,                  # 小于该字节数视为装饰图
    "drop_images": [],
}


def load_config(dirpath, path=None):
    p = path or os.path.join(dirpath, "clean_config.json")
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            cfg.update(json.load(f))
        return cfg, p
    return cfg, None

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

def text(inner):
    return re.sub(r"\s+", "", re.sub(r"</?[^>]+>", "", inner))

def img_keep(img):
    src = re.search(r'src="([^"]*)"', img)
    alt = re.search(r'alt="([^"]*)"', img)
    return '<img src="%s" alt="%s"/>' % (src.group(1) if src else "", alt.group(1) if alt else "")

# ---------- 步骤 ----------

def step_css(c, name, ctx, cfg):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + cfg["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if ('href="%s"' % cfg["css_href"]) not in c:
        c = re.sub(r"([ \t]*)</head>",
                   r'\1  <link href="%s" rel="stylesheet" type="text/css"/>\n\1</head>' % cfg["css_href"],
                   c, count=1)
        ctx["css"] += 1
    return c

def step_body(c, name, ctx, cfg):
    n = len(re.findall(r'<body[^>]*class="[^"]*">', c))
    ctx["body"] += n
    return re.sub(r'<body[^>]*class="[^"]*">', "<body>", c)

def step_footnotes(c, name, ctx, cfg):
    asides = []
    def aside(m):
        asides.append((m.group(1) or "", re.sub(r"</?span[^>]*>", "", m.group(2)).strip()))
        return ""
    c = re.sub(r'<aside epub:type="footnote"(?: id="([^"]*)")?><ol class="duokan-footnote-content">'
               r'<li class="duokan-footnote-item">(.*?)</li></ol></aside>\n?', aside, c, flags=re.S)
    nref_re = re.compile(r'<sup[^>]*><a epub:type="noteref" href="#([^"]*)">\s*'
                         r'<img[^>]*?alt="([^"]*)"[^>]*?/>\s*</a></sup>')
    refs = nref_re.findall(c)
    if len(refs) != len(asides):
        raise RuntimeError("%s: noteref(%d) != aside(%d)" % (name, len(refs), len(asides)))
    # 配对：优先按 id（且正文一致）；否则回退按文档顺序（源里可能有缺 id / 重复 id）
    pairs = None
    by_id = {}
    for a in asides:
        by_id.setdefault(a[0], []).append(a)
    if all(r[0] and by_id.get(r[0]) for r in refs):
        used, acc = set(), []
        for fid, alt in refs:
            cand = [a for a in by_id[fid] if a not in used]
            if not cand:
                acc = None; break
            acc.append(cand[0]); used.add(cand[0])
        pairs = acc
    if pairs is None:
        if all(html.unescape(r[1]).strip() == a[1] for r, a in zip(refs, asides)):
            pairs = asides
        else:
            raise RuntimeError("%s: 无法配对 noteref/aside" % name)
    # 生成唯一 fnote id
    used, fids = set(), []
    for i, (aid, txt) in enumerate(pairs, 1):
        fid = aid if (aid and aid not in used) else "footnote-%d" % i
        while fid in used:
            fid += "x"
        used.add(fid); fids.append((fid, txt))
    counter = iter(range(1, len(pairs) + 1))
    def nref(m):
        i = next(counter)
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%d]</a></sup>' % (fids[i-1][0], i, i)
    c = nref_re.sub(nref, c)
    for i, (fid, txt) in enumerate(fids, 1):
        ctx["fnotes"].append((fid, i, txt))
    return c

def step_sub_relocate(c, name, ctx, cfg):
    """把误置在标题里的 <sub> 数字挪到紧随其后的引导段（书本身的源缺陷，配置按需）"""
    rel = cfg.get("head_sub_relocate") or {}
    sub = cfg.get("sub_span")
    if not rel or not sub:
        return c
    pp = re.escape(cfg["p_para"])
    subre = r'<sub[^>]*class="[^"]*\b%s\b[^"]*">([^<]*)</sub>' % re.escape(sub)
    for head_cls, lead_cls in rel.items():
        pat = re.compile(r'(<p class="%s"><span[^>]*class="[^"]*\b%s\b[^"]*">)(.*?)(</span></p>)'
                         % (pp, re.escape(head_cls)), re.S)
        for m in reversed(list(pat.finditer(c))):
            inner = m.group(2)
            subs = "".join(re.findall(subre, inner))
            if not subs:
                continue
            inner2 = re.sub(subre, "", inner)
            after = c[m.end():]
            lm = re.search(r'(<p class="%s"><span[^>]*class="[^"]*\b%s\b[^"]*">)'
                           % (pp, re.escape(lead_cls)), after)
            if not lm:
                continue
            inj = "".join("<b>%s</b>" % ch for ch in subs)
            c = (c[:m.start()] + m.group(1) + inner2 + m.group(3)
                 + after[:lm.end()] + inj + after[lm.end():])
            ctx["submove"] += len(subs)
    return c

def step_heads(c, name, ctx, cfg):
    pp = re.escape(cfg["p_para"])
    for cls, tag in cfg["head_map"].items():
        # (a) <p class=p_para><span [id] class=cls>…</span></p>
        pat_a = re.compile(r'<p class="%s"><span(?: id="([^"]*)")? class="[^"]*\b%s\b[^"]*">(.*?)</span></p>'
                           % (pp, re.escape(cls)), re.S)
        def ra(m):
            ctx["heads"] += 1
            return '<%s%s>%s</%s>' % (tag, (' id="%s"' % m.group(1)) if m.group(1) else '', text(m.group(2)), tag)
        c = pat_a.sub(ra, c)
        # (b) <tag … class="…cls…" …>…</tag>
        pat_b = re.compile(r'<%s\b([^>]*)>(.*?)</%s>' % (tag, tag), re.S)
        def rb(m):
            attrs, inner = m.group(1), m.group(2)
            cm = re.search(r'class="([^"]*)"', attrs)
            if not cm or cls not in cm.group(1).split():
                return m.group(0)
            sid = re.search(r'\bid="([^"]*)"', attrs) or re.search(r'\bid="([^"]*)"', inner)
            attrs2 = re.sub(r'\s+class="[^"]*"', "", attrs)
            ctx["heads"] += 1
            return '<%s%s%s>%s</%s>' % (tag, attrs2, (' id="%s"' % sid.group(1)) if sid else "", text(inner), tag)
        c = pat_b.sub(rb, c)
    return c

def step_figures(c, name, ctx, cfg):
    d = ctx["dir"]
    fig = re.escape(cfg["fig_div"])
    caps = "|".join(re.escape(x) for x in (cfg.get("caption_spans") or []))
    cap_re = (r'(?:\s*<p class="%s"><span class="(?:%s)">(.*?)</span></p>)*'
              % (re.escape(cfg["p_para"]), caps)) if caps else r'()'
    pat = re.compile(r'<div class="%s">\s*(<img[^>]*?/>)\s*</div>%s' % (fig, cap_re), re.S)

    def is_orn(img):
        sm = re.search(r'src="([^"]*)"', img)
        if not sm:
            return False
        base = os.path.basename(sm.group(1))
        if base in (cfg.get("drop_images") or []):
            return True
        p = os.path.normpath(os.path.join(d, sm.group(1)))
        return os.path.exists(p) and os.path.getsize(p) < cfg.get("ornament_max_bytes", 0)

    def repl(m):
        img, capblock = m.group(1), (m.group(2) or "")
        caps2 = [text(x) for x in re.findall(r'<span class="[^"]*">(.*?)</span>', capblock, re.S)]
        orn = is_orn(img)
        if orn:
            adj = (bool(re.search(r"</h[1-4]>\s*(?:</div>\s*|<div[^>]*>\s*)*$", c[:m.start()]))
                   or bool(re.match(r"\s*(?:<div[^>]*>\s*)*<h[1-4][^>]*>", c[m.end():])))
            if adj:
                ctx["drop_orn"] += 1
                return ""
            ctx["sprt"] += 1
            out = '<p class="sprt">%s</p>' % img_keep(img)
        else:
            ctx["chatu"] += 1
            out = '<div class="chatu">\n<p class="image">%s</p>' % img_keep(img)
        if caps2:
            out += '\n<p class="caption">%s</p>' % "<br/>".join(caps2)
        return out + ("" if orn else "\n</div>")
    c = pat.sub(repl, c)

    # 仅含一图的包裹 div（扉页）
    pat2 = re.compile(r'<div id="[^"]*" class="%s">\s*(<img[^>]*?/>)\s*</div>' % re.escape(cfg["wrapper_div"]), re.S)
    def repl2(m):
        if is_orn(m.group(1)):
            ctx["drop_orn"] += 1
            return ""
        ctx["chatu"] += 1
        return '<div class="chatu">\n<p class="image">%s</p>\n</div>' % img_keep(m.group(1))
    return pat2.sub(repl2, c)

def step_quotes(c, name, ctx, cfg):
    pp = re.escape(cfg["p_para"])
    qs = "|".join(re.escape(x) for x in cfg["quote_spans"])
    pat = re.compile(r'<p class="%s"><span class="(?:%s)">(.*?)</span></p>' % (pp, qs), re.S)
    ms = list(pat.finditer(c))
    if not ms:
        return c
    body_start = c.find("<body")
    groups, cur = [], [ms[0]]
    for prev, m in zip(ms, ms[1:]):
        if c[prev.end():m.start()].strip() == "":
            cur.append(m)
        else:
            groups.append(cur); cur = [m]
    groups.append(cur)
    sig = None
    if cfg.get("sig_span"):
        sig = re.compile(r'\s*<p class="%s"><span class="%s">(.*?)</span></p>'
                         % (pp, re.escape(cfg["sig_span"])), re.S)
    for g in reversed(groups):
        start, end = g[0].start(), g[-1].end()
        first = not re.search(r'<p\b|<h2\b', c[body_start:start])
        body = "\n".join('<p class="bodytext">%s</p>' % x.group(1) for x in g)
        sm = sig.match(c, end) if sig else None
        if sm:
            end = sm.end()
            cls = cfg["epigraph_class"] if first else cfg["poem_class"]
            block = ('<blockquote%s>\n%s\n<p class="right">%s</p>\n</blockquote>'
                     % ((' class="%s"' % cls) if cls else "", body, sm.group(1).strip()))
        elif first and cfg.get("epigraph_class"):
            block = '<blockquote class="%s">\n%s\n</blockquote>' % (cfg["epigraph_class"], body)
        else:
            block = "<blockquote>\n%s\n</blockquote>" % body
        c = c[:start] + block + c[end:]
        ctx["quotes"] += len(g)
    return c

def step_lead(c, name, ctx, cfg):
    if not cfg.get("lead_spans"):
        return c
    ls = "|".join(re.escape(x) for x in cfg["lead_spans"])
    pat = re.compile(r'<p class="%s"><span(?: id="([^"]*)")? class="(?:%s)">(.*?)</span></p>'
                     % (re.escape(cfg["p_para"]), ls), re.S)
    def repl(m):
        ctx["lead"] += 1
        return '<p class="bodytext"%s><span><b>%s</b></span></p>' % (
            (' id="%s"' % m.group(1)) if m.group(1) else "", text(m.group(2)))
    return pat.sub(repl, c)

def step_bodytext(c, name, ctx, cfg):
    bs = "|".join(re.escape(x) for x in cfg["body_spans"])
    pat = re.compile(r'<p class="%s"><span(?: id="([^"]*)")? class="(?:%s)">(.*?)</span></p>'
                     % (re.escape(cfg["p_para"]), bs), re.S)
    def repl(m):
        ctx["bodytext"] += 1
        return '<p class="bodytext"%s>%s</p>' % ((' id="%s"' % m.group(1)) if m.group(1) else "", m.group(2))
    return pat.sub(repl, c)

def step_sub(c, name, ctx, cfg):
    if not cfg.get("sub_span"):
        return c
    n = len(re.findall(r'<sub[^>]*class="[^"]*\b%s\b[^"]*">' % re.escape(cfg["sub_span"]), c))
    ctx["sub"] += n
    return re.sub(r'<sub[^>]*class="[^"]*\b%s\b[^"]*">' % re.escape(cfg["sub_span"]), "<sub>", c)

def step_italic(c, name, ctx, cfg):
    if not cfg.get("italic_spans"):
        return c
    alts = "|".join(re.escape(x) for x in cfg["italic_spans"])
    pat = re.compile(r'<span class="(?:%s)">(.*?)</span>' % alts, re.S)
    ctx["italic"] += len(pat.findall(c))
    return pat.sub(r"\1", c)

def step_author_date(c, name, ctx, cfg):
    for key in ("author_span", "date_span"):
        cls = cfg.get(key)
        if cls:
            c = re.sub(r'<p class="%s"><span class="%s">(.*?)</span></p>'
                       % (re.escape(cfg["p_para"]), re.escape(cls)), r'<p class="right">\1</p>', c, flags=re.S)
    if cfg.get("author_span") or cfg.get("date_span"):
        i = c.find('<p class="right">')
        if i > 0:
            before = c[:i].rstrip()
            if before.endswith("</p>") and not before.endswith('<p class="bodytext"><br/></p>'):
                c = c[:i] + '<p class="bodytext"><br/></p>\n' + c[i:]
                ctx["signature"] += 1
    return c

def step_h1(c, name, ctx, cfg):
    title = (re.search(r"<title>(.*?)</title>", c, re.S) or [None, ""])[1].strip()
    title_attr = title.replace("&", "&amp;").replace('"', "&quot;")

    def repl_img(m):
        attrs, img = m.group(1), m.group(2)
        attrs = re.sub(r'\s+class="[^"]*"', "", attrs)
        ctx["h1"] += 1
        return '<h1%s title="%s">\n\t%s</h1>' % (attrs, title_attr, img_keep(img))
    c = re.sub(r"<h1([^>]*)>\s*(<img[^>]*?/>)\s*</h1>", repl_img, c, flags=re.S)

    hs = "|".join(re.escape(x) for x in (cfg.get("h1_spans") or []))
    if hs:
        def repl_txt(m):
            ctx["h1"] += 1
            return "<h1%s>%s</h1>" % ((' id="%s"' % m.group(1)) if m.group(1) else "", text(m.group(2)))
        c = re.sub(r'<h1[^>]*>\s*<span(?: id="([^"]*)")? class="(?:%s)">\s*(.*?)\s*</span>\s*</h1>' % hs,
                   repl_txt, c, flags=re.S)
    return c

def step_strip_b(c, name, ctx, cfg):
    if not cfg.get("bold_spans"):
        return c
    bs = "|".join(re.escape(x) for x in cfg["bold_spans"])
    pat = re.compile(r'<b[^>]*class="[^"]*\b(?:%s)\b[^"]*">(.*?)</b>' % bs, re.S)
    while True:
        c, n = pat.subn(r"\1", c)
        ctx["stripb"] += n
        if not n:
            break
    return c

def step_strip_spans(c, name, ctx, cfg):
    """清除残余的 calibre span（含嵌套）"""
    pat = re.compile(r'<span(?: id="([^"]*)")? class="calibre[^"]*">((?:(?!<span).)*?)</span>', re.S)
    while True:
        c, k = pat.subn(
            lambda m: ('<span id="%s">%s</span>' % (m.group(1), m.group(2))) if m.group(1) else m.group(2), c)
        ctx["spans"] += k
        if not k:
            break
    return c

def step_cover(c, name, ctx, cfg):
    if not cfg.get("cover_page"):
        return c
    m = re.search(r'<body>\s*<img([^>]*?)/>\s*</body>', c, re.S)
    if not m:
        return c
    ctx["cover"] += 1
    return c[:m.start()] + ('<body>\n<div class="chatu">\n<p class="image">%s</p>\n</div>\n</body>'
                            % img_keep(m.group(1))) + c[m.end():]

def step_unwrap(c, name, ctx, cfg):
    open_re = re.compile(r'<div[^>]*\bclass="%s"[^>]*>' % re.escape(cfg["wrapper_div"]))
    token_re = re.compile(r"<div\b[^>]*>|</div>")
    while True:
        m = open_re.search(c)
        if not m:
            break
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = token_re.search(c, j)
            if not m2:
                raise RuntimeError("%s: div 不配对" % name)
            depth += -1 if m2.group(0).startswith("</") else 1
            j = m2.end(); close = m2
        a, b = m.start(), m.end()
        if c[b:b + 1] == "\n":
            b += 1
        cs, ce = close.start(), close.end()
        if c[cs - 1:cs] == "\n" and c[ce:ce + 1] in ("", "\n"):
            cs -= 1
        c = c[:a] + c[b:cs] + c[ce:]
        ctx["unwrap"] += 1
    return c

def step_join(c, name, ctx, cfg):
    def repl(m):
        open_tag, inner = m.group(1), m.group(2)
        if "\n" not in inner:
            return m.group(0)
        ctx["join"] += 1
        inner = re.sub(r"\n[ \t]*(?=<)", "", inner)
        inner = re.sub(r"\n[ \t]*", " ", inner)
        return open_tag + inner + "</p>"
    return re.sub(r"(<p\b[^>]*>)(.*?)</p>", repl, c, flags=re.S)

def step_tidy(c, name, ctx, cfg):
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        head = re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0))
        c = c[:hm.start()] + head + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        ctx["blank"] += len(re.findall(r"^[ \t]*\n", body, re.M))
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        c = pre + body
    return c

def step_append(c, name, ctx, cfg):
    if not ctx["fnotes"]:
        return c
    head = "<hr/>\n" if cfg["hr"] else ""
    block = head + "\n".join('<p class="fnote" id="%s"><a href="#noteref-%d">[%d]</a> %s</p>' % (fid, i, i, txt)
                             for fid, i, txt in ctx["fnotes"]) + "\n"
    return c.replace("</body>", block + "</body>")

STEP_ORDER = ["css", "body", "footnotes", "sub_relocate", "heads", "figures", "quotes",
              "lead", "bodytext", "sub", "italic", "author_date", "h1",
              "strip_b", "strip_spans", "cover", "unwrap", "join", "tidy", "append"]
BUILTIN = {"css": step_css, "body": step_body, "footnotes": step_footnotes,
           "sub_relocate": step_sub_relocate, "heads": step_heads, "figures": step_figures,
           "quotes": step_quotes, "lead": step_lead, "bodytext": step_bodytext, "sub": step_sub,
           "italic": step_italic, "author_date": step_author_date, "h1": step_h1,
           "strip_b": step_strip_b, "strip_spans": step_strip_spans, "cover": step_cover,
           "unwrap": step_unwrap, "join": step_join, "tidy": step_tidy, "append": step_append}

def new_ctx(d):
    c = dict.fromkeys(["css", "body", "nref", "heads", "chatu", "drop_orn", "sprt", "quotes",
                       "lead", "bodytext", "sub", "italic", "h1", "stripb", "spans", "cover",
                       "unwrap", "join", "blank", "submove", "signature"], 0)
    c["dir"] = d
    c["fnotes"] = []
    return c

# ---------- 校验 ----------

def verify_content(c, name, cfg, dirpath):
    probs = []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e]
    if "<aside" in c or "duokan-footnote" in c:
        probs.append("残留 duokan 脚注")
    if "epub-footnote" in c:
        probs.append("残留脚注图标")
    if re.search(r'class="calibre', c):
        probs.append("残留 calibre 类")
    if re.search(r"<body[^>]*class=", c):
        probs.append("body 仍有 class")
    if re.search(r'href="[^"]*' + cfg["drop_css_re"] + r'"', c):
        probs.append("残留旧 css 链接")
    if ('href="%s"' % cfg["css_href"]) not in c:
        probs.append("缺少 %s 链接" % cfg["css_href"])
    if re.search(r"<span style=", c):
        probs.append("残留内联样式 span")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    for src in re.findall(r'<img[^>]*?src="([^"]+)"', c):
        if not os.path.exists(os.path.normpath(os.path.join(dirpath, src))):
            probs.append("图片不存在 %s" % src)
    nums = [int(x) for x in re.findall(r'id="noteref-(\d+)"', c)]
    if nums != list(range(1, len(nums) + 1)):
        probs.append("noteref 编号不连续")
    fn = len(re.findall(r'<p class="fnote"', c))
    if fn != len(nums):
        probs.append("fnote(%d) != noteref(%d)" % (fn, len(nums)))
    if (fn > 0) != (len(re.findall(r"<hr/>", c)) == 1):
        probs.append("hr 与脚注列表不一致")
    return probs

# ---------- analyze ----------

def analyze(dirpath, out=None, cfgpath=None):
    cfg, used = load_config(dirpath, cfgpath)
    L = ["# analyze(calibre): %s" % dirpath, "配置文件: %s" % (used or "无（默认）"), ""]
    files = list_files(dirpath)
    import collections
    pc = collections.Counter(); sc = collections.Counter(); dc = collections.Counter(); hc = collections.Counter()
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        a = len(re.findall(r'<aside epub:type="footnote"', c))
        n = len(re.findall(r'epub:type="noteref"', c))
        f = len(re.findall(r'<div class="%s">' % re.escape(cfg["fig_div"]), c))
        for k, v in collections.Counter(re.findall(r'<p class="([^"]+)"', c)).items():
            pc[k] += v
        for k, v in collections.Counter(re.findall(r'<span(?: id="[^"]*")? class="([^"]+)"', c)).items():
            sc[k] += v
        for k, v in collections.Counter(re.findall(r'<div[^>]*class="([^"]+)"', c)).items():
            dc[k] += v
        for k, v in collections.Counter(re.findall(r'<(h[1-6])\b[^>]*class="([^"]+)"', c)).items():
            hc[k] += v
        tot["aside"] += a; tot["nref"] += n
        L.append("%-18s title=%-20s aside=%-3d nref=%-3d fig=%-3d p:%s span:%s" % (
            name, (re.search(r"<title>(.*?)</title>", c, re.S) or [None, "?"])[1][:20], a, n, f,
            ",".join("%s x%d" % kv for kv in collections.Counter(re.findall(r'<p class="([^"]+)"', c)).most_common(4)),
            ",".join("%s x%d" % kv for kv in collections.Counter(re.findall(r'<span(?: id="[^"]*")? class="([^"]+)"', c)).most_common(5))))
    L.append("")
    L.append("== 汇总: files=%d aside=%d noteref=%d" % (len(files), tot["aside"], tot["nref"]))
    L.append("== p 类: %s" % ", ".join("%s x%d" % kv for kv in pc.most_common()))
    L.append("== span 类: %s" % ", ".join("%s x%d" % kv for kv in sc.most_common()))
    L.append("== div 类: %s" % ", ".join("%s x%d" % kv for kv in dc.most_common()))
    L.append("== hN 类: %s" % ", ".join("%s x%d" % kv for kv in hc.most_common()))
    used_imgs = collections.Counter()
    for fp in files:
        for src in re.findall(r'<img[^>]*?src="([^"]+)"', read(fp)):
            used_imgs[src] += 1
    L.append("== 引用图片（小/重复多者多为装饰图或脚注图标）:")
    for src, n in sorted(used_imgs.items(), key=lambda x: os.path.getsize(os.path.normpath(os.path.join(dirpath, x[0])))
                         if os.path.exists(os.path.normpath(os.path.join(dirpath, x[0]))) else 0):
        p = os.path.normpath(os.path.join(dirpath, src))
        L.append("   x%-3d %8d  %s" % (n, os.path.getsize(p) if os.path.exists(p) else -1, src))
    rep = "\n".join(L) + "\n"
    if out:
        open(out, "w", encoding="utf-8", newline="").write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

# ---------- process / verify ----------

def process(dirpath, dry=False, cfgpath=None):
    cfg, used = load_config(dirpath, cfgpath)
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml")
        sys.exit(1)
    print("配置: %s" % (used or "默认"))
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
        ctx = new_ctx(dirpath)
        for s in STEP_ORDER:
            c = BUILTIN[s](c, name, ctx, cfg)
        c = strip_sprt_between_chatu(c)
        probs = verify_content(c, name, cfg, dirpath)
        if probs:
            ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-18s chatu=%-2d orn=%-2d sprt=%-2d fnote=%-3d heads=%-3d quote=%-3d lead=%-3d body=%-4d sub=%-2d stripb=%-2d cover=%-d unwrap=%-2d" % (
            name, ctx["chatu"], ctx["drop_orn"], ctx["sprt"], len(ctx["fnotes"]), ctx["heads"],
            ctx["quotes"], ctx["lead"], ctx["bodytext"], ctx["sub"], ctx["stripb"], ctx["cover"], ctx["unwrap"]))
    print("RESULT:", "OK" if ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if ok else 1)

def verify_dir(dirpath, cfgpath=None):
    cfg, used = load_config(dirpath, cfgpath)
    ok = True
    for fp in list_files(dirpath):
        name = os.path.basename(fp)
        probs = verify_content(read(fp), name, cfg, dirpath)
        if probs:
            ok = False
            print("%-18s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-18s OK" % name)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser(description="calibre(duokan) 源 xhtml 清洗（配置驱动）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("analyze", "process", "verify"):
        sp = sub.add_parser(nm)
        sp.add_argument("dir")
        sp.add_argument("-c", "--config")
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
        analyze(d, out=getattr(a, "out", None), cfgpath=a.config)
    elif a.cmd == "process":
        process(d, dry=a.dry_run, cfgpath=a.config)
    else:
        verify_dir(d, cfgpath=a.config)

if __name__ == "__main__":
    main()
