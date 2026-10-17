#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epub_clean_common.py — 各 profile 共用的后处理规则

strip_sprt_between_chatu(c):
  两个 <div class="chatu"> 之间若夹着 <p class="sprt">…</p>，删去该 sprt
  （连续插图之间不需要分隔符；只删「chatu → sprt → chatu」这一种，其余 sprt 保留）

各 profile 在写出前调用它；也可单独用 epub_clean_fix.py 对已清洗过的目录补跑。
"""
import re

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
