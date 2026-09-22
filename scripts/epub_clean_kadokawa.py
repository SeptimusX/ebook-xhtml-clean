#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_kadokawa.py — KADOKAWA 竖排 / 固定版式 EPUB 清洗（阶段二）

背景：KADOKAWA 竖排书几乎没有语义标签，标题/引文/图片全靠 class 排版。
处理分两阶段：
  阶段一（人工语义化重排）：纯版式 markup → 语义标签（<h1>/<h3>/blockquote/chatu/fnote…）。
    判断性工作，本脚本不做；规则见 SKILL.md「KADOKAWA profile」。
  阶段二（本脚本，确定性批处理）：
    1) 全角字母 / 数字 → 半角（U+FF10–FF19 / FF21–FF3A / FF41–FF5A，减 0xFEE0；标点与全角空格不动）
    2) 注释编号加方括号：<span class="key2"…>N</span> → …>[N]<…；<span class="key1">N</span> → …>[N]<…
       （href/id 锚点不动，双向跳转保持有效）

子命令: analyze / process / verify （与其他 profile 一致）
额外校验：逐文件恒等校验 —— 输出（去掉方括号）== 源文件经同样全角→半角转换的结果。
"""
import argparse, datetime, glob, os, re, shutil, sys
import xml.etree.ElementTree as ET

CONFIG = {
    "fullwidth_letters_digits": True,   # 阶段二 1
    "bracket_notes": True,              # 阶段二 2
    # 可选：Kobo 阅读器导出时注入的噪声（KADOKAWA 书常见）
    "strip_kobo_spans": False,          # 去掉 <span class="koboSpan" …> 包裹（保留内容）
    "drop_scripts": False,              # 去掉 <script …></script>
    "drop_kobo_style": False,           # 去掉 <style id="koboSpanStyle">…</style>
}

# 注释编号（容忍两位数被 <span class="tcy"> 竖排縦中横 包裹，包裹保留）
KEY2_RE = re.compile(r'<span class="key2"([^>]*)>(<span class="tcy">)?(\d+)(</span>)?</span>')
KEY1_RE = re.compile(r'<span class="key1">(<span class="tcy">)?(\d+)(</span>)?</span>')
# 尚未加方括号的注释编号（残留检测）
KEY_RAW_RE = re.compile(r'<span class="key[12]"[^>]*>(?:<span class="tcy">)?\d+')

# 全角 → 半角（仅字母 / 数字）
_FW = list(range(0xFF10, 0xFF1A)) + list(range(0xFF21, 0xFF3B)) + list(range(0xFF41, 0xFF5B))
FW_TABLE = str.maketrans({chr(c): chr(c - 0xFEE0) for c in _FW})

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

def step_fullwidth(c, name, ctx):
    if not CONFIG["fullwidth_letters_digits"]:
        return c
    ctx["fw"] += len(re.findall(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]", c))
    return c.translate(FW_TABLE)

def step_brackets(c, name, ctx):
    if not CONFIG["bracket_notes"]:
        return c
    ctx["key2"] += len(KEY2_RE.findall(c))
    ctx["key1"] += len(KEY1_RE.findall(c))
    c = KEY2_RE.sub(lambda m: '<span class="key2"%s>%s[%s]%s</span>' % (
        m.group(1), m.group(2) or "", m.group(3), m.group(4) or ""), c)
    c = KEY1_RE.sub(lambda m: '<span class="key1">%s[%s]%s</span>' % (
        m.group(1) or "", m.group(2), m.group(3) or ""), c)
    return c

def step_kobo(c, name, ctx):
    if CONFIG["drop_scripts"]:
        c = re.sub(r"[ \t]*<script\b[^>]*>.*?</script>[ \t]*\n?", "", c, flags=re.S)
    if CONFIG["drop_kobo_style"]:
        c = re.sub(r'[ \t]*<style\b[^>]*id="koboSpanStyle"[^>]*>.*?</style>[ \t]*\n?', "", c, flags=re.S)
    if CONFIG["strip_kobo_spans"]:
        open_re = re.compile(r'<span\b[^>]*class="koboSpan"[^>]*>')
        token_re = re.compile(r"<span\b[^>]*>|</span>")
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
            ctx["kobo"] += 1
    return c

STEPS = [("kobo", step_kobo), ("fullwidth", step_fullwidth), ("brackets", step_brackets)]

# ---------- 校验 ----------

def strip_brackets(s):
    return s.replace("[", "").replace("]", "")

def _structural():
    return (CONFIG["strip_kobo_spans"] or CONFIG["drop_scripts"] or CONFIG["drop_kobo_style"])

def identity(orig, result):
    """恒等校验：
    未启用结构性选项时 —— 输出（去方括号）== 源经同样全角→半角转换（去方括号）（逐字符）
    启用时 —— 退化为文本级内容一致性（去标签去方括号去空白后相等）"""
    if not _structural():
        return strip_brackets(result) == strip_brackets(orig.translate(FW_TABLE))

    def txt(s):
        s = re.sub(r"<script\b[^>]*>.*?</script>", "", s, flags=re.S)
        s = re.sub(r"<style\b[^>]*>.*?</style>", "", s, flags=re.S)
        s = re.sub(r"<head\b[^>]*>.*?</head>", "", s, flags=re.S)
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("[", "").replace("]", "")
        return re.sub(r"\s+", "", s)

    return txt(result) == txt(orig.translate(FW_TABLE))

def verify_content(c, name, d, orig=None):
    probs, info = [], []
    src_ok = None
    if orig is not None:
        try:
            ET.fromstring(orig.encode("utf-8"))
            src_ok = True
        except Exception:
            src_ok = False
    try:
        ET.fromstring(c.encode("utf-8"))
    except Exception as e:
        # Kobo 导出的 KADOKAWA 书常见源文件本身非良构；源可解析而结果不可才算我们的错
        if orig is None or src_ok:
            probs.append("XML 解析失败: %s" % e)
        else:
            info.append("源本非良构XML(跳过XML校验)")
    if CONFIG["bracket_notes"]:
        if KEY_RAW_RE.search(c):
            probs.append("注释编号未加方括号")
        key_all = len(re.findall(r'<span class="key[12]"', c))
        key_br = len(re.findall(r'<span class="key[12]"[^>]*>(?:<span class="tcy">)?\[', c))
        if key_all != key_br:
            msg = "未加方括号的 key 标记 %d/%d" % (key_all - key_br, key_all)
            if src_ok is False:
                info.append(msg + "(源结构损坏，无法自动加括号)")
            else:
                probs.append(msg + "（若被 koboSpan 包裹，需加 --strip-kobo）")
    fw = re.findall(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]", c)
    if CONFIG["fullwidth_letters_digits"] and fw:
        probs.append("残留全角字母/数字 %d 处" % len(fw))
    if CONFIG["strip_kobo_spans"] and 'class="koboSpan"' in c:
        probs.append("残留 koboSpan")
    ids = re.findall(r'\bid="([^"]+)"', c)
    dups = sorted(set(i for i in ids if ids.count(i) > 1))
    if dups:
        probs.append("重复 id: %s" % dups[:3])
    for h in re.findall(r'href="#([^"]+)"', c):
        if h not in ids:
            probs.append("悬空链接 #%s" % h)
    info.append("key2=%d key1=%d" % (len(re.findall(r'<span class="key2"', c)),
                                     len(re.findall(r'<span class="key1"', c))))
    return probs, info

# ---------- 命令 ----------

def analyze(d, out=None):
    import collections
    L = []
    w = lambda s="": L.append(s)
    w("# analyze(kadokawa): %s" % d)
    files = list_files(d)
    cls = collections.Counter()
    tot = collections.Counter()
    for fp in files:
        c = read(fp)
        name = os.path.basename(fp)
        links = re.findall(r'<link[^>]*href="([^"]+)"', c)
        lang = re.search(r'xml:lang="([^"]*)"', c)
        fw = len(re.findall(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]", c))
        k2 = len(re.findall(r'<span class="key2"', c))
        k1 = len(re.findall(r'<span class="key1"', c))
        kobo = len(re.findall(r'class="koboSpan"', c))
        stage1 = any(x in c for x in ('class="bodytext"', "class=\"chatu\"", "<blockquote", "<h1", "<h3"))
        for m in re.findall(r'class="([^"]*)"', c):
            cls[m] += 1
        tot["fw"] += fw; tot["key2"] += k2; tot["key1"] += k1; tot["kobo"] += kobo
        w("%-16s lang=%-6s stage1=%-5s fw=%-3d key2=%-3d key1=%-3d kobo=%-4d css=%s" % (
            name, lang.group(1) if lang else "?", stage1, fw, k2, k1, kobo, ",".join(links)))
    w()
    w("== 汇总: files=%d 全角字母数字=%d key2=%d key1=%d koboSpan=%d" % (
        len(files), tot["fw"], tot["key2"], tot["key1"], tot["kobo"]))
    w("== class 取值（前 25）: %s" % ", ".join("%s x%d" % (k, v) for k, v in cls.most_common(25)))
    w("== 提示: stage1=False 的文件尚未做语义化重排（阶段一），规则见 SKILL.md")
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
        ctx = {"fw": 0, "key2": 0, "key1": 0, "kobo": 0}
        for sname, fn in STEPS:
            c = fn(c, name, ctx)
        probs, info = verify_content(c, name, d, orig)
        if not identity(orig, c):
            probs.append("恒等校验失败")
        if probs:
            ok = False
            print("%-16s FAIL: %s" % (name, "; ".join(probs)))
            continue
        write(os.path.join(outdir, name) if dry else fp, c)
        print("%-16s fw=%-4d key2=%-3d key1=%-3d kobo=%-4d %s" % (
            name, ctx["fw"], ctx["key2"], ctx["key1"], ctx["kobo"], info[0]))
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
    ap = argparse.ArgumentParser(description="KADOKAWA 竖排/固定版式 EPUB 清洗（阶段二）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("analyze", "process", "verify"):
        sp = sub.add_parser(nm)
        sp.add_argument("dir")
        if nm == "analyze":
            sp.add_argument("-o", "--out")
        if nm == "process":
            sp.add_argument("--dry-run", action="store_true")
            sp.add_argument("--strip-kobo", action="store_true", help="去掉 koboSpan 包裹（Kobo 导出噪声）")
            sp.add_argument("--drop-scripts", action="store_true", help="去掉 <script>")
            sp.add_argument("--drop-kobo-style", action="store_true", help="去掉 <style id=\"koboSpanStyle\">")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if not os.path.isdir(d):
        print("!! 目录不存在: %s" % d)
        sys.exit(1)
    if a.cmd == "analyze":
        analyze(d, getattr(a, "out", None))
    elif a.cmd == "process":
        if getattr(a, "strip_kobo", False):
            CONFIG["strip_kobo_spans"] = True
        if getattr(a, "drop_scripts", False):
            CONFIG["drop_scripts"] = True
        if getattr(a, "drop_kobo_style", False):
            CONFIG["drop_kobo_style"] = True
        process(d, dry=a.dry_run)
    else:
        verify_dir(d)

if __name__ == "__main__":
    main()
