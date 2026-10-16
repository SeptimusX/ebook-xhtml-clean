# ebook-xhtml-clean

把各类来源的电子书章节 XHTML 清洗为统一的语义化格式（`bodytext` / `fnote` / `chatu` / `blockquote` + `styles.css`）。
An opencode skill / CLI for cleaning EPUB xhtml from thirteen common Chinese e-book sources.

## 支持的源格式（十三套 profile）

| profile | 脚本 | 典型特征 |
|---|---|---|
| 得到 / 中华书局 | `scripts/epub_clean.py` | `<aside epub:type="footnote">注文</aside>`、仿宋引文、`<p><span style="…">` 内联样式 |
| calibre + 多看(duokan) | `scripts/epub_clean_calibre.py`（**配置驱动**：`<dir>/clean_config.json`，`calibreNN` 类号逐书不同） | `calibreN` 类、duokan 脚注 `<ol><li>`、`<div class="calibre13">` 图 |
| 微信读书 / QQ阅读 | `scripts/epub_clean_weread.py` | `readerChapterContent`、`data-wr-footernote`、`p.content` / `p.quotation` |
| KADOKAWA 竖排 / 固定版式 | `scripts/epub_clean_kadokawa.py` | `book-style.css`、`kfont` 引文、`key1`/`key2` 注释锚点 |
| 多看原生（图片式注释标记） | `scripts/epub_clean_duokan.py` | `p.text`、`h2.chapter-title2`、`../Styles/*.css`、`a.duokan-footnote` + `note.png` 注释标记 |
| InDesign / Adept | `scripts/epub_clean_indesign.py` | `<h1 class="f_" id="_idParaDest-N">`、`p.f_1`/`f_2`/`f_4`、`_idfootnotelink`、`<div type="footnote">`、`<div class="mg_l_*">` 图 |
| 人民邮电 / 得到（`p.content` 系） | `scripts/epub_clean_ptpress.py` | `h1.firstTitle#sigil_toc_id_N`、`p.content` / `content_100..110`、`div.pic`+`imgtitle`、`span.kt_104`、`span.super[id=refN]`+`p.noindent[id=annotN]` |
| 多看原生 · 内文/标题（`neiwen`/`biaoti`） | `scripts/epub_clean_duokan_biaoti.py` | `p>span.neiwen`（变体 `neiwen2/2_1/3/4/5/6`）、`h1>span.biaoti1`+`biaoti2`、`h2>span.biaoti3`/`biaoti5`、`div.duokan-image-single`+`maintitle`/`subtitle`、`a.duokan-footnote`+`note.png`、`ol.duokan-footnote-content`、`hr.xian`、`p.whitespace` |
| Kobo 导出 · 多看式（`koboSpan`） | `scripts/epub_clean_kobo.py` | `style.kobostylehacks` + `../Styles/css.css`、`div#book-columns>div#book-inner`、每段文字被 `span.koboSpan[id=kobo.N.M]` 包裹、`h1.h2`(章)/`h1.h1`(后记)/`h2`(节)、`p.kh`(楷体引文)、`p.no.fs`(年表)、`div.hr`(题词)、`a.duokan-footnote`+`06.png`、`aside`+`ol.duokan-footnote-content` |
| InDesign→calibre 繁中重注本（`_idParaDest`） | `scripts/epub_clean_indesign_calibre.py` | `body#story-N.calibre2` + `div.calibre3`、`h1[id=_idParaDest-N].calibre4>span.small`、`h5.calibre8`/`h6.h6_b`、`p.calibre5`/`p_`/`calibre11`、`p.end`/`end_k`、`p.kai_n`/`kai_nb`、`div.container`+`img.fit`+`p.caption`、`table.calibre9`、`img.pw`(生僻字图)、`div.foot`+`hr.calibre6`+`p.footnote`+`a.ref1`(章内注)、`a.calibre7`(跨文件引用注) |
| 掌阅 ZHANGYUE（`text-title-*`，已语义化稿） | `scripts/epub_clean_zhangyue.py` | `h1.text-title-1-c/-r`、`div.zhangyue-c80>h2.text-title-2[id=sigil_toc_id_N]`、`h3.text-title-3`、`p.bodytext`(本已语义化)、`sup>a[href=#note_N][id=noteref_N]` + 文末 `pre>code` `[注释]`、`p.bodytext>span>a[id=note_N]`、`div.zhangyue-c>img.zhangyue-img`+`p.bodytext-no`+`p.img-note`、`span.fangsong`、`../Styles/Style0001.css`+`jianrong.css`、内联 style |
| Kindle-cn 亚马逊中国（`kindle-cn-*`） | `scripts/epub_clean_kindle_cn.py` | `body.calibre`、`../stylesheet.css`+`../page_styles1.css`、`h1.kindle-cn-heading[id=calibre_pb_0]`、`h2.kindle-cn-heading2`(内嵌空锚 `a[id=sec001].calibre6`)、`h3.kindle-cn-heading3`、`p.calibre1`/`p.kindle-cn-para-2em-indent`/`-no-indent(1)`、`p.kindle-cn-poem-left`、`p.kindle-cn-signature(1)`、尾注 `a[id=chN-back][href=file#chN]>sup.calibre5` + `p.fnote>a[id=chN]`、`div.empty`+20×U+2014、`div.kindle-cn-toc-level(1)`、`div.kindle-cn-bodycontent-div-alone`、`img.kindle-cn-inline-character`、`div.chatu_img`+`gaiword.png` |
| InDesign EPUB3 新版（`ff_serif/fz_*/ti_*`） | `scripts/epub_clean_indesign_epub3.py` | `body#BK7026X-N` + 无 class 外层 `div`、`css/YYYY.N.h.css`、`h1.ff_serif.fz_1-9em.ta_left[id=_idParaDest-N]`、`p.ff_serif.fz_1-0em.ti_2em`、`p.ff_cursive.fz_1-0em.mg-str_2-0em`、`ta_right`、`p.ff_serif.fz_1-6em`、`p.ff_sans.fz_1-0em.ta_center`、`span.ff_serif/ff_sans.fw_900`、`span.ff_cursive.fs_italic`、`a._idFootnoteLink[role=doc-noteref]` + `hr.HorizontalRule-1` + `section._idFootnotes>ol>li._idFootnote>a._idFootnoteAnchor`、`div.mg-str_10pr.mg-end_10pr`、`div[class~=box]`、`<p>　</p>` |

先跑 `analyze` 判断属于哪一套，再选脚本。

## 主要能力

- **脚注 → 尾注**：`[N]` 编号 + 双向回链，章末 `<hr/>` 后集中列出；符号注（`[*]`、`[†]`…）自动分组
- **插图 → chatu**：装饰性重复小图自动删除（或降级为 `sprt`），真插图保留图注
- **引文 → blockquote**：连续引文段合并为一个块，块内每行独立成 `p.bodytext`（不用 `<br/>` 分行）
- **正文 → bodytext**：章副标题并入 `h1`、`h` 标签去 `b`、CSS 链接统一为 `styles.css`
- **杂项**：内嵌 SVG 生僻字图替换为实际字符、全角字母/数字转半角、注释编号方括号化
- **内置校验**：XML 良构、无残留标记、id 唯一、锚点可解析、编号连续、**正文文本完整性**比对

## 用法

放进 opencode 的 skills 目录（`~/.config/opencode/skills/`）并重启，即可用自然语言触发
（例如「按 2do.md 处理 xhtml」「清洗微信读书导出的 EPUB」）。

也可以直接当命令行工具用：

```bash
python scripts/epub_clean.py analyze <dir>           # 体检（只读），输出结构报告
python scripts/epub_clean.py process <dir> --dry-run # 试处理到临时目录
python scripts/epub_clean.py process <dir>           # 正式处理（自动备份 + 校验，不过就不写回）
python scripts/epub_clean.py verify  <dir>           # 独立复检
```

把 `epub_clean.py` 换成上表对应的 profile 脚本即可；子命令完全一致。
KADOKAWA 的 Kobo 导出版本额外加 `--strip-kobo --drop-scripts --drop-kobo-style`。
InDesign / Adept 导出（`<h1 class="f_" id="_idParaDest-N">`、`_idfootnotelink`、`<div type="footnote">`）用 `scripts/epub_clean_indesign.py`。
人民邮电/得到导出（`h1.firstTitle`、`p.content`、`div.pic`、`span.kt_104`、`super[id=refN]`+`noindent[id=annotN]`）用 `scripts/epub_clean_ptpress.py`。

## 要求

- Python 3（只用标准库，无第三方依赖）
- 目标目录为书籍解包后的 `<项目>/xhtml`，同目录应有 `styles.css`
- 脚本会自动把原文件备份到系统临时目录；目录里的 `.bak` 只读跳过

## 文档

完整约定（各 profile 的处理顺序、默认输出格式、已知陷阱）见 [`SKILL.md`](SKILL.md)。
