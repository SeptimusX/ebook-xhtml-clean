#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean.py — EPUB xhtml 清洗流水线（得到/中华书局系 xhtml → 标准 bodytext/fnote/chatu 格式）

子命令:
  analyze <dir> [-c CONFIG] [-o REPORT]   结构普查（不做任何修改），输出体检报告
  process <dir> [-c CONFIG] [--dry-run]   执行清洗（自动备份到临时目录；--dry-run 只输出不写回）
  verify  <dir> [-c CONFIG]               对已处理文件做独立校验

配置: 默认 <dir>/clean_config.json（可用 -c 指定），未提供的键用内置默认值。
自定义步骤: <dir>/custom_clean.py 可定义 extra_steps() -> [(name, fn)]，
  fn(content, ctx) -> content；插入位置由 config "custom_steps_position" 决定
  （值为某个内置步骤名=该步骤之后，"pre"=最前，"post"=最后，默认 "post"）。
"""
import argparse, datetime, glob, html, importlib.util, json, os, re, shutil, sys
import xml.etree.ElementTree as ET

DEFAULT_CONFIG = {
    "css_href": "styles.css",
    "pre_strip_span_styles": [],           # 原始 style 串（与文件中逐字一致，含 &#39; 等实体）；
                                           # 仅当 style 是 span 唯一属性时删除，span 变 <span>
    "inline_glyph_map": {},                # 内嵌生僻字图片 → 实际字符，如 {"image_003.svg": "字"}；
                                           # analyze 会列出内嵌 SVG，逐个辨识后写入（可查上下文/询问用户）
    "unwrap_div_class_re": "header|part",  # class 命中该正则的 div 解包（保留内容）
    "chatu": {"enabled": True, "div_style": "display: block;text-align:center;"},
    "footnotes": {"enabled": True, "hr": True},
    "blockquote_quotes": {"enabled": True, "style_marker": "FZFangSong",
                          "bodytext_p": True},   # 引文段在 blockquote 内保留 bodytext class
    "h1_subtitle": {"enabled": True,
                    "style_marker": "display: block;text-align:center"},  # h1 后紧跟的居中样式段并入 h1
    "bold_bodytext": {"enabled": True},     # 整段加粗引导段 → <p class="bodytext"><span><b>…</b></span></p>；
                                            # 行内嵌套加粗 span 去 style（保留 span/b）
    "bodytext": {"enabled": True, "plain_span": True, "id_style_span": True},
    "join_multiline_p": {"enabled": True},  # 跨行段落合并为单行（内嵌 SVG 生僻字图片行并入正文）
    "h_fix": {"enabled": True, "levels": [1, 2, 3], "strip_span_style": True},
    "custom_steps_position": "post",
}

STEP_ORDER = ["pre_strip", "inline_glyphs", "chatu", "footnotes", "blockquote_quotes",
              "unwrap", "h1_subtitle", "bold_bodytext", "bodytext", "join_multiline_p",
              "h_fix", "css_link", "append_fnotes"]

# ---------- 基础工具 ----------

def deep_merge(base, extra):
    out = json.loads(json.dumps(base))
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out

def load_config(dirpath, config_path=None):
    path = config_path or os.path.join(dirpath, "clean_config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return deep_merge(DEFAULT_CONFIG, json.load(f)), path
    return json.loads(json.dumps(DEFAULT_CONFIG)), None

def list_files(dirpath):
    return sorted(f for f in glob.glob(os.path.join(dirpath, "*.xhtml"))
                  if not f.endswith(".bak"))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")   # 统一 LF

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

# ---------- 处理步骤（顺序不可变，见 SKILL.md 说明） ----------

def step_pre_strip(c, name, cfg, ctx):
    n = 0
    for s in cfg.get("pre_strip_span_styles") or []:
        pat = re.compile(r'<span style="' + re.escape(s) + r'">')
        c, k = pat.subn("<span>", c)
        n += k
    ctx["pre_strip"] += n
    return c

def step_inline_glyphs(c, name, cfg, ctx):
    """内嵌生僻字图片（SVG）替换为实际 Unicode 字符（映射见 inline_glyph_map）"""
    for img_name, ch in (cfg.get("inline_glyph_map") or {}).items():
        pat = re.compile(r'<img[^>]*src="[^"]*/' + re.escape(img_name) + r'"[^>]*/>')
        ctx["glyphs"] += len(pat.findall(c))
        c = pat.sub(lambda m: ch, c)
    return c

def step_chatu(c, name, cfg, ctx):
    rule = cfg["chatu"]
    if not rule.get("enabled"):
        return c
    style = rule.get("div_style", "display: block;text-align:center;")
    # 注意：img 与 </div> 通常同一行（alt=""/></div>），caption 紧随其后一行
    pat = re.compile(
        r'<div style="' + re.escape(style) + r'">\n'
        r'(<img[^>]*?src="([^"]+)"[^>]*?/>)</div>\n'
        r'<p><span[^>]*>(.*?)</span></p>((?:</div>)*)')

    def repl(m):
        img_tag, src, caption, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        altm = re.search(r'alt="([^"]*)"', img_tag)
        alt = altm.group(1) if altm else ""
        ctx["chatu"] += 1
        return ('<div class="chatu">\n'
                '<p class="image"><img src="%s" alt="%s"/></p>\n'
                '<p class="caption">%s</p>\n'
                '</div>%s') % (src, alt, caption, tail)

    return pat.sub(repl, c)

def step_footnotes(c, name, cfg, ctx):
    if not cfg["footnotes"].get("enabled"):
        return c
    asides = []

    def aside_repl(m):
        asides.append((m.group(1), m.group(2)))
        return ""

    c = re.sub(r'<aside epub:type="footnote" id="([^"]+)">(.*?)</aside>\n?',
               aside_repl, c)
    pool = [{"id": aid, "text": txt, "used": False} for aid, txt in asides]

    noteref_re = re.compile(
        r'<sup><a epub:type="noteref" href="#([^"]+)">\s*'
        r'<img[^>]*?alt="([^"]*)"[^>]*?/>\s*</a></sup>')
    used_out = {}

    def noteref_repl(m):
        fid, alt = m.group(1), m.group(2)
        alt_u = html.unescape(alt).strip()
        cands = [a for a in pool if not a["used"] and a["id"] == fid]
        pick = None
        for a in cands:                       # alt 文本与 aside 正文精确匹配优先（重复 id 消歧）
            if html.unescape(a["text"]).strip() == alt_u:
                pick = a
                break
        if pick is None and cands:
            pick = cands[0]
        if pick is None:
            raise RuntimeError("%s: noteref #%s 找不到匹配的 aside (alt=%s...)" % (name, fid, alt[:30]))
        pick["used"] = True
        n = len(ctx["fnotes"]) + 1
        k = used_out.get(fid, 0) + 1          # 重复 id 输出时加 -2/-3 后缀，保证 id 唯一
        used_out[fid] = k
        out_id = fid if k == 1 else "%s-%d" % (fid, k)
        ctx["fnotes"].append((n, out_id, pick["text"].strip()))
        return '<sup><a epub:type="noteref" href="#%s" id="noteref-%d">[%d]</a></sup>' % (out_id, n, n)

    c = noteref_re.sub(noteref_repl, c)
    leftover = [a["id"] for a in pool if not a["used"]]
    if leftover:
        raise RuntimeError("%s: 有 aside 未被任何 noteref 引用: %s" % (name, leftover[:5]))
    return c

def step_blockquote_quotes(c, name, cfg, ctx):
    rule = cfg["blockquote_quotes"]
    if not rule.get("enabled"):
        return c
    marker = rule.get("style_marker", "FZFangSong")
    pfmt = '<p class="bodytext">%s</p>' if rule.get("bodytext_p", True) else "<p>%s</p>"
    # 整段样式 span 的引文段（位置法分组不依赖行结构，可容忍多行段落）
    pat = re.compile(r'<p><span style="[^"]*' + re.escape(marker) + r'[^"]*">(.*?)</span></p>', re.S)
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
        block = "<blockquote>\n" + "\n".join(pfmt % m.group(1) for m in g) + "\n</blockquote>"
        c = c[:start] + block + c[end:]
        ctx["fs_quotes"] += len(g)
    return c

def step_unwrap(c, name, cfg, ctx):
    if not cfg.get("unwrap_div_class_re"):
        return c
    open_re = re.compile(r'<div[^>]*\bclass="[^"]*(?:%s)[^"]*"[^>]*>' % cfg["unwrap_div_class_re"])
    token_re = re.compile(r"<div\b[^>]*>|</div>")
    n = 0
    while True:
        m = open_re.search(c)
        if not m:
            break
        depth, j, close = 1, m.end(), None
        while depth:
            m2 = token_re.search(c, j)
            if not m2:
                raise RuntimeError("%s: div 不配对" % name)
            if m2.group(0).startswith("</"):
                depth -= 1
            else:
                depth += 1
            j = m2.end()
            close = m2
        start, after_open = m.start(), m.end()
        if c[after_open:after_open + 1] == "\n":
            after_open += 1
        cs, ce = close.start(), close.end()
        if c[cs - 1:cs] == "\n" and c[ce:ce + 1] in ("", "\n"):
            cs -= 1
        c = c[:start] + c[after_open:cs] + c[ce:]
        n += 1
    ctx["unwrapped"] += n
    return c

def step_h1_subtitle(c, name, cfg, ctx):
    """h1 后紧跟的居中样式副标题段 → 并入 h1：<h1>标题<br/><span class="subtitle">副题</span></h1>"""
    rule = cfg.get("h1_subtitle", {})
    if not rule.get("enabled"):
        return c
    marker = rule.get("style_marker", "display: block;text-align:center")
    pat = re.compile(
        r'<h1>(.*?)</h1>\n'
        r'<p><span style="[^"]*' + re.escape(marker) + r'[^"]*">(.*?)</span></p>', re.S)

    def repl(m):
        title = re.sub(r"<[^>]+>", "", m.group(1))   # 去掉 h1 内的 span/b 等标签，只留文字
        ctx["subtitle"] += 1
        return '<h1>%s<br/><span class="subtitle">%s</span></h1>' % (title, m.group(2))

    return pat.sub(repl, c)

def step_bold_bodytext(c, name, cfg, ctx):
    """整段加粗引导段 → <p class="bodytext"><span><b>…</b></span></p>；
    行内嵌套加粗 span 去 style（保留 span 与 b）"""
    rule = cfg.get("bold_bodytext", {})
    if not rule.get("enabled", True):
        return c
    pat = re.compile(r'<p><span style="[^"]*font-weight: bold[^"]*">(.*?)</span></p>', re.S)
    n = len(pat.findall(c))
    c = pat.sub(lambda m: '<p class="bodytext"><span>%s</span></p>' % m.group(1), c)
    pat2 = re.compile(r'<span style="[^"]*font-weight: bold[^"]*">')
    n += len(pat2.findall(c))
    c = pat2.sub("<span>", c)
    ctx["bold"] += n
    return c

def step_bodytext(c, name, cfg, ctx):
    rule = cfg["bodytext"]
    if not rule.get("enabled"):
        return c
    n = 0
    if rule.get("plain_span"):
        # 非锚定 + dotall：段内可能内嵌 SVG 生僻字图片而跨行
        pat = re.compile(r"<p><span>(.*?)</span></p>", re.S)
        n += len(pat.findall(c))
        c = pat.sub(lambda m: '<p class="bodytext">%s</p>' % m.group(1), c)
    if rule.get("id_style_span"):
        pat = re.compile(r'<p><span (id="[^"]+") style="[^"]*">(.*?)</span></p>', re.S)
        n += len(pat.findall(c))
        c = pat.sub(lambda m: '<p class="bodytext"><span %s>%s</span></p>' % (m.group(1), m.group(2)), c)
    ctx["bodytext"] += n
    return c

def step_join_multiline_p(c, name, cfg, ctx):
    """跨行段落合并为单行（源文件里内嵌 SVG 生僻字图片常使段落断行）"""
    if not cfg.get("join_multiline_p", {}).get("enabled", True):
        return c

    def repl(m):
        if "\n" not in m.group(1):
            return m.group(0)
        ctx["joined"] += 1
        return m.group(0).replace("\n", "")

    return re.sub(r"<p\b[^>]*>(.*?)</p>", repl, c, flags=re.S)

def step_h_fix(c, name, cfg, ctx):
    rule = cfg["h_fix"]
    if not rule.get("enabled"):
        return c
    lv = "".join(str(x) for x in rule.get("levels", [1, 2, 3]))
    nb = [0]

    def fix(m):
        t = m.group(0)
        nb[0] += len(re.findall(r"</?b(?:\s[^>]*)?>", t))
        t = re.sub(r"</?b(?:\s[^>]*)?>", "", t)
        if rule.get("strip_span_style", True):
            t = re.sub(r'(<span[^>]*?)\s+style="[^"]*"', r"\1", t)
        return t

    c = re.sub(r"<h[%s][^>]*>.*?</h[%s]>" % (lv, lv), fix, c, flags=re.S)
    ctx["h_b"] += nb[0]
    return c

def step_css_link(c, name, cfg, ctx):
    href = cfg.get("css_href")
    if not href or ('href="%s"' % href) in c:
        return c
    return re.sub(r"([ \t]*)</head>",
                  r'\1  <link rel="stylesheet" type="text/css" href="%s"/>\n\1</head>' % href,
                  c, count=1)

def step_append_fnotes(c, name, cfg, ctx):
    fnotes = ctx.get("fnotes") or []
    if not fnotes or not cfg["footnotes"].get("enabled"):
        return c
    head = "<hr/>\n" if cfg["footnotes"].get("hr", True) else ""
    block = head + "\n".join(
        '<p class="fnote" id="%s"><a href="#noteref-%d">[%d]</a> %s</p>' % (oid, n, n, txt)
        for n, oid, txt in fnotes) + "\n"
    return c.replace("</body>", block + "</body>")

BUILTIN_STEPS = {
    "pre_strip": step_pre_strip, "inline_glyphs": step_inline_glyphs,
    "chatu": step_chatu, "footnotes": step_footnotes,
    "blockquote_quotes": step_blockquote_quotes, "unwrap": step_unwrap,
    "h1_subtitle": step_h1_subtitle, "bold_bodytext": step_bold_bodytext,
    "bodytext": step_bodytext, "join_multiline_p": step_join_multiline_p,
    "h_fix": step_h_fix, "css_link": step_css_link,
    "append_fnotes": step_append_fnotes,
}

def load_custom(dirpath):
    p = os.path.join(dirpath, "custom_clean.py")
    if not os.path.exists(p):
        return []
    spec = importlib.util.spec_from_file_location("custom_clean", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    steps = mod.extra_steps()
    if not isinstance(steps, list) or not all(
            isinstance(t, tuple) and len(t) == 2 for t in steps):
        raise RuntimeError("custom_clean.py: extra_steps() 须返回 [(name, fn)]")
    return steps

# ---------- 校验 ----------

def verify_content(c, name, cfg, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], info
    if cfg["footnotes"].get("enabled"):
        if "<aside" in c:
            probs.append("残留 aside")
        if "epub-footnote" in c:
            probs.append("残留脚注图标 img")
    for img_name in (cfg.get("inline_glyph_map") or {}):
        if ("/" + img_name) in c:
            probs.append("残留字图 %s" % img_name)
    if cfg["chatu"].get("enabled"):
        style = cfg["chatu"].get("div_style", "display: block;text-align:center;")
        if ('<div style="%s"' % style) in c:
            probs.append("残留插图 div")
    if cfg["blockquote_quotes"].get("enabled"):
        if cfg["blockquote_quotes"].get("style_marker") in c:
            probs.append("残留引文样式 span")
    if cfg["bold_bodytext"].get("enabled", True) and re.search(
            r'<span style="[^"]*font-weight: bold', c):
        probs.append("残留加粗样式 span")
    if cfg["bodytext"].get("enabled"):
        if cfg["bodytext"].get("plain_span") and "<p><span>" in c:
            probs.append("残留无属性 span 段落")
        if cfg["bodytext"].get("id_style_span") and re.search(r'<p><span id="[^"]+" style=', c):
            probs.append("残留 id+style span 段落")
    if cfg.get("unwrap_div_class_re") and re.search(
            r'<div[^>]*\bclass="[^"]*(?:%s)[^"]*"' % cfg["unwrap_div_class_re"], c):
        probs.append("残留 header/part div")
    if cfg["h_fix"].get("enabled"):
        lv = "".join(str(x) for x in cfg["h_fix"].get("levels", [1, 2, 3]))
        for hm in re.finditer(r"<h[%s][^>]*>(.*?)</h[%s]>" % (lv, lv), c, re.S):
            if re.search(r"<b(?:\s[^>]*)?>|</b>", hm.group(1)):   # 注意排除 <br/>
                probs.append("h 标签内残留 b")
                break
    if cfg.get("css_href") and ('href="%s"' % cfg["css_href"]) not in c:
        probs.append("缺少 css 链接")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for href in re.findall(r'href="#([^"]+)"', c):
        if href not in ids:
            probs.append("悬空链接 #%s" % href)
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
    info.append("styled-p=%d" % len(re.findall(r"<p><span ", c)))
    return probs, info

# ---------- analyze ----------

def analyze(dirpath, cfg, out=None):
    L = []

    def w(s=""):
        L.append(s)

    w("# analyze: %s" % dirpath)
    w("配置文件: %s" % ("clean_config.json（已加载）" if os.path.exists(
        os.path.join(dirpath, "clean_config.json")) else "无（用默认）"))
    files = list_files(dirpath)
    if not files:
        w("!! 未找到 *.xhtml（.bak 已排除）")
        return
    tot = dict(asides=0, noterefs=0, chatu=0, fs=0)
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        w()
        w("== %s (%d bytes)" % (name, len(c.encode("utf-8"))))
        raw = open(fp, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            w("   !! BOM 存在")
        if b"\r\n" in raw:
            w("   !! CRLF 行尾存在")
        named = set(re.findall(r"&([a-zA-Z]+);", c)) - {"amp", "lt", "gt", "quot", "apos"}
        if named:
            w("   !! 命名实体（XML 不安全）: %s" % sorted(named))
        # aside / noteref
        asides = re.findall(r'<aside epub:type="footnote" id="([^"]+)">(.*?)</aside>', c, re.S)
        dup = sorted(set(i for i, _ in asides if [a for a, _ in asides].count(i) > 1))
        nrefs = re.findall(r'<sup><a epub:type="noteref" href="#([^"]+)">\s*<img[^>]*?alt="([^"]*)"[^>]*?/>\s*</a></sup>', c)
        all_sup = re.findall(r"<sup><a epub:type=\"noteref\".{0,400}?</sup>", c, re.S)
        odd = [s for s in all_sup if not re.match(
            r'<sup><a epub:type="noteref" href="#[^"]+">\s*<img[^>]*alt="[^"]*"[^>]*/>\s*</a></sup>$', s, re.S)]
        w("   aside=%d noteref=%d 重复id=%d 非标准noteref=%d" % (
            len(asides), len(nrefs), len(dup), len(odd)))
        if dup:
            w("      重复 id: %s" % ", ".join(dup[:8]) + ("..." if len(dup) > 8 else ""))
        if odd:
            w("      !! 非标准 noteref 样例: %s" % odd[0][:120])
        # 预配对检查
        pool = [{"id": a, "text": t, "used": False} for a, t in asides]
        dang = 0
        for fid, alt in nrefs:
            au = html.unescape(alt).strip()
            cands = [a for a in pool if not a["used"] and a["id"] == fid]
            pick = next((a for a in cands if html.unescape(a["text"]).strip() == au), None)
            if pick is None:
                pick = cands[0] if cands else None
            if pick is None:
                dang += 1
            else:
                pick["used"] = True
        orph = len([a for a in pool if not a["used"]])
        if dang or orph:
            w("      !! 预配对异常: 悬空noteref=%d 未引用aside=%d" % (dang, orph))
        # 插图 div
        style = cfg["chatu"].get("div_style", "display: block;text-align:center;")
        idivs = re.findall(r'<div style="' + re.escape(style) + r'">\n(<img[^>]*/>)([^\n]*)\n(<p>.*?</p>)([^\n]*)', c)
        w("   插图div=%d" % len(idivs))
        if idivs and (idivs[0][1] != "</div>" or idivs[0][3]):
            w("      !! 布局变体: after-img=%r after-p=%r" % (idivs[0][1], idivs[0][3]))
        tot["chatu"] += len(idivs)
        # span / div 清单
        spans = {}
        for s in re.findall(r"<span([^>]*)>", c):
            spans[s] = spans.get(s, 0) + 1
        divs = {}
        for s in re.findall(r"<div([^>]*)>", c):
            divs[s] = divs.get(s, 0) + 1
        plain = spans.pop("", 0)
        w("   span: 无属性=%d, 带属性=%s" % (plain, ", ".join(
            "x%d %s" % (v, k.strip()[:90]) for k, v in sorted(spans.items(), key=lambda x: -x[1]))))
        for k, v in sorted(divs.items(), key=lambda x: -x[1]):
            w("      div x%d: %s" % (v, k.strip()[:90]))
        # h 标签
        htags = re.findall(r"<h[1-6][^>]*>.*?</h[1-6]>", c, re.S)
        hb = len([h for h in htags if "<b>" in h])
        w("   h标签=%d 含b=%d" % (len(htags), hb))
        # 引文样式 span（区分 caption）
        marker = cfg["blockquote_quotes"].get("style_marker", "FZFangSong")
        fs_spans = [m for m in re.finditer(
            r'<p><span style="[^"]*' + re.escape(marker) + r'[^"]*">', c)]
        cap = 0
        for m in fs_spans:
            before = c[:m.start()]
            if re.search(r'<div style="' + re.escape(style) + r'">\n<img[^>]*/>[^\n]*</div>\n$', before):
                cap += 1
        w("   %s整段span=%d（其中caption=%d，引文=%d）" % (marker, len(fs_spans), cap, len(fs_spans) - cap))
        tot["fs"] += len(fs_spans) - cap
        # 其他图片（非脚注图标、非插图）
        imgs = re.findall(r"<img[^>]*>", c)
        other = [i for i in imgs if "epub-footnote" not in i]
        w("   非图标img=%d" % len(other))
        for i in other[:6]:
            if not any(i in d for d in idivs):
                w("      内嵌: %s" % i[:100])
        # 多行段落
        multi = len([1 for m in re.finditer(r"<p>(?:(?!</p>).)*?\n(?:(?!</p>).)*?</p>", c, re.S)])
        w("   跨行段落=%d" % multi)
        tot["asides"] += len(asides)
        tot["noterefs"] += len(nrefs)
    w()
    w("== 汇总: 文件=%d aside=%d noteref=%d 插图div=%d 引文段=%d" % (
        len(files), tot["asides"], tot["noterefs"], tot["chatu"], tot["fs"]))
    # 建议的 pre_strip 候选（出现最多的含 font-family 的整段 style）
    cand = {}
    svgs = {}
    for fp in files:
        c = read(fp)
        for s in re.findall(r'<span style="([^"]*)">', c):
            if "font-family" in s and "bold" not in s:
                cand[s] = cand.get(s, 0) + 1
        for s in re.findall(r'<img[^>]*src="([^"]*?/([^/]+\.svg))"[^>]*/>', c):
            svgs.setdefault(s[1], 0)
            svgs[s[1]] += 1
    if svgs:
        w("== 内嵌 SVG 字图（辨识每个字符后写入 inline_glyph_map）:")
        w('   "inline_glyph_map": {')
        for s, n in sorted(svgs.items()):
            w('     "%s": "□",   # x%d 待辨识' % (s, n))
        w("   }")
    if cand:
        w("== pre_strip 候选（出现次数降序，确认后写入 clean_config.json）:")
        for s, n in sorted(cand.items(), key=lambda x: -x[1])[:6]:
            w("   x%-4d %s" % (n, s))
    w()
    w("下一步: 对照 2do.md 检查以上结构与内置规则是否一致；有出入则写 clean_config.json / custom_clean.py")
    rep = "\n".join(L) + "\n"
    if out:
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

# ---------- process ----------

def process(dirpath, cfg, dry=False):
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml")
        sys.exit(1)
    custom = load_custom(dirpath)
    pos = cfg.get("custom_steps_position", "post")
    steps = []
    for sname in STEP_ORDER:
        steps.append((sname, BUILTIN_STEPS[sname]))
        if custom and pos == sname:
            steps.extend(custom)
    if custom and pos == "pre":
        steps = custom + steps
    if custom and pos == "post":
        steps = steps + custom
    if custom and pos not in STEP_ORDER + ["pre", "post"]:
        print("!! custom_steps_position=%r 无效（可用: %s / pre / post），自定义步骤被忽略" % (pos, ", ".join(STEP_ORDER)))

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if dry:
        backup_dir = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                                  "%s-%s" % (os.path.basename(os.path.normpath(dirpath)), stamp), "out")
        os.makedirs(backup_dir, exist_ok=True)
    else:
        backup_dir = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                                  "%s-%s" % (os.path.basename(os.path.normpath(dirpath)), stamp))
        os.makedirs(backup_dir, exist_ok=True)
    print("备份/输出目录: %s" % backup_dir)

    all_ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(backup_dir, name))
        ctx = {"chatu": 0, "fnotes": [], "fs_quotes": 0, "bodytext": 0,
               "unwrapped": 0, "h_b": 0, "pre_strip": 0, "subtitle": 0, "bold": 0,
               "joined": 0, "glyphs": 0}
        for sname, fn in steps:
            c = fn(c, name, cfg, ctx)
        probs, info = verify_content(c, name, cfg, dirpath)
        if probs:
            all_ok = False
            print("%-28s FAIL: %s" % (name, "; ".join(probs)))
            continue
        target = os.path.join(backup_dir, name) if dry else fp
        write(target, c)
        print("%-28s pre=%-4d glyph=%-2d chatu=%-2d fnotes=%-3d fs=%-2d bodytext=%-3d sub=%d bold=%-3d join=%d unwrap=%-2d hB=%d %s" % (
            name, ctx["pre_strip"], ctx["glyphs"], ctx["chatu"], len(ctx["fnotes"]),
            ctx["fs_quotes"], ctx["bodytext"], ctx["subtitle"], ctx["bold"],
            ctx["joined"], ctx["unwrapped"], ctx["h_b"],
            "(" + info[0] + ")" if info else ""))
    print("RESULT:", "OK" if all_ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if all_ok else 1)

# ---------- verify ----------

def verify_dir(dirpath, cfg):
    files = list_files(dirpath)
    all_ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs, info = verify_content(c, name, cfg, dirpath)
        if probs:
            all_ok = False
            print("%-28s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-28s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="EPUB xhtml 清洗流水线")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("analyze", "process", "verify"):
        sp = sub.add_parser(name)
        sp.add_argument("dir")
        sp.add_argument("-c", "--config")
        if name == "analyze":
            sp.add_argument("-o", "--out", help="报告写入文件（避免控制台中文乱码）")
        if name == "process":
            sp.add_argument("--dry-run", action="store_true", help="不写回，输出到临时目录")
    a = ap.parse_args()
    dirpath = os.path.abspath(a.dir)
    if not os.path.isdir(dirpath):
        print("!! 目录不存在: %s" % dirpath)
        sys.exit(1)
    cfg, cfgpath = load_config(dirpath, getattr(a, "config", None))
    if cfgpath:
        print("config: %s" % cfgpath)
    if a.cmd == "analyze":
        analyze(dirpath, cfg, out=getattr(a, "out", None))
    elif a.cmd == "process":
        process(dirpath, cfg, dry=a.dry_run)
    else:
        verify_dir(dirpath, cfg)

if __name__ == "__main__":
    main()
