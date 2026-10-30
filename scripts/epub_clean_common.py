#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_common.py — 各 profile 共用的后处理规则

postprocess(c) 依次执行:
  1) dedupe_chatu(c)            正文去重：同一 (img src + 图注) 只保留首次出现。
                                · 「彩图页」（整页插图墙：chatu>=3 且正文段<=2）整体跳过：
                                  既不去重，也不计入 seen，图版照旧保留。
                                · 其余文件（正文）跨文件去重，保留第一次出现。
                                · seen 为模块级集合，一次 process＝一个书目录＝一个进程，天然复位。
  2) strip_sprt_between_chatu   两个 <div class="chatu"> 之间不保留 <p class="sprt">…</p>

各 profile 在写出前调用 postprocess(c)；也可用 epub_clean_fix.py 对已清洗目录补跑。

另有 ensure_styles(dirpath)：处理前把 skill 内的 assets/styles.css（规范版，以此为准）
复制到目标目录；各 profile 的 process() 会自动调用，不需手动找 css。
"""
import os
import re
import shutil

ASSET_STYLES = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "styles.css"))


def ensure_styles(dirpath):
    """确保目标目录有最新 styles.css（skill 的 assets/styles.css 为准）。返回状态字符串。"""
    if not os.path.exists(ASSET_STYLES):
        return "missing-asset"
    dst = os.path.join(dirpath, "styles.css")
    try:
        if os.path.exists(dst):
            if open(ASSET_STYLES, "rb").read() == open(dst, "rb").read():
                return "same"
            shutil.copyfile(ASSET_STYLES, dst)
            return "updated"
        shutil.copyfile(ASSET_STYLES, dst)
        return "copied"
    except OSError as e:
        return "error:%s" % e

# ---------- 1) 正文 chatu 去重（彩图页除外，保留首次） ----------

_CHATU = re.compile(
    r'<div class="chatu">\s*<p class="image"><img src="([^"]*)"[^>]*/></p>\s*'
    r'(?:<p class="caption">(.*?)</p>\s*)?</div>', re.S)

_seen_chatu = set()


def _chatu_key(m):
    return (m.group(1), re.sub(r"\s+", "", m.group(2) or ""))


def reset_dedupe():
    _seen_chatu.clear()


def is_gallery(c):
    """整页插图墙（彩图页）：chatu 多、正文段极少"""
    chatu = len(_CHATU.findall(c))
    body = len(re.findall(r'class="bodytext(?:-noindent)?"', c))
    return chatu >= 3 and body <= 2


def dedupe_chatu(c):
    if is_gallery(c):
        return c                      # 彩图页：不去重、不登记

    def repl(m):
        key = _chatu_key(m)
        if key in _seen_chatu:
            return ""
        _seen_chatu.add(key)
        return m.group(0)

    c = _CHATU.sub(repl, c)
    return re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", c)


def register_chatu(c):
    """把本文件的 chatu 记入 seen（供 verify 模拟处理顺序）"""
    for m in _CHATU.finditer(c):
        _seen_chatu.add(_chatu_key(m))


def count_dupe_chatu(c):
    """只统计、不修改 seen：本文件内与已见（或本文件内重复）的 chatu 数"""
    n, local = 0, set()
    for m in _CHATU.finditer(c):
        k = _chatu_key(m)
        if k in _seen_chatu or k in local:
            n += 1
        local.add(k)
    return 0 if is_gallery(c) else n


# ---------- 2) chatu 之间不保留 sprt ----------

_SPRT_BETWEEN_CHATU = re.compile(
    r'(<div class="chatu">(?:(?!</div>).)*?</div>)\s*'
    r'<p class="sprt">[^<]*</p>\s*'
    r'(<div class="chatu">)',
    re.S)


def strip_sprt_between_chatu(c):
    prev = None
    while prev != c:
        prev = c
        c = _SPRT_BETWEEN_CHATU.sub(r"\1\n\2", c)
    return c


def count_sprt_between_chatu(c):
    return len(_SPRT_BETWEEN_CHATU.findall(c))


# ---------- 3) blockquote 内的 <p> 默认 bodytext ----------

_BQ = re.compile(r'(<blockquote\b[^>]*>)(.*?)(</blockquote>)', re.S)


def blockquote_bodytext(c):
    """引文块里没有 class 的 <p> 一律补成 <p class="bodytext">（poem/menu 等由 css 覆盖）"""
    def repl(m):
        return m.group(1) + re.sub(r"<p\s*>", '<p class="bodytext">', m.group(2)) + m.group(3)
    return _BQ.sub(repl, c)


def count_blockquote_bare_p(c):
    return sum(len(re.findall(r"<p\s*>", m.group(2))) for m in _BQ.finditer(c))


# ---------- 组合 ----------

def _fix_text_node(t):
    t = t.replace("\u00a0", " ")                       # NBSP -> 普通空格
    t = t.replace("\u25cb", "\u3007")                   # ○(U+25CB) -> 〇(U+3007)：年份/数量里的「零」
    t = re.sub(r"(?<=[0-9A-Za-z])\s+(?=[\u4e00-\u9fff])", "", t)   # A4 大小 -> A4大小
    t = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[0-9A-Za-z])", "", t)   # 中文 ABC -> 中文ABC
    t = re.sub(r"(?<=[A-Za-z])\s+(?=[.\-])", "", t)                # T .S . -> T.S.
    return t


def normalize_typography(c):
    """文本节点规范化：NBSP→空格、○→〇、中英之间空格、缩写点前空格；并合并逐字 <i>、一段一行"""
    c = re.sub(r">([^<]+)<", lambda m: ">" + _fix_text_node(m.group(1)) + "<", c)
    c = re.sub(r"</i>\s*<i>", "", c)                    # <i>阿</i><i>提</i> -> <i>阿提</i>
    c = re.sub(r"</p>\s*<p", "</p>\n<p", c)             # 两个 <p> 不挤在同一行
    return c


def ensure_xml_decl(c):
    """把 XML 声明规范成 <?xml version="1.0" encoding="utf-8"?> 独占一行；缺则补上。"""
    body = c.lstrip("\ufeff")
    canon = '<?xml version="1.0" encoding="utf-8"?>'
    m = re.match(r"<\?xml[^>]*\?>", body)
    if m:
        rest = body[m.end():].lstrip("\r\n")
        new = canon + "\n" + rest
        return c if new == c else new
    return canon + "\n" + body


def postprocess(c):
    c = dedupe_chatu(c)
    c = strip_sprt_between_chatu(c)
    c = blockquote_bodytext(c)
    c = normalize_typography(c)
    c = ensure_xml_decl(c)
    return c
