#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_indesign.py — Adobe InDesign / Adept 导出 EPUB xhtml 清洗

适用特征（源文件，多为繁体中文译本）:
  <body ... class="calibre">、<div class="calibre1"> 包裹层
  <h1 class="f_" id="_idParaDest-N"><span class="bold">标题</span></h1>
  <p class="f_1">正文、<p class="f_2">署名/推荐人、<p class="f_4">脚注文字或图注
  脚注: 正文 <span id="footnote-N-backlink"><a class="… _idfootnotelink …" href="f#footnote-N">N</a></span>
        文末 <hr class="horizontalrule"/> + <div class="calibre1" type="footnote" id="footnote-N">
             <p class="f_4"><a class="… _idfootnotelink …" href="f#footnote-N-backlink">N</a>　注文</p></div>
  引文/题词: <span class="kfont">…</span>（章首多行、末行以 —署名 结尾 = 题词）
  插图: <div class="mg_l_*"><div …><img class="calibre3" src="…"/></div>…<p class="f_4">图注</p></div>
  分隔: <p class="f_1">＊</p>

映射:
  <p class="f_1">              -> <p class="bodytext">
  章首题词(kfont,以—结尾)       -> <blockquote class="intro">（首行 class="blockquote"，署名 class="right"）
  正文 kfont 引文段              -> <blockquote><p class="bodytext">（段后仍有正文才转换，避免误判章末简介/献词）
  正文注释标记                    -> <sup><span id="footnote-N-backlink"><a href="f#footnote-N">[N]</a></span></sup>
  脚注 div(<div type="footnote">) -> <p class="fnote" id="footnote-N"><a href="f#footnote-N-backlink">[N]</a>　注文</p>
  mg_l_* 插图                    -> <div class="chatu"><p class="image"><img src="…" alt=""/></p>
                                     <p class="caption">图注1<br/>图注2</p></div>
  <p class="f_1">＊</p>           -> <p class="sprt">＊</p>
  css 链接                       -> styles.css（删除 styleNNNN / stylesheet / page_styles 链接）

子命令:
  analyze <dir> [-o REPORT]   结构普查（只读）
  process <dir> [--dry-run]   执行清洗（自动备份；--dry-run 输出到临时目录）
  verify  <dir>               独立校验
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "css_href": "styles.css",
    "drop_css_re": r"(?:style\d+|stylesheet|page_styles)\.css",
    "hr_class": "horizontalrule",
    "fnote_div_class": "calibre1",         # 脚注/插图外层 div 的 class
    "margin_div_prefix": "mg_l_",          # 插图包裹 div class 前缀
    "quote_span": "kfont",                 # 引文/题词 span class
    "bodytext_src": "f_1",                 # 正文段 class
    "intro_first_p_class": "bodytext",     # 题词各行 class（署名行固定 right）
    "sep_text": "＊",                       # 分隔符段文字
}

# 注释锚点/回链的 <a> 常带 pcalibre* 等类，用 [_idfootnotelink] 宽松匹配
REF_CLS = r'[^"]*_idfootnotelink[^"]*'

# ---------- 基础 ----------

def list_files(d):
    return sorted(f for f in glob.glob(os.path.join(d, "*.xhtml")) if not f.endswith(".bak"))

def read(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")

def write(fp, c):
    with open(fp, "w", encoding="utf-8", newline="") as f:
        f.write(c)

def div_end(c, start):
    """从 <div ...> 起点返回匹配 </div> 的结束索引（不含）；不匹配返回 None"""
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div>", c[start:]):
        if m.group().startswith("</div"):
            depth -= 1
            if depth == 0:
                return start + m.end()
        else:
            depth += 1
    return None

# ---------- 步骤 ----------

def step_css(c, name, cfg, ctx):
    c = re.sub(r'[ \t]*<link[^>]*href="[^"]*' + cfg["drop_css_re"] + r'"[^>]*/>[ \t]*\n?', "", c)
    if ('href="%s"' % cfg["css_href"]) not in c:
        c = c.replace("</head>",
                      '  <link rel="stylesheet" type="text/css" href="%s"/>\n</head>' % cfg["css_href"], 1)
        ctx["css"] += 1
    return c

def step_quotes(c, name, cfg, ctx):
    kspan = r'<span class="%s">[^<]*</span>' % cfg["quote_span"]
    kitem = r'(?:%s|<span id="footnote-\d+-backlink"><a [^>]*>\[?\d+\]?</a></span>)' % kspan
    p_inner = r'(?:%s)+' % kitem
    run_re = re.compile(r'(?:<p class="%s">%s</p>\s*)+' % (cfg["bodytext_src"], p_inner))
    para_re = re.compile(r'<p class="%s">(%s)</p>' % (cfg["bodytext_src"], p_inner))

    def strip_k(s):
        return re.sub(r'<span class="%s">(.*?)</span>' % cfg["quote_span"], r"\1", s, flags=re.S)

    def text_of(s):
        return re.sub(r"<[^>]+>", "", strip_k(s))

    def repl(m):
        paras = para_re.findall(m.group(0))
        if not paras:
            return m.group(0)
        texts = [text_of(p) for p in paras]
        if texts[-1].lstrip().startswith("—"):        # 题词：末行以 —署名 结尾
            lines = []
            for i, p in enumerate(paras):
                if i == 0:
                    cls = cfg["intro_first_p_class"]
                elif texts[i].lstrip().startswith("—"):
                    cls = "right"
                else:
                    cls = "bodytext"
                lines.append('<p class="%s">%s</p>' % (cls, strip_k(p).strip()))
            ctx["intro"] += 1
            return '<blockquote class="intro">\n' + "\n".join(lines) + "\n</blockquote>\n"
        # 正文引文：段后仍有正文才转换（避免把章末"作者简介/献词"误当引文）
        after = c[m.end():].split("</body>")[0]
        if not re.search(r"<p\b", after):
            ctx["quote_skip"] += 1
            return m.group(0)
        lines = ['<p class="bodytext">%s</p>' % strip_k(p).strip() for p in paras]
        ctx["blockquote"] += 1
        return "<blockquote>\n" + "\n".join(lines) + "\n</blockquote>\n"

    return run_re.sub(repl, c)

def step_markers(c, name, cfg, ctx):
    pat = re.compile(r'<span id="(footnote-\d+-backlink)"><a class="' + REF_CLS + r'" href="([^"]*)">(\d+)</a></span>')

    def repl(m):
        ctx["markers"] += 1
        return '<sup><span id="%s"><a href="%s">[%s]</a></span></sup>' % (m.group(1), m.group(2), m.group(3))

    return pat.sub(repl, c)

def step_footnotes(c, name, cfg, ctx):
    pat = re.compile(
        r'<div class="%s" type="footnote" id="(footnote-\d+)">\s*'
        r'<p class="f_4"><a class="' % cfg["fnote_div_class"] + REF_CLS +
        r'" href="([^"]*)">(\d+)</a>(.*?)</p>\s*</div>', re.S)

    def repl(m):
        fid, href, num, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        ctx["fnotes"].append(fid)
        return '<p class="fnote" id="%s"><a href="%s">[%s]</a>%s</p>' % (fid, href, num, rest)

    return pat.sub(repl, c)

def step_figures(c, name, cfg, ctx):
    reps = []
    for m in re.finditer(r'<div class="%s[^"]*"[^>]*>' % cfg["margin_div_prefix"], c):
        s = m.start()
        e = div_end(c, s)
        if e is None:
            continue
        block = c[s:e]
        im = re.search(r'<img[^>]*src="([^"]*)"', block)
        if not im:
            continue
        caps = [re.sub(r"\s+", " ", x).strip()
                for x in re.findall(r'<p class="f_4">(.*?)</p>', block, re.S)]
        parts = ['<div class="chatu">',
                 '<p class="image"><img src="%s" alt=""/></p>' % im.group(1)]
        if caps:
            parts.append('<p class="caption">%s</p>' % "<br/>".join(caps))
        parts.append("</div>")
        chatu = "\n".join(parts)
        s2, e2 = s, e
        mm = re.search(r'<div class="%s">\s*$' % cfg["fnote_div_class"], c[:s])
        if mm:
            s2 = mm.start()
            mp = re.match(r"\s*</div>", c[e:])
            if mp:
                e2 = e + mp.end()
        reps.append((s2, e2, chatu))
    for s, e, new in reversed(reps):
        c = c[:s] + new + c[e:]
    ctx["chatu"] += len(reps)
    return c

def step_sep(c, name, cfg, ctx):
    pat = re.compile(r'<p class="%s">%s</p>' % (cfg["bodytext_src"], re.escape(cfg["sep_text"])))
    ctx["sprt"] += len(pat.findall(c))
    return pat.sub('<p class="sprt">%s</p>' % cfg["sep_text"], c)

def step_bodytext(c, name, cfg, ctx):
    pat = re.compile(r'<p class="%s">' % cfg["bodytext_src"])
    ctx["bodytext"] += len(pat.findall(c))
    c = pat.sub('<p class="bodytext">', c)
    # 历史输出/误写：<p class="blockquote"> 归一为 bodytext
    n = len(re.findall(r'<p class="blockquote">', c))
    ctx["bodytext"] += n
    return c.replace('<p class="blockquote">', '<p class="bodytext">')

def step_sub(c, name, cfg, ctx):
    """<span class="sub">X</span> → <sub>X</sub>"""
    pat = re.compile(r'<span class="sub">(.*?)</span>', re.S)
    ctx["sub"] += len(pat.findall(c))
    return pat.sub(r'<sub>\1</sub>', c)

def step_author(c, name, cfg, ctx):
    """<p class="f_2">：以 `—` 开头（署名/推荐落款）→ <p class="right">，且其后若还有段落则补一空行段；
    否则（作者名）→ <p class="author">"""
    def repl(m):
        inner = m.group(1)
        if inner.lstrip().startswith("—"):
            blank = ""
            if re.match(r"\s*<p\b", c[m.end():]):
                blank = '\n<p class="bodytext"><br/></p>'
                ctx["sig_blank"] += 1
            ctx["author_right"] += 1
            return '<p class="right">%s</p>%s' % (inner, blank)
        ctx["author"] += 1
        return '<p class="author">%s</p>' % inner
    return re.sub(r'<p class="f_2">(.*?)</p>', repl, c, flags=re.S)

def step_kai(c, name, cfg, ctx):
    """残留 <span class="kfont"> → <span class="kai">（styles.css 只定义 .kai/.kaiti，未定义 .kfont）"""
    n = len(re.findall(r'class="kfont"', c))
    ctx["kai"] += n
    return c.replace('class="kfont"', 'class="kai"')

def step_zerocircle(c, name, cfg, ctx):
    """○ (U+25CB) → 〇 (U+3007)（年份/数量中的「零」）"""
    n = c.count('\u25CB')
    ctx["zerocircle"] += n
    return c.replace('\u25CB', '\u3007')

def step_tidy(c, name, cfg, ctx):
    """清理因删除元素产生的空行与行首缩进（InDesign 导出普遍带 \t 缩进）"""
    hm = re.search(r"<head>.*?</head>", c, re.S)
    if hm:
        head = re.sub(r"\n(?:[ \t]*\n)+", "\n", hm.group(0))
        c = c[:hm.start()] + head + c[hm.end():]
    i = c.find("<body")
    if i >= 0:
        pre, body = c[:i], c[i:]
        n = len(re.findall(r"^[ \t]*\n", body, re.M))
        body = re.sub(r"^[ \t]*\n", "", body, flags=re.M)
        body = re.sub(r"^[ \t]+(?=<)", "", body, flags=re.M)
        ctx["blank"] += n
        c = pre + body
    return c

STEP_ORDER = ["css", "quotes", "markers", "footnotes", "figures", "sep", "bodytext", "sub", "author", "kai", "zerocircle", "tidy"]
BUILTIN = {"css": step_css, "quotes": step_quotes, "markers": step_markers,
           "footnotes": step_footnotes, "figures": step_figures,
           "sep": step_sep, "bodytext": step_bodytext, "sub": step_sub,
           "author": step_author, "kai": step_kai, "zerocircle": step_zerocircle, "tidy": step_tidy}

# ---------- 校验 ----------

def verify_content(c, name, cfg, dirpath):
    probs, info = [], []
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        return ["XML 解析失败: %s" % e], info
    if '<p class="%s">' % cfg["bodytext_src"] in c:
        probs.append("残留 <p class=\"%s\">" % cfg["bodytext_src"])
    if 'type="footnote"' in c:
        probs.append("残留脚注 div")
    if "_idfootnotelink" in c:
        probs.append("残留 _idfootnotelink")
    if re.search(r'<div class="%s[^"]*"' % cfg["margin_div_prefix"], c):
        probs.append("残留插图包裹 div")
    if re.search(r'href="[^"]*' + cfg["drop_css_re"] + r'"', c):
        probs.append("残留旧 css 链接")
    if ('href="%s"' % cfg["css_href"]) not in c and "</head>" in c:
        probs.append("缺少 css 链接")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for href in re.findall(r'href="#([^"]+)"', c):
        if href not in ids:
            probs.append("悬空链接 #%s" % href)
    for src in re.findall(r'<img[^>]*src="([^"]+)"', c):
        if not os.path.exists(os.path.normpath(os.path.join(dirpath, src))):
            probs.append("图片不存在 %s" % src)
    marks = re.findall(r'<sup><span id="footnote-\d+-backlink"><a href="[^"]*#footnote-\d+">', c)
    fn = re.findall(r'<p class="fnote" id="footnote-\d+">', c)
    if len(marks) != len(fn):
        probs.append("注释标记(%d) != 尾注(%d)" % (len(marks), len(fn)))
    info.append("fnote=%d intro=%d bq=%d chatu=%d" % (
        len(fn), c.count('class="intro"'),
        len(re.findall(r"<blockquote>", c)), c.count('class="chatu"')))
    return probs, info

# ---------- analyze ----------

RE_MARKER = re.compile(r'<span id="footnote-\d+-backlink"><a class="' + REF_CLS + '"')
RE_BODY = re.compile(r'<p class="f_1">')
RE_FNOTE = re.compile(r'<div class="[^"]*" type="footnote"')
RE_FIG = re.compile(r'<div class="mg_l_')
RE_KFONT = re.compile(r'<span class="kfont">')
RE_H1 = re.compile(r'<h1 class="f_" id="_idParaDest')
RE_OLDCSS = re.compile(r'href="[^"]*' + CONFIG["drop_css_re"] + r'"')
RE_SEP = re.compile(r'<p class="f_1">%s</p>' % re.escape(CONFIG["sep_text"]))

def analyze(dirpath, out=None):
    L = []

    def w(s=""):
        L.append(s)

    files = list_files(dirpath)
    w("# analyze(indesign): %s" % dirpath)
    w("文件=%d" % len(files))
    if not files:
        return _emit(L, out)
    hit = {k: any(r.search(read(f)) for f in files) for k, r in (
        ("h1", RE_H1), ("bodytext(f_1)", RE_BODY), ("fnote_div", RE_FNOTE),
        ("marker", RE_MARKER), ("figure(mg_l)", RE_FIG), ("kfont", RE_KFONT))}
    w("特征命中: %s" % ", ".join(k for k, v in hit.items() if v))
    if not (hit["fnote_div"] or hit["marker"] or hit["figure(mg_l)"] or hit["bodytext(f_1)"]):
        w("!! 未命中 InDesign/Adept 特征，请改用于对应 profile 的脚本")
    tot = dict(fnote=0, marker=0, fig=0, kfont=0, sep=0, oldcss=0)
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        fn, mk, fg = len(RE_FNOTE.findall(c)), len(RE_MARKER.findall(c)), len(RE_FIG.findall(c))
        kf, sp, oc = len(RE_KFONT.findall(c)), len(RE_SEP.findall(c)), len(RE_OLDCSS.findall(c))
        w("%-24s fnote=%-3d marker=%-3d fig=%-2d kfont=%-3d sep=%-2d oldcss=%d  %s" % (
            name, fn, mk, fg, kf, sp, oc, "OK" if fn == mk else "!! fnote/marker 不等"))
        tot["fnote"] += fn; tot["marker"] += mk; tot["fig"] += fg
        tot["kfont"] += kf; tot["sep"] += sp; tot["oldcss"] += oc
    w("== 汇总: fnote=%d marker=%d 插图div=%d kfont段=%d 分隔=%d 旧css=%d" % (
        tot["fnote"], tot["marker"], tot["fig"], tot["kfont"], tot["sep"], tot["oldcss"]))
    w("== 默认规则: f_1->bodytext、章首题词->blockquote.intro、kfont正文引文->blockquote、")
    w("   注释标记->sup[N]、脚注div->p.fnote(id/backlink 双向)、mg_l图->chatu、＊->sprt、css->styles.css、去缩进")
    w("== 出入时调 CONFIG（脚本顶部）或在 <dir>/clean_config.json 覆写同名键")
    return _emit(L, out)

def _emit(L, out):
    rep = "\n".join(L) + "\n"
    if out:
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(rep)
        print("report -> %s" % out)
    else:
        sys.stdout.write(rep)

# ---------- process / verify ----------

def process(dirpath, dry=False):
    files = list_files(dirpath)
    if not files:
        print("!! 未找到 *.xhtml")
        sys.exit(1)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(os.environ.get("TEMP", "."), "opencode", "epub-clean",
                        "%s-%s" % (os.path.basename(os.path.normpath(dirpath)), stamp))
    backup_dir = os.path.join(base, "out") if dry else base
    os.makedirs(backup_dir, exist_ok=True)
    print("备份/输出目录: %s" % backup_dir)
    all_ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        if not dry:
            shutil.copy2(fp, os.path.join(backup_dir, name))
        ctx = dict(css=0, intro=0, blockquote=0, quote_skip=0, markers=0,
                   fnotes=[], chatu=0, sprt=0, bodytext=0, sub=0, author=0,
                   author_right=0, sig_blank=0, kai=0, zerocircle=0, blank=0)
        for s in STEP_ORDER:
            c = BUILTIN[s](c, name, CONFIG, ctx)
        probs, info = verify_content(c, name, CONFIG, dirpath)
        if probs:
            all_ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(backup_dir, name) if dry else fp, c)
        print("%-24s fnote=%-3d intro=%d bq=%d skip=%d chatu=%-2d sprt=%-2d bodytext=%-3d sub=%-2d author=%d/%d kai=%-3d ○=%-3d blank=%d" % (
            name, len(ctx["fnotes"]), ctx["intro"], ctx["blockquote"], ctx["quote_skip"],
            ctx["chatu"], ctx["sprt"], ctx["bodytext"], ctx["sub"],
            ctx["author"], ctx["author_right"], ctx["kai"], ctx["zerocircle"], ctx["blank"]))
    print("RESULT:", "OK" if all_ok else "FAIL（有文件未通过校验，未写回）")
    sys.exit(0 if all_ok else 1)

def verify_dir(dirpath):
    files = list_files(dirpath)
    allids = {os.path.basename(f): set(re.findall(r'\bid="([^"]+)"', read(f))) for f in files}
    all_ok = True
    for fp in files:
        name = os.path.basename(fp)
        c = read(fp)
        probs, info = verify_content(c, name, CONFIG, dirpath)
        for href in re.findall(r'href="([^"]+\.xhtml#[^"]+)"', c):
            fn, frag = href.split("#", 1)
            if fn in allids and frag not in allids[fn]:
                probs.append("跨文件悬空 %s" % href)
        if probs:
            all_ok = False
            print("%-24s FAIL: %s" % (name, "; ".join(probs)))
        else:
            print("%-24s OK %s" % (name, " ".join(info)))
    print("RESULT:", "PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="InDesign/Adept xhtml 清洗")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("analyze", "process", "verify"):
        sp = sub.add_parser(n)
        sp.add_argument("dir")
        if n == "analyze":
            sp.add_argument("-o", "--out")
        if n == "process":
            sp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if not os.path.isdir(d):
        print("!! 目录不存在: %s" % d)
        sys.exit(1)
    if a.cmd == "analyze":
        analyze(d, out=getattr(a, "out", None))
    elif a.cmd == "process":
        process(d, dry=a.dry_run)
    else:
        verify_dir(d)

if __name__ == "__main__":
    main()
