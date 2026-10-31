---
name: ebook-xhtml-clean
description: 电子书 EPUB xhtml 清洗流水线（二十三套 profile：得到/中华书局、calibre+多看、微信读书/QQ阅读、KADOKAWA 竖排、多看原生图片式注释、InDesign/Adept、人民邮电/得到 p.content 系、多看原生内文/标题 neiwen/biaoti、Kobo 导出·多看式排版 koboSpan/book-columns、InDesign→calibre 繁中重注本 _idParaDest/div.foot、掌阅 ZHANGYUE 已语义化稿 text-title-*/noteref_N、Kindle-cn 亚马逊中国 calibre 混合 kindle-cn-*/chatu_img、InDesign EPUB3 新版导出 ff_serif/fz_*/ti_*、bookcrafter 生成版 bookcrafter-body-paragraph/(N) 纯文本尾注、文景/上海人民 bodyContent-1/fnContent-1 跨文件注、八旗文化繁中 p.kai/ol.footnote、Kindle→calibre 转码版 calibre_4/calibre_7/calibre_18/mbp_pagebreak、旧成果收尾 legacy content/picture/fnotecontent、Google Books 增强版 GBS 扫描页码锚点/ops:switch 固定版式页、Kindle→calibre 第二套类号 blockquote.calibre_13/15 标题、calibre 简类号社科书 p.note/p.block/center1、竖排 EPUB3 vrtl/hltr+tcy+noteref/footnote）——脚注提取为 fnote 尾注列表（[N] 编号、双向回链、符号注分组）、按 h1 合并章节、插图 div 转 chatu（装饰图删除/降级）、引文段合并转 blockquote、内嵌 SVG/图片生僻字替换为实际字符、正文加 bodytext、章副标题并入 h1、解包 header/part div、h 标签去 b、链接 styles.css、全角转半角与注释编号方括号化，并自动校验 XML/链接/编号/正文完整性。当用户说『按照 2do.md 处理 xhtml』、『处理/提取脚注（尾注、注释）』、『清洗/规范化 EPUB xhtml』、『微信读书导出清理』、『KADOKAWA 竖排书处理』、『InDesign/Adept 导出清理』、『得到/人邮导出清理』、『Kobo 导出清理』、『掌阅导出清理』、『Kindle 导出清理』、『bookcrafter 导出清理』、『文景导出清理』，或提到 fnote、bodytext、chatu、noteref、data-wr-footernote、duokan-footnote、note.png、kfont、key1/key2、_idfootnotelink、f_1、firstTitle、kt_104、annot、neiwen、biaoti、duokan-image-single、xian、koboSpan、book-columns、kobostylehacks、_idParaDest、div.foot、ref1、text-title-1-c、zhangyue-c80、sigil_toc_id、noteref_N、kindle-cn-heading、kindle-cn-inline-character、chatu_img、gaiword、ff_serif、fz_1-0em、ti_2em、doc-noteref、_idFootnotes、bookcrafter-body-paragraph、toc-list、bodyContent-1、fnContent-1、chaptertitle-c、txtheading-1-c、contents-1、jzyy_、noindent-copyContent、ol.footnote、fnX-、img.pw、pic-c、span.num2、sigil_not_in_toc、book-title-main、calibre_4、calibre_7、calibre_18、mbp_pagebreak、filepos、calibre:cover 时使用。
---

# EPUB xhtml 清洗流水线

把 EPUB 的 xhtml 转换为标准格式（`bodytext` / `fnote` / `chatu` / `blockquote` + `styles.css`）。
目标目录通常是书籍解包后的 `<项目>/xhtml` 或 `<项目>/EPUB/xhtml`（同目录应已有 `styles.css`）。

## 二十三套 profile（先 analyze 判断，再选脚本）

| 源格式 | 脚本 | 特征 |
|---|---|---|
| 得到/中华书局（纯文本 aside） | `scripts/epub_clean.py` | `<aside epub:type="footnote" id="…">注文</aside>`、`<div style="display: block;text-align:center;">` 图、FZFangSong 引文、`<p><span style="…">` 内联样式、`.bak` 原始文件；**逐字包裹** `<b>似</b><b>是</b>`／`<i>S</i><i>o</i>`（脚本自动合并）、插图 div 的 `style="&gt;display: block;text-align:center;"` 变体（多一个 `&gt;`，`chatu` 也认）、标题 id 常挂在 `h1>span[id=sigil_toc_id_N]`；另有 InDesign 导出版：`div.header0/header1` 外壳 + `div.part` 正文容器（`unwrap_div_class_re` 解包）、脚注锚是 `<sup><a epub:type="noteref"><img class="epub-footnote" alt="注文"/>`（每章同一张「注」小圆图，`step_footnotes` 按 alt/id 配对，转成 `[N]`） |
| calibre + 多看(duokan) | `scripts/epub_clean_calibre.py` | `<body class="calibre2">`、`<p class="calibre7"><span class="calibre10">`、`calibre23` 引文、`<aside…><ol class="duokan-footnote-content"><li>` 脚注、`<div class="calibre13">` 图 |
| 微信读书 / QQ阅读 | `scripts/epub_clean_weread.py` | `<section class="readerChapterContent"><div data-wr-bd="1">`、`<span data-wr-id="layout">`、`<p class="content">` / `<p class="quotation">`、`<span class="reader_footer_note" data-wr-footernote="注释">`、`styles/common.css` + 内联 `<style>` |
| KADOKAWA 竖排/固定版式 | `scripts/epub_clean_kadokawa.py`（**只做阶段二**） | `<html … xml:lang="zh-TW" class="hltr">`、`../style/book-style.css`、`<p class="mfont font-1em10">` 空段、`<p>　　<br/></p>` 版式空行、`class="kfont"` 引文、`class="key1"/"key2"` 注释锚点、`mokuji-` 锚点 |
| 多看原生（图片式注释标记） | `scripts/epub_clean_duokan.py` | `<p class="text">`、`<h2 class="chapter-title2" id="sigil_toc_id_N">`、`../Styles/stylesheet.css` + `oxenfont.css`、正文 `<a class="duokan-footnote" …><img src="../Images/note.png"/></a>`、文末 `<ol class="duokan-footnote-content">` |
| InDesign / Adept | `scripts/epub_clean_indesign.py` | `<body … class="calibre">`、`<h1 class="f_" id="_idParaDest-N">`、`<p class="f_1">` / `f_2` / `f_4`、注文/回链类 `_idfootnotelink`（常带 `pcalibre*`）、脚注 `<div type="footnote" id="footnote-N">`、插图 `<div class="mg_l_*">`、`<span class="kfont">` 题词 |
| 人民邮电/得到（`p.content` 系） | `scripts/epub_clean_ptpress.py` | `xml:lang="zh-hans"`、`<h1 class="firstTitle" id="sigil_toc_id_N">`、`<p class="content">` / `content_100..110`、`<div class="pic">`+`imgtitle` 图、`<span class="kt_104">` 楷体、`<span class="super" id="refN">`+`<p class="noindent" id="annotN">` 注释 |
| 多看原生·内文/标题（`neiwen`/`biaoti`） | `scripts/epub_clean_duokan_biaoti.py` | `<p><span class="neiwen">`（变体 `neiwen2/2_1/3/4/5/6`）、`<h1><span class="biaoti1">…<br/><span class="biaoti2">`、`<h2><span class="biaoti3">`/`biaoti5`、`<div class="duokan-image-single">` 插图（`duokan-image-maintitle/subtitle`）、`<a class="duokan-footnote" href="#foN" id="forefN"><img src="../images/note.png"/></a>`、文末 `<ol class="duokan-footnote-content">`、`<hr class="xian"/>`、`<p class="whitespace">&#160;</p>` |
| Kobo 导出·多看式排版（`koboSpan`） | `scripts/epub_clean_kobo.py` | `<style class="kobostylehacks">` + `../Styles/css.css`、`<div id="book-columns"><div id="book-inner">`、**每段文字被 `<span class="koboSpan" id="kobo.N.M">` 逐句包裹**、`<h1 class="h2">章名</h1>` / `<h1 class="h1">后记</h1>` / `<h2>一</h2>`、`<p class="kh">` 楷体引文、`<p class="no fs"><b>年份</b></p>`、`<div class="hr">` 题词、`<a class="duokan-footnote" …><img src="../Images/06.png"/></a>` + `<aside><ol class="duokan-footnote-content">` |
| InDesign→calibre 繁中重注本（`_idParaDest`） | `scripts/epub_clean_indesign_calibre.py` | `<body id="story-N" class="calibre2">`、`<div class="calibre3">` 包裹、`<h1 id="_idParaDest-N" class="calibre4"><span class="small">标签</span>　章名</h1>`、`<h5 class="calibre8">`、`<h6 class="h6_b/h6_s">`、正文 `<p class="calibre5/p_/p_b/p_s/calibre11/text_tp">`、`<p class="end/end_k">`、`<p class="kai_n/kai_nb">`、`<div class="container"><img class="fit"/><p class="caption">`、`<table class="calibre9">`、生僻字图 `<img class="pw" src="image/a1.jpg"/>`（a1=燠 a2=賴）、章内脚注 `<div class="foot"><hr class="calibre6"/><p class="footnote"><a id="foot-NNN" href="#back-NNN" class="green">[N]</a>` + 正文 ref `<a id="back-NNN" href="story-N.xhtml#foot-NNN" class="ref1">N</a>`、跨文件引用注 ref `<a id="back-aN" href="story-28.xhtml#foot-aN" class="ref1">` / 注 `<p class="footnote_a/b/c"><a id="foot-aN" href="#back-aN" class="calibre7">N</a>` |
| 掌阅 ZHANGYUE（`text-title-*`，已语义化稿） | `scripts/epub_clean_zhangyue.py` | `<h1 class="text-title-1-c/text-title-1-r">`、`<div class="zhangyue-c80"><h2 class="text-title-2" style="padding-left:3.5em;text-indent:-3.5em" id="sigil_toc_id_N">`、`<h3 class="text-title-3" id="sigil_toc_id_N">`、正文 `<p class="bodytext">`（本已语义化）、文件内尾注 `<sup class=""><a href="#note_N" id="noteref_N">N</a></sup>` + 文末 `<pre><code><b>[注释]</b></code></pre>` 与 `<p class="bodytext"><span class=""><a href="#noteref_N" id="note_N"> N</a></span>`、图 `<div class="zhangyue-c"><img class="zhangyue-img"/><p class="bodytext-no">图题</p><p class="img-note">图注</p><hr/>`、`span.fangsong`、`../Styles/Style0001.css`+`jianrong.css`、内联 style |
| Kindle-cn 亚马逊中国（`kindle-cn-*`，calibre 混合） | `scripts/epub_clean_kindle_cn.py` | `<body class="calibre">`、`../stylesheet.css`+`../page_styles1.css`、`h1.kindle-cn-heading[id=calibre_pb_0]`、`h2.kindle-cn-heading2`（内含空锚 `<a id=sec001 class=calibre6>`）、`h3.kindle-cn-heading3`、正文 `p.calibre1`/`p.kindle-cn-para-2em-indent`/`-no-indent(1)`、`p.kindle-cn-poem-left`、`p.kindle-cn-signature(1)`、文件内尾注 `<a id=chN-back href=file#chN><sup class=calibre5>[N]</sup></a>` + `<p class="fnote"><a id=chN>`、尾注前 `div.empty`+20×U+2014、`div.kindle-cn-toc-level(1)`、图片页 `div.kindle-cn-bodycontent-div-alone`、生僻字图 `img.kindle-cn-inline-character`、`div.chatu_img`+`gaiword.png` 广告 |
| InDesign EPUB3 新版（`ff_serif/fz_*/ti_*`） | `scripts/epub_clean_indesign_epub3.py` | `body#BK7026X-N` + 无 class 外层 `div`、css 链 `css/YYYY.N.h.css`、`h1.ff_serif.fz_1-9em.ta_left[id=_idParaDest-N]`、正文 `p.ff_serif.fz_1-0em.ti_2em`、`p.ff_cursive.fz_1-0em.mg-str_2-0em`（引文）、`ta_right`（署名）、`p.ff_serif.fz_1-6em`（小标题）、`p.ff_sans.fz_1-0em.ta_center`、行内 `span.ff_serif/ff_sans.fw_900`、`span.ff_cursive.fs_italic`、尾注 `a._idFootnoteLink[role=doc-noteref]` + `hr.HorizontalRule-1` + `section._idFootnotes>ol>li._idFootnote>a._idFootnoteAnchor`、图 `div.mg-str_10pr.mg-end_10pr`、引文框 `div.…box`、`<p>　</p>` |
| bookcrafter 生成版（磨铁 / Z-Library） | `scripts/epub_clean_bookcrafter.py` | `<html … xml:lang="zh-CN">`、`../Styles/style.css` + 内联 `<style>body p.bookcrafter-body-paragraph{…duokan-text-indent…}</style>`、`<h1 style="font-size:1.45em;text-align:center;…">`、正文全为 `<p class="bookcrafter-body-paragraph">`（无 span/img/br）、**脚注是纯文本编号**：正文 `  (1)  `、章末 `<p class="bookcrafter-body-paragraph">(1) 　注文</p>` 连续成块、目录页 `div.toc-list` |
| 文景/上海人民（`bodyContent-1`，跨文件注） | `scripts/epub_clean_bodycontent.py` | `<html … xml:lang="zh-cn">`、`../Styles/stylesheet.css`+`stylesheet-1.css`、`h1.chaptertitle-c/parttitle-c/prefacetitle-c/backtitle-c[id=isbn…]`、`h3.txtheading-1-c`/`h4.txtheading-2-c`、`p.bodyContent-1(-top/-top-2/-c)`、`p.noindent-copyContent-1`、`p.hang-bodyContent-1`（译名表）、`p.bodyContent-2-kaiti(-top-4)` 楷体引文、**跨文件脚注** `<a href="partNNNN.xhtml#jz_X" id="jzyy_X"><sup>(N)</sup></a>` + `<p class="fnContent-1"><a href="…" id="jz_X">(N)</a>`、`div.chatu_img/title_img>img.pic-img`、`p.contents-1/2/3` 三级目录 |
| 八旗文化（繁中 InDesign，`p.kai`/`ol.footnote`） | `scripts/epub_clean_baqi.py` | `<html … xmlns:epub>（无 lang）`、`../Styles/Style.css`(+`Copyright.css`)、`h1/h2[title]` 内 `<span class="num">`+`<span class="num2">`、`h3.h3.sigil_not_in_toc`、正文 `<p>` 无 class、`p.kai`/`div.kai` 楷体引文、`p.sec`（* * *）、`div.pic/pic-c>img+span.caption`、**章末** `<a class="footnote" href="#fnX-N" id="fX-N">[N]</a>` + `<ol class="footnote"><li id="fnX-N">…<a href="#fX-N"><img class="pw" src="../Images/back.png"/></a></li>`、`p.ref`（书目）、`p.title`+`p.item`（名词释义）、`div.boxend`、`<p><br/></p>` |
| Kindle（AZW3 经 calibre 转码，`calibre_4/7/13/18`） | `scripts/epub_clean_kindle_calibre.py` | `<body class="calibre">`、`stylesheet.css`+`page_styles.css`、**几乎无 h 标签**：标题/图/正文全压在同一批组合类上——`p.calibre_4`（内 `<span class="bold">`=标题 / 内 `<img>`=插图）、`p.calibre_7`（正文，内层 `span.calibre_18` 只是整段字体壳）、`p.calibre_13`（引文落款）、`p.calibre_9`（书内目录）、`p.calibre_3`（空 `<p id="fileposN">` 锚点块，书内目录的链接目标，**须保留**）、`div.calibre_14`（空）、`div.mbp_pagebreak`（分页符，`id="calibre_pb_N"`）、`titlepage.xhtml` 带 `<style>@page` 的封面页（转 `body.cover`）、脚注 ref 为**同一张「注」圆圈图标**（4 个文件名同图，`<sup class="calibre7"><small class="calibre8"><img …/></small></sup>`，**不含数字**）+ 注文 `<ol class="calibre_15|17"><li value="1" class="calibre_16">`（value 恒为 1）；章标题常拆成 `第N章`／`章名`／`副标题` 连续多条，用 `<br/>` 合并；**无注文文件中**同形态文字 `sup` 是表格上标数字残渣（一个字符一个 sup，如 `9,847,009`），须原样解包不加 `[N]` |
| Kindle-cn 三联/学术注释版（`p.calibre8` + `kindle-cn-noindent`） | `scripts/epub_clean_kindle_cn2.py` | `<body id="…" class="calibre">`、`../stylesheet.css`+`../page_styles*.css`、正文 `<p class="calibre8">` / `p.kindle-cn-para-no-indent` / `p.kindle-cn-para-2em-indent`、小节标题 `<p class="kindle-cn-noindent">一　平民家世</p>`（年表里同一类装「前256年·秦昭王五十一年」）、正文外壳 `div.kindle-cn-toc-level1`（不是目录）、`h2.calibre6` 节标题（内嵌 `<a id=secNNN>`）、尾注 `<a id=chN-back href=…><sup class="calibre3">[N]</sup></a>` + `<p class="fnote">`、分隔 `<div class="empty"></div>`+20×—、图页 `div.kindle-cn-bodycontent-div-alone`（**可嵌套**）、图注 `p.kindle-cn-picture-txt-withfewcharactors/-withmanycharactors`、`table.kindle-cn-picture-parallel` 双图、版权页 `p.kindle-cn-copyright-text`、`span.kindle-cn-bold/-hei/-kai1`、行内字图 `img.kindle-cn-inline-image1`（`rare_map.json`） |
| Kindle→calibre 第二套类号（标题是 `blockquote.calibre_13/15`） | `scripts/epub_clean_kindle_calibre2.py` | `<body class="calibre">`、`stylesheet.css`+`page_styles.css`、**标题不是 h1 而是 blockquote**：`blockquote.calibre_13`（章号/單元名）+ `blockquote.calibre_15`（章名）、节标题 `p.calibre_4`（内 `span.calibre1>span.bold`）、正文 `p.calibre_7/_8/_16/_20/_26/_30`、推荐序署名 `p.calibre_6`、图 `p.calibre_`|`p.calibre_NN` 内单独 `<img>` + 图注 `blockquote.calibre_18`、尾注 `ol.calibre_11>li.calibre_12`（回链 `a>span` 里是 ↺）+ 正文 `sup.calibre3>small[id=fileposN]>a>span` 的 `[N  ]`、有序引文清单 `ol.calibre_11>li.calibre_25`、参考文献 `p.calibre_28`+`ul.calibre_29>li.calibre_25`、目录页 `p.calibre_31`(Table of Contents)+`ol.calibre_33/35>li.calibre_34`、空壳 `<a></a>` / `div.calibre_10|24|32` / `div.mbp_pagebreak` |
| calibre 简类号社科书（`p.note` 注文 + `p.block` 引文） | `scripts/epub_clean_calibre_simple.py` | `<html … xml:lang="zh-CN">` + `../Styles/style0001.css`、正文 `<p>` 无 class、引文/条文 `<p class="block">`、图 `<p class="center"><img/></p>`(+`<p class="img">图注</p>`)、题词 `p.center1`+`p.lk`、脚注 `<a id="wN"></a><a href="文件#mN"><sup>[N]</sup></a>` + 章末 `<hr/>` + `<p class="note"><a id="mN"></a>…`、书内目录 `<ul><li><a href="partNNNN.xhtml#aNNN">`（可嵌套）、封面 `cover_page.xhtml`（内联 `<style>`+SVG）、前折口/书名页/后折口/封底 纯图页、CIP 版权页独立文件 |
| 旧成果收尾（legacy `content`/`picture`/`fnotecontent`） | `scripts/epub_clean_legacy.py` | `<p class="content">`、`<div class="picture">`+`p.imgIntro`、`<sup><a id=chN href=file#chN-back>[N]</a></sup>`+章末 `<hr/>`+`p.fnotecontent`、`p.contents1/2`、`p.inscribe`、`div.copyright.margin-left2`、书名页 `bookTitle/booksubname/author/publish`、`style0001.css` |
| Google Books 增强版（GBS，`ops:switch` 固定版式页） | `scripts/epub_clean_gbs.py` | opf 里 `<meta content="GoogleEbooks" name="GBSEpubSource"/>` + `_page_map_.xml` + spine `page-map`、正文夹 4000+ 个扫描页码锚点 `<a id="GBS.0059.02"/>` 与 `<div style="display:none;">…</div>`、封面/书名页/部扉页是 `<ops:switch><ops:case><svg><image xlink:href="image/part01.jpg"/></svg></ops:case><ops:default><img src="inserted_file_…_svg_raster.jpeg"/></ops:default></ops:switch>`、正文 `<p>` 无 class、引文 `p.sans0/sans/skai`、插图 `div.picbox>p.pic>img.w100`+`p.caption`、尾注 `p.footnote[id=foot-N]`+正文 `a.ref[id=back-N]`、章首 `p.leading`（第一/第二/第三）+`h2`、书内目录 `p.chapter`（篇）/`p.part`（章）/`p`（节）、`h3.p0` 目次 |
| 竖排 EPUB3（`vrtl/hltr` + `tcy` + `noteref/footnote`） | `scripts/epub_clean_vertical.py` | `<html class="vrtl|hltr" xml:lang="zh-TW">`、`../Styles/style-standard.css`+`style-advance.css`+`book-style.css`、`<body class="bodymatter" epub:type="bodymatter">`、`<p>` 无 class、`<p id="fp">`、`<h1 id="toc_index_N"><span class="tcy">9.</span><br/>标题<br/><small>副题</small></h1>`、`span.tcy`（縦中横）、`p.kfont`+`p.kfont.text-right` 题词、`p.t4 kfont` 年表、`p.sep` 分隔图、`img.full`、`a[id=fnref_N][href=#fn_N][class=noteref]` + `div.footnotes>div.footnote` 尾注、整页图版 `<svg viewBox=0 0 1444 2048><image xlink:href/><title>图注</title></svg>`、`nav.xhtml` |

**注意**：KADOKAWA 书几乎没有语义标签，需**先人工做阶段一语义化重排**（规则见下），脚本只做阶段二
（全角→半角 + 注释编号方括号化）。

二十三套脚本的子命令、备份、校验机制相同（analyze / process / verify，`--dry-run` 试跑）。
所有脚本同时收录 `*.xhtml` 与 `*.html`（部分书目标目录用 `.html` 扩展名）。

## 环境要点

- 用 `python -X utf8` 运行（Windows 上若 PATH 里的 `python` 是 Microsoft Store 假桩、
  静默无输出，改用 `py -3` 或 `where python` 找到的真实解释器完整路径）。
- 控制台输出中文可能乱码：`analyze` 用 `-o 报告路径` 写文件再读；process/verify
  的输出行以 ASCII 为主，可直接看。
- 文件一律 UTF-8 无 BOM、LF 行尾（脚本已按此读写，保持原样）。
- 目录里的 `.bak` 是保留的原始文件，**只读、绝不修改、处理时自动跳过**。
- 处理前脚本自动把原文件备份到系统临时目录 `<TEMP>/opencode/epub-clean/<目录名>-<时间戳>/`。

## 工作流

0. **先放 styles.css**：skill 自带 `assets/styles.css`（规范版，以此为准）。处理前把它复制到目标目录
   （各 profile 的 `process()` 已自动调用 `ensure_styles(dirpath)`：缺则复制、不同则覆盖、相同不动；
   `process` 日志里出现 `styles.css: updated/copied` 即生效）。目标目录的 `styles.css` 一律以这里为准，
   不要在书里另维护一份。当前版本 6087 B / MD5 `44902CE72304D3D3E8698560CE24EB78`（《意外的國度》手工修改：
   `.caption/.image` 字号 0.95em、行高 1.4、`max-width:90%`、`margin:0 auto`；另加嵌套列表规则
   `ul ul, ol ol, ul ol, ol ul { padding-left:.5em; padding-top/bottom:0 }`，避免逐级加倍缩进。
   此前版本 5732 B / `CCD6B717…`、5716 B / `8C24BC37…`（《秦崩》版））。
1. **读规则**：读目标目录的 `2do.md`（或用户口述）。没有 2do.md 就把用户需求映射到
   默认约定（下节），有出入再问用户。
2. **体检**：`SCRIPT analyze <dir> -o <临时目录>\report.txt`，Read 报告。重点看：
   - aside/noteref 数量是否相等、重复 id、预配对是否 0 异常
   - 插图 div 布局是否有变体、引文样式 span 有多少（caption vs 引文）
   - span 样式清单（识别应保留的东西；若正文 span 还带内联样式＝原始状态，
     把报告给出的 `pre_strip 候选` 写进配置）
   - `内嵌 SVG 字图` 清单：逐个辨识字符（结合上下文引文核对古籍原文；辨识不了
     用浏览器打开 SVG 看字形，或问用户），写入 `inline_glyph_map`
3. **定配置**：与默认规则一致则无需配置文件；有差异（不同样式标记、禁用某规则、
   字图映射、pre_strip）就在目标目录写 `clean_config.json`（schema 见脚本头部
   DEFAULT_CONFIG）。2do.md 里有内置规则覆盖不了的转换（如 epigraph→
   blockquote.intro、figure/figcaption→chatu），写 `custom_clean.py` 挂钩子
   （`extra_steps() -> [(name, fn)]`）。
4. **处理**：`SCRIPT process <dir>`（先 `--dry-run` 输出到临时目录人工抽查更稳妥）。
   脚本内置校验（XML 良构、无残留、id 唯一、内链可解析、编号连续、图片存在），
   任何文件不过校验就不写回并整体 FAIL。注意：图片存在性按 `<dir>/../images` 校验，
   若在临时目录试处理须镜像 images 目录，否则会 FAIL。
5. **报告**：向用户汇报计数表（pre/glyph/chatu/fnotes/fs/bodytext/sub/bold/join/
   unwrap/hB），并说明保留项与判断项。

## 默认输出约定（经用户确认/精修，勿重复询问）

- 排版规范化（`epub_clean_common.normalize_typography()`，各 profile 写出前自动执行）：
  `U+00A0`（NBSP）→ 普通空格；**`○`（U+25CB）→ `〇`（U+3007）**（年份、卷次、数量里的「零」，
  正文/脚注/图注/书目录/alt 里的全部替换，编号 `二○○○年`→`二〇〇〇年`、`卷八○`→`卷八〇`）；
  中英文/数字之间不留空格（`A4 大小`→`A4大小`）；
  缩写点前不留空格（`T .S .`→`T.S.`）；逐字 `<i>` 合并（`<i>阿</i><i>提</i>`→`<i>阿提</i>`）；
  两个 `<p>` 不挤在同一行；**每个 xhtml 一律以 `<?xml version="1.0" encoding="utf-8"?>` 独占一行开头**
  （`epub_clean_common.ensure_xml_decl()`：缺则补、`<?xml version='1.0'?>`
  /`encoding="UTF-8"`/`standalone="no"` 等变体统一改写，且声明后换行（BOM 不碰）。
- **段首不留全角空格**：源书用「　　」手工缩进的，一律删掉 —— `styles.css` 的 `text-indent` 已负责两格，留着会叠成四格。`epub_clean_common.strip_indent_spaces()` 在 `postprocess()` 里自动执行（旧成果用 `epub_clean_fix.py process <dir>` 补跑，`verify` 会报残留）。`center`、`left`、`right`、`poem/poems`、`caption`、`toc`、`sprt`、`image`、`fnote`、`author`、`title/subtitle`、`logo`、`cover` 这些类的段首空格保留（空格可能是版面意图）。
- **`<html>` 的语言一律 `zh-CN`**：`zh-TW`、`zh-Hant`、`zh-Hans`、`zh-HK`、`zh-cn` 等变体（`lang` 与 `xml:lang` 两个属性）都改成 `zh-CN`，纯 `zh` 保持。`epub_clean_common.normalize_lang()` 在 `postprocess()` 里自动执行；旧成果用 `epub_clean_fix.py process <dir>` 补跑，`verify` 会报残留。注意只改 html 标签，`content.opf` 的 `dc:language` 不动（需要时另行统一）。
- **`<blockquote>` 内的 `<p>` 一律带 `class="bodytext"`**（默认规则，`epub_clean_common.blockquote_bodytext()`
  自动补；`blockquote.poem/menu` 等特例由 css 的 `blockquote.poem p` 覆盖，不用另写 class）。
- 脚注：正文 `<sup><a epub:type="noteref" href="#footnote-x" id="noteref-N">[N]</a></sup>`；
  章末 `<hr/>` 后 `<p class="fnote" id="footnote-x"><a href="#noteref-N">[N]</a> 注文</p>`；
  编号每文件从 [1] 重新开始；重复的 footnote id 输出时加 `-2`/`-3` 后缀消歧
  （noteref→aside 按 alt 文本精确配对，aside 正文为权威文本）。
- 插图：`<div class="chatu">` + `<p class="image"><img src=... alt=""/></p>` + `<p class="caption">`。
  **两个 `chatu` 之间不放 `<p class="sprt">`**（连续插图之间不需要分隔符），已有则删 ——
  只处理「chatu → sprt → chatu」这一种，其余 sprt（如 chatu 后接正文的分隔）保留。
  **正文中同一 (img src + 图注) 的 chatu 只保留首次出现**（跨文件去重）；
  **彩图页**（整页插图墙：chatu ≥ 3 且正文段 ≤ 2）整体跳过：不去重、也不参与后续比对。
  以上两条统一由 `scripts/epub_clean_common.py`（`dedupe_chatu()` / `strip_sprt_between_chatu()`，
  入口 `postprocess()`）实现，各 profile 写出前调用。
- 引文：整段 FZFangSong 仿宋引文，连续段合并为一个 `<blockquote>`，内部每段一律
  `<p class="bodytext">`（脚本自动补，见上），段内 noteref 保留。**blockquote 内不用 `<br/>` 分行：
  每一行各自成一个 `<p class="bodytext">`**（诗歌、多行引文按行拆段）。
- 章副标题：h1 后紧跟的居中样式段并入 h1 →
  `<h1>标题<br/><span class="subtitle">——副题</span></h1>`（h1 内原有 span/b 标签去掉）。
  **例外**：若源标题分「章号行 + 书名行」两行（如多看 `biaoti1`+`biaoti2`），
  `.subtitle` 包**章号行**、书名行作正文（`<h1><span class="subtitle">第二章</span><br/>书名</h1>`）。
- 加粗引导段（整段）：去样式 → `<p class="bodytext"><span><b>（一）…</b></span></p>`；
  行内嵌套加粗 span 同样去 style（保留 span+b）。处理后全文件不应残留任何
  `<span style=`。
- 内嵌 SVG 生僻字：按 `inline_glyph_map` 替换为实际字符，跨行段落合并为单行。
- bodytext 覆盖所有正文段，**包括前置文件**（作者简介、插图目录；版权页 span 保留
  id、去内联样式）。作者简介页首行的人名用户偏好改为 `<h2>人名</h2>`（手工判断，
  遇到时照做）。
- h1–h3 去 `<b>`，同时去掉 h 内 span 的内联样式（保留 id）。
- 保留不动：空 `<div id="文件名">` 容器、已有的其他 css 链接（如 cover.css）。
- 处理顺序固定不可变：pre_strip → inline_glyphs → chatu → footnotes → blockquote →
  unwrap → merge_emphasis → h1_subtitle → bold_bodytext → bodytext → join_multiline_p → h_fix →
  css → append（chatu 先于引文规则消费 fangsong caption；footnotes 先于引文规则
  以免 aside 割裂连续性；unwrap 先于 bodytext/h1_subtitle；merge_emphasis 在 unwrap 后、
  bold_bodytext 前，把逐字 `<b>/<i>` 合并成一个标签）。

## calibre + duokan profile 约定（epub_clean_calibre.py，**配置驱动**）

calibre 的 `calibreNN` 类号**每本书都不同**（按首次出现顺序分配），所以本 profile 全部角色都走配置：
默认值见脚本头 `DEFAULT_CONFIG`，目标目录放 **`<dir>/clean_config.json`**（顶层键覆盖默认；`-c` 可另指）。
`analyze` 会列出各文件的 p/span/div/hN 类号与图片尺寸，据此写配置。

主要 CONFIG 键：

| 键 | 作用 |
|---|---|
| `p_para` | 段落容器 `<p class="…">`（默认 `calibre7`）|
| `body_spans` | 正文 span → `<p class="bodytext">`（去 span，span 上的 id 移到 `<p>`）|
| `quote_spans` | 引文 span（连续段合并 `<blockquote>`，块内每行独立 `<p class="bodytext">`）|
| `sig_span` | 引文**后紧跟的落款** span → 并进块内 `<p class="right">` |
| `epigraph_class` / `poem_class` | **章首题词**（body 内本块前无 `<p>`/`<h2>`）用前者（默认 `intro`）；**正文内带落款的引文**用后者（默认 `poem`）；**无落款**的正文引文用**裸 `<blockquote>`**。⚠️ `intro` 只应出现在标题后，正文内禁 `intro` |
| `lead_spans` | 整段逐字加粗 → `<p class="bodytext"><span><b>…</b></span></p>`（后记「其一」、年表年份等）|
| `head_map` | `{类号: 标签}` → `<hN>`（类号可在 hN 标签上，也可在 `<p class="p_para"><span class="…">` 里；保 id、去 span/逐字 b）|
| `h1_spans` | `<h1><span class="…"><b>…</b></span></h1>` → `<h1>` |
| `fig_div` | 插图 div → `chatu` |
| `caption_spans` | 图后的图注 span → `<p class="caption">`（多行 `<br/>` 合并）|
| `sub_span` | `<sub class="…">` → `<sub>` |
| `italic_spans` | 去 span 保留内容（保留 `<i>`）|
| `author_span` / `date_span` | 正文底部署名/日期 → `<p class="right">` + 前置空行段 |
| `bold_spans` | 逐字 `<b class="…">` 去标签保留文字 |
| `cover_page` | `<body><img/></body>` → `<div class="chatu">` |
| `head_sub_relocate` | `{标题类号: 引导段类号}` 把**源里误置于标题的 `<sub>` 数字**挪到紧随其后的引导段（如年表首条年份）|
| `ornament_max_bytes` / `drop_images` | 装饰图判定（小于阈值或列名单）；**紧邻标题(h1–h4)前后 → 整块删除**，否则 → `<p class="sprt"><img/></p>`；真插图 → `chatu`。`0` = 不判装饰图 |

其余固定行为：

- `aside`（`<ol><li>`）+ noteref → 章末 `<hr/>` + `<p class="fnote">`，`[N]` 每文件从 1、双向回链；
  **配对优先按 id，失败回退按文档顺序**（源里常有缺 id / 重复 id，但 noteref 的 alt 与 aside 正文逐条一致）；
  `aside > ol > li` 之间允许任意空白（源里常写成 `</li> </ol> </aside>`）
- **支持 `<dir>/custom_clean.py` 钩子**（与 profile A 一致）：`extra_steps() -> [(name, fn)]`，
  `fn(c, name, ctx, cfg) -> c`；插入位置由 `clean_config.json` 的 `custom_steps_position`
  指定（内置步骤名 / `"pre"` / `"post"`，默认 `"post"`）。本书特有的结构（图注正文用 `<sub>` 排小字、
  引文内嵌正文 span、参考文献条目、生僻字图、标题页合并后的层级）优先写进这里，不改内置规则
- css 链接 → `styles.css`（删除 `styleNNNN/stylesheet/page_styles/fonts.css`）
- `<body class="…">` → `<body>`；`wrapper_div`（默认 `calibre3`）解包；清理空行与行首缩进
- 源文件可能是 **CRLF**，读取时统一为 LF
- 装饰图常见形态：同一张很小的图（十几 KB）在小节标题后反复出现；真照片通常 ≥ 80KB，阈值以 analyze 为准
- **脚注标记常为图片**（`<img src="../images/…png"/>`，几千字节、重复出现）；它们由脚注步骤消费，
  不要当成装饰图（analyze 的小图清单里会出现，属正常）
- 编辑判断（不自动化，遇到时照做）：
  - **章首图**（章节第一张图）按惯例手工改成 `<h1 title="第X章 …"><img/></h1>`（skill 的图片页约定）
  - 诗歌引文若与相邻正文诗行混标 → 统一处理
  - **年表/大事记类文件的条目**（`<p><span class="calibre25">年份</span></p>` + 条目段）不映射成 h3/h4：
    年份行做成 `<p class="bodytext"><b>年份</b></p>`，条目段 `p.bodytext`，每组之间插空行段
  - **参考文献/书目条目**用 `p.bodytext`（不用 `bodytext-noindent`，书里不另设悬挂缩进类）
  - **列传体章节**（古籍原文 + 今译对照）：原文 `p.bodytext`、今译 `p.bodytext > span.kai`，中间插空行段
  - **正文引用的古籍原文**包 `<blockquote><p class="bodytext">`（不加 class、不加 `span.kai`）
  - **节标题「一、xxx」** 编号并入标题一行（`<h2>一、…</h2>`），不用 `subtitle` 分行
  - 详见「人工精修清单」——同类内容一律按该清单处理


## Kobo 导出 · 多看式排版 profile 约定（epub_clean_kobo.py）

源：**Kobo 阅读器导出**的「多看」式 EPUB（`<style class="kobostylehacks">` + `../Styles/css.css`；
`<div id="book-columns"><div id="book-inner">` 包裹；**每段文字被 `<span class="koboSpan" id="kobo.N.M">` 逐句包住**）。
文件常为 `101.xhtml`…`NNN.xhtml` + `cover.xhtml`。

识别特征：

- `<body class="fen">`（章标题页）/ `body class="copy"`（版权页）/ 无 class（正文）
- 章标题页 `<h1 class="h2">楔子　北境</h1>`；后记/年表/书目 `<h1 class="h1">…</h1>`；
  节 `<h2>一</h2>`；小节 `<h3 id="sigil_toc_id_N"><span class="h3kt">古籍</span></h3>`
- 正文 `<p>`；后记/书目/年表 `<p class="fs">`、`<p class="no fs"><b>年份</b></p>`
- 楷体引文 `<p class="kh">`；章首题词 `<div class="hr"><p class="fs center">…</p><p class="fs right">——落款<br/>《出处》</p></div>`
- 装饰空块 `<div class="logo">` / `<div class="image">`
- 脚注标记 `<a class="duokan-footnote" epub:type="noteref" href="#B_N" id="A_N"><img src="../Images/06.png"/></a>`；
  文末 `<aside epub:type="footnote"><div><hr class="xian"/></div><ol class="duokan-footnote-content">
  <li class="duokan-footnote-item" id="B_N"><p class="footnote"><a href="#A_N">⊙</a>注文</p></li></ol></aside>`

处理顺序（脚本 STEPS，固定不可乱）：css → body → kobo(去 koboSpan) → wrap(解包) → dropdiv → headings → footnotes → epigraph → quotes → paras → tidy → append

1. **css**：删 `<style class="kobostylehacks">` 与 `../Styles/css.css` 链接 → `styles.css`
2. **koboSpan**：`<span class="koboSpan" …>…</span>` 去标签保留文字（含空 span）
3. **wrap**：`#book-columns` / `#book-inner` 深度计数解包
4. **dropdiv**：`div.logo` / `div.image`（空装饰）与 `style="page-break-before:always"` 的 div 整块删除
5. **headings**：`<h1 style="display:none">` 删；`h1.h1`/`h1.h2` → `<h1>`（保 id）；`<h3><span class="h3kt">` → `<h3>`
6. **footnotes**：`aside` 内 `<li id="B_N">` 的注文收集、整块删；正文 `<a class="duokan-footnote">` → `[N]`
   （每文件从 1、`href=#B_N` ↔ `li id=B_N`、双向回链），章末 `<hr/>` + `<p class="fnote" id="B_N">`
7. **epigraph**：`div.hr` → `<blockquote class="intro">`（引文行 `p.bodytext`、落款行 `p.right`；块内 `<br/>` 拆成独立段）
8. **quotes**：`<p class="kh">`（连续）→ `<blockquote><p class="bodytext">…`（每行独立段）
9. **paras**：其余 `<p …>` 统一 → `bodytext`（`right`→`p.right`、含 `center`/`vol`→`p.center`），去段首全角空格
10. **收尾**：清理空行与行首缩进

**保留不动**：`cover.xhtml` 的 SVG（`<image xlink:href="../Images/03.jpg"/>` 原样）。

**校验**：XML 良构、无残留（`koboSpan` / `kobo.` / `duokan-footnote` / `<aside` / `class="kh|fs|no|h3kt"` /
`book-columns` / 旧 css）、id 唯一、内链可解析、图片存在、注释标记数 == 尾注数。

**注意**：正文标记、脚注图片标记（`06.png`，115 次引用）都是图片式；脚注步骤会消费标记，故图片清单里
`06.png` 属正常。版权页里的「制作组页脚」（如 `<p class="center">阿獴读书·阅读经典</p>`）会按正文保留，
如需删除请手工处理。


## 微信读书 / QQ阅读 profile 约定（epub_clean_weread.py）

处理顺序（依赖关系，不可乱）：

1. **头部**：`styles/common.css` 链接 + 内联 `<style>…</style>` → `<link rel="stylesheet" href="styles.css" />`
2. **分隔符**：`<p class="content|quotation"><span>*　*　*</span></p>` → `<p class="sprt">*　*　*</p>`
3. **脚注**：`<span class="reader_footer_note js_readerFooterNote" data-wr-co="N" data-wr-footernote="注文"></span>`
   → 文中 `<a class="ref" href="#note_N" id="noteref_N"><sup>[N]</sup></a>`（**每文件从 1 编号**）
4. **引文**：`<p class="quotation">` → `blockquote > p.bodytext`，**连续段合并进同一个 blockquote**
   （不可按行做：`</p>` 后可能紧跟 `<div>` 或跨行；用「打临时标记再合并」两步法）
5. **正文**：`<p class="content">` → `<p class="bodytext">`（精确匹配 `class="content(?=[\s"])`，
   不碰 `content-c`/`content-b`/`newContentCR` 等）
6. **清理**：6a 移除无 class 的 span（layout 包裹，需平衡匹配处理嵌套）；
   6b 移除 `data-wr-co` / `data-wr-id`；6c 拆 `quotation-inline` span（保留 `italic`/`text-sup`）
7. **结构**：补齐缺失的 `</div></section>`（按 div/section 计数各缺多少补多少）
8. **尾注块**：`<hr/>` + `<p class="fnote" id="note_N"><a href="#noteref_N">[N]</a> 注文</p>`，
   插在 `</div></section>` 前

**符号注**（注文以 `[*]`、`[†]`、`[‡]`、`[§]`、`[¶]`、`[**]` 等纯标点方括号开头，
判定 `^\[([^\w\]]{1,4})\]`）：标记改用符号（`note_sK`/`noteref_sK`），注文去掉开头 `[符号]`；
**符号注排在数字注之前，两组之间留一个空行**，数字注重新从 1 连续编号。

保留 `data-wr-bd` / `data-wr-inset` / `data-book-id` / `data-chapter-uid`；`styles.css` 不修改，
未定义类（`firstTitle`、`force-page-break` 等）原样保留；`.bak` 不动。

**注释章例外**：某章的 `p.quotation` 实为尾注条目（内含锚点链接）时，只做
`class="quotation"` → `class="bodytext"`，不包 blockquote —— 文件名写入 `notes_chapters`，
analyze 会对「quotation 含链接」的文件打 `!!` 标记。

**校验**：除常规项（XML、id 唯一、锚点可解析、blockquote 配对、残留检查）外，process 还会做
**正文文本完整性**比对：源（去脚注 span）与成果（去正文标记与尾注块）分别去标签去空白后应完全相等。



## KADOKAWA 竖排 / 固定版式 profile

源：KADOKAWA 繁体中文竖排书，**HTML 里几乎没有语义标签**——标题/引文/图片全是 `<p>` + class 排版；
缩进靠全角空格 `　　`，空行靠 `<p>　　<br /></p>`。处理分两阶段。

### 阶段一：人工语义化重排（判断性工作，脚本不做）

先把原始文件另存到 `xhtml\o\` 作对照，再逐文件重排。原则：**保留功能性 class**
（`fnote`/`image`/`chatu`/`sprt`/`right`/`subtitle`/`main`），删除纯版式 class 与噪声。

- 头部：`xml:lang="zh-TW" lang="zh-TW"` → `xml:lang="zh" lang="zh"`；
  正文页 `../style/book-style.css` → 同目录 `styles.css`；固定版式扉絵页保留 `fixed-layout-jp.css`
- 去版式噪声：删空行段 `<p>　　<br /></p>`、`<p><br /></p>`；删段首缩进全角空格 `　　`；
  删对齐用全角空格（`作　　者：` → `作者：`）
- 正文段 `<p>` / `<p class="word-break-break-all">` → `<p class="bodytext">`
- 标题：`<p><span class="bold font-1em30">T</span></p>`（+ 紧跟 `font-1em15` 副标题 S）
  → `<h1>T<br/><span class="subtitle">S</span></h1>`；作者/译者 → `<h2>作者　某某</h2>`；
  节标题 `<p id="mokuji-XXXX-N"><span class="gfont15">T</span></p>` → `<h3>T</h3>`；
  扉絵页 `<div class="main"><svg><image/></svg></div>` → `<h1 title="第一章　……"><img src="…"/></h1>`
- 引文：`<p>　　<span class="kfont">Q</span></p>`（夹在空行之间）→
  `<blockquote><p class="bodytext"><span>Q</span></p></blockquote>`（去 `kfont`，留裸 `<span>`）
- 图片：`<p><img …/></p>`（夹在空行之间）→ `<div class="chatu"><p class="image"><img …/></p></div>`
  （保留 `fit`/`width-060per` 与 `alt`）
- 注释：文末注 `<p id="ref1-00N">　<a class="cyu"…>…</a>　正文</p>` →
  `<p class="fnote" id="ref1-00N">…`（加 class、去前导全角空格）；正文中的 `<a class="cyu">` 保持不动
- 分隔符 `<p class="start-7em">*　*　*</p>` → `<p class="sprt">*　*　*</p>`
- 右对齐 `<p class="align-end">` → `<p class="right">`；`<p class="start-5em word-break-break-all">`
  → `<p class="start-5em bodytext">`
- 删除：`kfont`/`gfont15`/`bold font-1emXX`/`word-break-break-all`/`align-end`（已被语义标签取代）；
  保留：`mfont font-1em10`（装饰空段）、`m-before-*`/`m-after-*`/`h-indent-*`/`start-5em`/`main`/目录 `gfont`
- ⚠️ 提升 `<h3>` 时若丢掉 `mokuji-XXXX-N` 的 id，会让目录页的节级链接（`href="…p-XXX.xhtml#mokuji-XXXX-N"`）悬空
  （通常不补回，后期用 Sigil 重排时会自动补全目录与锚点）

### 阶段二：脚本批量收尾（epub_clean_kadokawa.py，确定性）

1. **全角字母/数字 → 半角**：U+FF10–FF19 / FF21–FF3A / FF41–FF5A 减 0xFEE0；
   **标点（，。「」）与全角空格 U+3000 必须保留**
2. **注释编号加方括号**：`<span class="key2"…>N</span>` → `…>[N]<…`；`<span class="key1">N</span>` → `…>[N]<…`
   （容忍两位数被 `<span class="tcy">` 縦中横 包裹并保留之；`href`/`id` 锚点不动）
3. 写回 UTF-8 无 BOM；整串正则替换，**不拆行重组**，以保留行尾与结构

**Kobo 导出变体**（用 Kobo 阅读器导出时常见）：带 `<script src="../../js/kobo.js">`、
`<style id="koboSpanStyle">`、以及大量 `<span class="koboSpan" id="kobo.N.M">` 包裹（注号常被它包住）。
用 `process <dir> --strip-kobo --drop-scripts --drop-kobo-style` 处理。

**校验**：除常规项外，做**逐文件恒等校验** ——
输出（去方括号）== 源经同样全角→半角转换（去方括号）；启用 Kobo 选项时退化为文本级内容一致性。
未加方括号的 `key1/key2` 标记会报错（源结构损坏的文件降级为提示，无法自动加括号）。



## 多看原生 profile 约定（epub_clean_duokan.py，图片式注释标记变体）

源：多看(duokan) 原生导出的 xhtml（无 calibre 类，靠 `chapter-title*` / `text` 类排版）。

1. **css**：`../Styles/stylesheet.css` + `../Styles/oxenfont.css` → 同目录 `styles.css`
2. **正文**：`<p class="text">` → `<p class="bodytext">`
3. **标题**（按 class **整体下移一级**，整元素匹配、保留 id）：
   `chapter-title2` → `<h3>`、`chapter-title3` → `<h4>`（无 `chapter-title3` 的书不受影响）
4. **其它语义类**（`class_map`）：`leftquote` → `left`、`preface` → `bodytext`、`poems` → `center`
5. **引文/署名**：`<blockquote>` 内的 `<p class="quote">` → `<p class="bodytext">`；
   `<p class="signature">（原载于…）</p>` → `<p class="right">…</p>`，并在其前插入一个
   `<p class="bodytext"><br/></p>` 空行段（其余 `<p class="signature">` 只改 class）
6. **分隔符**：内容为纯符号（`*`、`*　*　*`、`—` 等）的 `<p class="center">` → `<p class="sprt">`（**内容保留**，只归一化类名）
7. **注释标记**（图片式）：
   `<a class="duokan-footnote" href="#a_X_Y" id="c_X_Y"><img alt="注释N" class="duokan-footnote" src="../Images/note.png"/></a>`
   → `<sup><a epub:type="noteref" href="#a_X_Y" id="noteref-N">[N]</a></sup>`
   （源文件常未声明 `xmlns:epub`，脚本会自动补上）
8. **注释列表**：文末
   `<ol class="duokan-footnote-content"><li class="duokan-footnote-item" id="a_X_Y"><p class="footnote-text"><a class="duokan-footnote-link" href="#c_X_Y">注文</a>​​​​​</p></li>…</ol>`
   → `<hr/>` + `<p class="fnote" id="a_X_Y"><a href="#noteref-N">[N]</a> 注文</p>`（每文件从 1 编号、双向回链，去掉零宽空格）
   （注释正文的 p 类在不同书里可能是 `footnote-text` 或 `footnote-bodytext`，脚本两者都认）

以上规则均可在 <dir>/clean_config.json 覆盖（如 heading_map、class_map、separator_classes）。

⚠️ **不要对这类文件做「全局 `text` → `bodytext` 替换」**：它会把 `text-align`、`text/html` 一起改坏
（曾出现封面 `bodytext-align: center`、meta `content="bodytext/html"` 的遗留事故）。只按 class 精确匹配。

## 多看原生·内文/标题 profile 约定（epub_clean_duokan_biaoti.py）

源：多看(duokan) 原生导出的又一种变体，正文/标题用「内文/标题」拼音类名（`neiwen*` / `biaoti*`），
插图带主/副标题，注释同样是图片式标记但列表结构不同（注文直接是 `<p class="footnote-content">`）。
`<html>` 常无 `xml:lang`，也无 `xmlns:epub`；文件扩展名可能是 `partNN.xhtml` / `partNN.html` 混排。

识别特征：

- `<link … href="../styles/fonts.css"/>` + `page_styles.css` + `stylesheet.css`
- 正文 `<p><span class="neiwen">…</span></p>`（变体 `neiwen2` 引文、`neiwen2_1` 引文内诗行、
  `neiwen3` 章前摘要、`neiwen4` 落款、`neiwen5` ◆问句、`neiwen6` h1 内导语）
- 标题 `<h1><span class="biaoti1">第X章<br/><span class="biaoti2">副题</span></span></h1>`、
  `<h2><span class="biaoti3">一</span></h2>`、`<h2><span class="biaoti5">1.1 …</span></h2>`
- 插图 `<div class="duokan-image-single"><img/><p class="duokan-image-maintitle">…</p>
  <p class="duokan-image-subtitle">…</p></div>`（**主标题带 `<a id="imgN" href="partNN.html#imgfN">` 链到插图目录**）
- 注释标记 `<a class="duokan-footnote" href="#foN" id="forefN"><img src="../images/note.png"/></a>`
  （`href`/`id` 是 `#foN`/`forefN`，与上一种多看的 `#a_X_Y`/`c_X_Y` 不同）
- 文末 `<hr class="xian"/>` + `<ol class="duokan-footnote-content"><li class="duokan-footnote-item" id="foN">
  <p class="footnote-content"><a href="#forefN" style="…">[N]</a> 注文</p></li></ol>`
  （注文段类固定 `footnote-content`，`[N]` 源里已带方括号）
- 辅助页：`<h3><span class="list_of_ill">` 插图目录、`<h5><span class="banquan">` 版权页
- `<p class="whitespace">&#160;</p>` 空段

处理顺序（脚本 STEPS，固定不可乱）：css → images → headings → quotes → intro → body → hr → footnotes → ws

1. **css**：`fonts.css` + `page_styles.css` + `stylesheet.css` → 同目录 `styles.css`；
   **若该文件有内联 `<style>`（封面常见），`styles.css` 链接插到内联样式之前**，保证内联覆盖优先级更高
   （否则 `styles.css` 的 `body{text-align:justify}` 会反过来压掉封面的居中）
2. **插图**：`duokan-image-single` → `<div class="chatu">`：`<p class="image"><img src alt/></p>` +
   主标题 `<p class="caption">` + 副标题再一条 `<p class="caption">`（**保留 `<a id="imgN" href="…">` 链接**，img 只留 src/alt）
3. **标题**：`biaoti1`（章号行）+ `biaoti2`（书名行）→
   `<h1><span class="subtitle">章号</span><br/>书名</h1>`（`.subtitle` 是 80% 字号，**包章号、不包书名**）；
   只有 `biaoti1` 的（缘起/尾声/后记/插图目录/DLC 等）→ `<h1>文本</h1>`，不加 subtitle；
   `biaoti1/2/3/5`、`list_of_ill`、`banquan`、`neiwen6` 的 span 一律去掉
   （标签与层级保留：`biaoti3`/`biaoti5` 都仍是 `<h2>`，**不降级**）
4. **引文**：`<p><span class="neiwen2">…</span></p>` → `<blockquote><p class="bodytext">…</p></blockquote>`
   （连续段合并；内层 `neiwen2_1` 先整批去标签，再处理外层，避免非贪婪在内层 `</span>` 处截断；
   **引文内的 `<br/>` 一律拆成独立 `<p class="bodytext">`，blockquote 里不出现 `<br/>`**）
5. **正文**：`neiwen` / `neiwen5` → `<p class="bodytext">`；`neiwen4`（`——落款`）→ `<p class="right">`
6. **章前摘要**：章标题单独成文件时，紧跟 `</h1>` 的那条 `neiwen3` →
   `<blockquote class="intro">` + `<p class="center">…</p>`（脚本按「紧跟在 `</h1>` 之后」精确匹配；
   若不属于该结构的 `neiwen3` 兜底降为 `<p class="bodytext">`）
7. **注释**：先删除重复 id 的空 `<a class="footnote-trigger" …></a>`；标记 →
   `<sup><a epub:type="noteref" href="#foN" id="noteref-K">[N]</a></sup>`；文末 `<ol>` →
   `<hr/>` + `<p class="fnote" id="foN"><a href="#noteref-K">[N]</a> 注文</p>`（每文件从 1 编号、双向回链）。
   脚本先做 hr 步骤，故 **`<ol>` 前原有的 `<hr class="xian"/>` 会被复用**，不会再补一个造成两个 `<hr/>` 相邻
8. **收尾**：`<hr class="xian"/>`（含 `<div>` 包裹）→ `<hr/>`；删除 `<p class="whitespace">&#160;</p>` 空段

⚠️ 同多看上一种：**不要做全局 `text` → `bodytext` 替换**（会改坏 `text-align` 等）。只按 class 精确匹配。

**教训（同类变体留意）**：`biaoti5` 的 class 有时**直接挂在 `<h2>` 标签上**（`<h2 class="biaoti5">1.2 …</h2>`），
而非包在 span 里；标题去 span 规则必须同时处理 `span.biaotiX` 与 `hN.biaotiX` 两种写法。

## InDesign / Adept profile 约定（epub_clean_indesign.py）

源：Adobe InDesign 导出（常见于繁体中文译本），`<body … class="calibre">` + `<div class="calibre1">` 包裹，
标题/段落靠 `f_*` class，脚注是 `<div type="footnote">`，注文/回链的 `<a>` 类为 `_idfootnotelink`
（常带 `pcalibre*` 前缀，脚本用 `[^"]*_idfootnotelink[^"]*` 宽松匹配）；行尾普遍带 `\t` 缩进。

映射（脚本内 CONFIG 可调）：

- `<p class="f_1">` → `<p class="bodytext">`
- `<p class="f_2">`：以 `—` 开头（推荐/署名落款）→ `<p class="right">`，且其后若还有段落则补一个
  `<p class="bodytext"><br/></p>` 空行段；否则（作者名，如 `<h1>導讀 …</h1>` 后的 `黃貞祥`）→ `<p class="author">`
- **章首题词**：连续 `<p class="f_1">` 全为 `<span class="kfont">…</span>`，且**末行以 `—署名` 结尾**
  → `<blockquote class="intro">`：署名行 `class="right"`、其余行 `class="bodytext"`
- **正文引文**（kfont 段，非题词）→ `<blockquote><p class="bodytext">`；
  **若该段之后本文件已无其它 `<p>`（章末作者简介/献词）则不转换**，避免误判
- 正文注释标记 `<span id="footnote-N-backlink"><a class="_idfootnotelink" href="f#footnote-N">N</a></span>`
  → `<sup><span id="footnote-N-backlink"><a href="f#footnote-N">[N]</a></span></sup>`
- 脚注 `<div class="calibre1" type="footnote" id="footnote-N"><p class="f_4"><a …>N</a>　注文</p></div>`
  → `<p class="fnote" id="footnote-N"><a href="f#footnote-N-backlink">[N]</a>　注文</p>`
  （**保留 `id="footnote-N"` 以支持正文跳回；编号沿用原书全局编号，不重排**）
- 插图 `<div class="mg_l_*"> … <img …/> … <p class="f_4">图注</p> </div>` →
  `<div class="chatu"><p class="image"><img src="…" alt=""/></p><p class="caption">图注1<br/>图注2</p></div>`
  （多层 div 用**深度计数**取匹配的 `</div>`；外层同名 `calibre1` 包裹一并替换）
- `<p class="f_1">＊</p>` → `<p class="sprt">＊</p>`
- `<span class="sub">X</span>` → `<sub>X</sub>`（下标；`span.super` 暂不动）
- 残留 `<span class="kfont">` → `<span class="kai">`（styles.css 只定义 `.kai`/`.kaiti`，未定义 `.kfont`）
- `○`(U+25CB) → `〇`(U+3007)（年份/数量里的「零」）
- css 链接 → `styles.css`（删除 `styleNNNN.css` / `stylesheet.css` / `page_styles.css`）
- `tidy`：删空行、去行首缩进

**处理顺序固定不可变**：css → quotes → markers → footnotes → figures → sep → bodytext → sub → author → kai → zerocircle → tidy
（quotes 必须在 markers 之前：注释标记一旦被 `<sup>` 包裹，kfont 题词/引文段就不再匹配；kai 必须在 quotes 之后，否则题词的 kfont 会被改名而漏掉引文规则）。

**保留不动**：`h1.f_`（含内层 `span.bold`）、`f_3` 及非图注的 `f_4`、`hr.horizontalrule`、
`calibre1`/`_idContainer*` 容器与 id、`span.super`/`hfont`/`italic`、`lang` 属性。

**校验**：XML 良构、无残留（`f_1` / `type="footnote"` / `_idfootnotelink` / `mg_l_` / 旧 css）、
id 唯一、内链与跨文件锚点（`f.xhtml#id`）可解析、图片存在、注释标记数 == 尾注数。

**注意**：输出里的 `<img>` 必须自闭合（`<img …/>`）；若写成 `<img …>`（漏 `/`）会让 XHTML 无法解析。


## InDesign→calibre 繁中重注本 profile 约定（epub_clean_indesign_calibre.py）

源：Adobe InDesign 导出后经 calibre 转码的繁体中文译本（**重注释学术书**，如《不正義的地理學》），
`<body id="story-N" class="calibre2">` + `<div class="calibre3">` 包裹，保留 InDesign 的 `_idParaDest-N` 锚点。

映射（脚本内 CONFIG 可调）：

- css → `styles.css`（删 `../stylesheet.css` / `../page_styles.css`）；`<body>` 去 class（保留 id）
- `<h1 id="_idParaDest-N" class="calibre4|h1_">…<span class="small">标签</span>　章名…</h1>` → `<h1 id>`
  （`span.small` 是标签，如「推薦序 / 第一章」；源用 `　` 与标题连在同一行 → **直接去掉标签 span**，
  只有 `h1` 内含 `<br/>` 真正分行时才保留 `<span class="subtitle">`）
- `<h5 class="calibre8">节</h5>` → `<h3>`；`<h6 class="h6_b|h6_s">…</h6>` → `<h4>`；`<h4 class="calibre12">书名</h4>` → `<h4>`
- 正文 `<p class="calibre5|p_|p_1|p_2|p_3|p_b|p_s|calibre11|text_tp">` → `<p class="bodytext">`
- 署名 `<p class="end|end_k">`：**紧跟在 `</h1>` 之后**（章首作者，如推薦序作者名+职务）→ `<p class="author">`
  且**去掉内层 `span`**（`<span class="kai">姓名</span><span class="small1">（职务）</span>` → 纯文本）；
  其余（`——`落款、序末署名）→ `<p class="right">`
- 楷体引文 `<p class="kai_n|kai_nb">`（连续段）→ `<blockquote><p class="bodytext">`；
  **引文（blockquote）内去掉 `span.kai`**（源常按句切成多个 kai span，合并为纯文本）
- 插图 `<div class="container"><div …><img class="fit" src/><p class="caption">…</p></div></div>` →
  `<div class="chatu"><p class="image"><img …/></p><p class="caption">…</p></div>`；**`p.caption` 内也去掉 `span.kai`**（保留 `span.bold`）
- **`<p class="fnote">` 脚注内同样去掉 `span.kai`**（脚注正文不用楷体）
- 生僻字内嵌图 `<img class="pw" src="image/aN.jpg"/>` → 实际字符（CONFIG `rare_img_map`，按书的索引罗马字判定）
- `<div class="box">`（献词）/ `<div class="copyright">` → 解包；`table/tr/td` 去 class 保留
- `span.small1` → `span.small`、`span.bold1` → `span.bold`；`italic`/`kai`/`bold` 保留
- **章内脚注**（`<div class="foot"><hr class="calibre6"/><p class="footnote"><a id="foot-NNN" href="#back-NNN">[N]</a> 注文</p>…</div>`
  + 正文 ref `<a id="back-NNN" href="story-N.xhtml#foot-NNN" class="ref1">N</a>`）
  → 章末 `<hr/>` + `<p class="fnote" id="foot-NNN"><a href="#back-NNN">[i]</a> 注文</p>`，
  **每文件从 1 重排、转小写罗马数字**（文件内注量小，标记很短）、双向回链
- **跨文件引用注**（ref 在正文各章 `<a id="back-aN" href="story-28*.xhtml#foot-aN" class="ref1">N</a>`，
  注在「注釋」章 `<p class="footnote_a|_b|_c"><a id="foot-aN" href="story-*#back-aN" class="calibre7">N</a> 文献…`）
  → `<sup><a epub:type="noteref" href="story-28*.xhtml#foot-c43" id="back-c43">[43]</a></sup>`，注就地转 `<p class="fnote">`，
  **用阿拉伯数字**（`anum()`，取 id 尾数 `43`；每个文件只引用一个系列，故文件内不会重复）
- 空行段 `<p class="calibre5|…">　</p>`（仅全角空格）→ **保留**为 `<p class="bodytext"><br/></p>`
  （源书的空行是排版意图：文末落款与正文间、落款与附注/附筆间、推荐语署名之间等；**不要删**）；
  **连续两个以上的空行段折叠为一个**
- `○`(U+25CB) → `〇`(U+3007)：年份/数量里的「零」，全篇整体替换（本书 299 处）
- **固定版式页**（`<meta name="viewport">` + 内联 SVG，如书名页/插图页）**原样保留**（只去 calibre class）

**处理顺序**：css → body → rare（生僻字）→ figures → footnotes → headings → quotes → paras → table → spans
→ unwrap_extra（box/copyright）→ unwrap（calibre3）→ residual（去残留 calibre class）→ tidy → append（章末尾注）

**注意**：脚注文字必须**保留内部空格**（英文文献脚注需要）——不要用「去所有空白」的 txt()，
用 flat()（折叠空白+去首尾，并剥掉源 calibre class）。**编号方案（两套，形式不同故不撞号）**：
**文件内**注（章末 `<hr/>`+fnote）每文件从 1 重排、转**小写罗马数字**（`[i]`…`[iv]`，量小标记短）；
**跨文件**引用注（链到书末「注釋」章）用**阿拉伯数字**（`[43]`，该系列原序号；每文件只引用一个系列）。
不要用带圈数字（Unicode 只到 ㊿=50，本书 16 个系列有 11 个超过 50）。

## 掌阅 ZHANGYUE profile 约定（epub_clean_zhangyue.py）

源：掌阅（ZHANGYUE）导出的书稿，**已经相当语义化**（正文本就是 `p.bodytext`），脚注经 SigilFootnoteUltimate
插件处理（`noteref_N`/`note_N`）。结构：`Text/*.xhtml` + `Text/styles.css`（规范版）+
`Styles/Style0001.css`（`@font-face` 見容 cs/仿宋 fs）+ `Styles/jianrong.css`（掌阅排版）。

映射（统一到同目录 `styles.css`）：

- css 链 → `styles.css`（删 `../Styles/Style0001.css`、`jianrong.css`）
- `<h1 class="text-title-1-c|text-title-1-r">` → `<h1>`；`<div class="zhangyue-c80">` **解包**（可同名嵌套，深度计数）；
  `<h2 class="text-title-2" … id="sigil_toc_id_N">` → `<h2 id>`；`<h3 class="text-title-3" id="sigil_toc_id_N">` → `<h3 id>`
  ——**属性顺序不定，`id` 必须原样保留**（`toc.ncx` 按 `#sigil_toc_id_N` 跳转）
- 正文 `<p class="bodytext">` 保持；`<span class="fangsong">` → `<span class="kai">`
- `<br/>*` + `<pre><code><b>[注释]</b></code></pre>` → `<hr/>` + `<h2>注释</h2>`；
  `<pre><code>尾注说明：</code></pre>` → `<p class="sprt">`
- 尾注 ref `<sup class=""><a href="#note_N" id="noteref_N">N</a></sup>` →
  `<sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>`；
  注文 `<p class="bodytext"><span class=""><a href="#noteref_N" id="note_N"> N</a></span> 注文</p>` →
  `<p class="fnote" id="foot-K"><a href="#back-K">[K]</a> 注文</p>`（**每文件从 1 重排、阿拉伯**；本书全部为文件内尾注，无跨文件）
- 图 `<div class="zhangyue-c">` → `<div class="chatu">`：`<img class="zhangyue-img">` → `<p class="image"><img …/></p>`；
  `p.bodytext-no`（图题）与 `p.img-note`（图注）→ `<p class="caption">`（**保留原序**，有的图题在图上方）；块内 `<hr/>` 删除
- `p.bodytext-no`（图块外）→ `p.bodytext-noindent`
- 内联 style：`text-align:right` → `class="right"`、`center` → `center`，其余丢弃（含 h2 的悬挂缩进、cover 的居中 div）
- **`<html>` 补 `xmlns:epub`**（源未声明；用了 `epub:type` 就必须补，否则 XML 不合法）；封面 SVG 原样保留

**处理顺序**：css → spans → noteheads → footnotes → ns → figures → headings → unwrap → styles → tidy

**校验**：XML 良构；无残留（`text-title-*`/`zhangyue-*`/`fangsong`/`img-note`/内联 style/`noteref_`/`note_`/`<pre>`/`[注释]`）；
id 唯一；**源 id 一个都不能丢**（process 比对源与成果的 id 集合）；ref ↔ fnote 双向配对；`styles.css` 已链。

**注意**：`content.opf` 的 manifest 需把 `Styles/Style0001.css`、`Styles/jianrong.css` 两项换成
`<item id="styles.css" href="Text/styles.css" media-type="text/css"/>`，否则阅读器不加载样式（本书已同步改好）。

## Kindle-cn（亚马逊中国）profile 约定（epub_clean_kindle_cn.py）

源：亚马逊中国（Kindle）导出后经 calibre 转码，`zh-CN`，`<body class="calibre">` + `kindle-cn-*` 混用；
css 链 `../stylesheet.css` + `../page_styles1.css`；同目录另有规范版 `styles.css`。
常见「书籍分享公众号」污染：`<div class="chatu_img"><img src="../gaiword.png"></div>` + 若干 `p.calibre8` 求书段，
**可能整篇位于 `</body>` 之后**（非法 HTML），也有整文件只有广告的 `_split_000` 残片。

映射（统一到同目录 `styles.css`）：

- css 链 → `styles.css`；`<body>` 去 class；`<html>` 补 `xmlns:epub`
- **广告**：`div.chatu_img` 及其后连续的 `p.calibre8` 求书段、`gaiword` 引用，整块删除；空 `<div class="calibre4|empty">` 删除；
  `</body>` 之后的残留一并清掉（整篇只有广告的文件会变成空 body，需在打包时删除）
- 标题去 class：`h1.kindle-cn-heading|kindle-cn-toc-title` → `h1`（保留 `id="calibre_pb_0"`）；
  `h2.kindle-cn-heading2|calibre7` → `h2`，**把 h2 内嵌空锚 `<a id="secNNN" class="calibre6"></a>` 的 id 提到 `<h2 id="secNNN">`**
  （`toc.ncx` 与书内目录都按 `#secNNN` 跳转）；`h3.kindle-cn-heading3` → `h3`；`h4.kindle-cn-heading1` → `h4`
- 目录页 `div.kindle-cn-toc-level` → `div.toc1`；`toc-level1` → `div.toc2`（styles.css 已定义）；`a.calibre3` → `<a>`
- 正文 `p.calibre1|kindle-cn-para-2em-indent` → `bodytext`；`kindle-cn-para-no-indent(1)` → `bodytext-noindent`；
  `p.kindle-cn-kai` → `bodytext` 内包 `span.kai`；`p.kindle-cn-signature(1)` → `p.right`
- 诗句（连续 `p.kindle-cn-poem-left`）→ `<blockquote class="poem">` + 各段 `<p class="bodytext">`（段末多余 `<br/>` 去掉）
- 尾注：ref `<a id="chN-back" href="file#chN"><sup class="calibre5">[N]</sup></a>` →
  `<sup><a epub:type="noteref" href="#foot-N" id="back-N">[N]</a></sup>`；
  注文 `<p class="fnote"><a id="chN" href="file#chN-back">[N]</a> 注文</p>` →
  `<p class="fnote" id="foot-N"><a href="#back-N">[N]</a> 注文</p>`；
  **编号沿用原书（本就是每文件 1..M 顺序）**；`href` 指别的文件时保留文件部分（跨文件注，如 `_split_000`↔`_split_001` 共享编号）
  尾注前 `div.empty` + 20 个 U+2014 的段 → `<hr/>`（故 **footnotes 步骤必须在 ads 之前**，否则 `div.empty` 被先删）
- 图片页 `div.kindle-cn-bodycontent-div-alone` → `<div class="chatu"><p class="image"><img …/></p></div>`
- 行内图 `<img class="kindle-cn-inline-character|kindle-cn-inline-image">` → `<img src alt/>`（**保留**）；
  若目录下存在 `rare_map.json`（`{"Image00003.jpg": "𠀀", …}`）则按表替换为实际字符并计数
- `span.kindle-cn-bold` → `<b>`；`br.calibre4` → `<br/>`；`span.calibre8` 去 class（保留 `lang`）
- `href` 里 `textNNNNN.html` → `textNNNNN.xhtml`；**文件 `.html` → `.xhtml`**（打包时同步 `content.opf`/`toc.ncx` 的 href/src）

**处理顺序**：css → toc → headings → footnotes → poem → paras → figures → inline_imgs → misc → ads → body → ns → tidy

**校验**：XML 良构；无残留（`calibre`/`kindle-cn`/`chatu_img`/`empty`/`gaiword`/`.html` 链接/`chN` id/内联 style）；
id 唯一；**源 id 一个不丢**（TOC 锚点 `secNNN`、`calibre_pb_0` 等，比对源与成果）；ref↔注 配对（跨文件与源书悬空注只提示不判错）。

**注意**：`text00014_split_000/_001` 是被拆成两半的同一章（ref 在 _000、310 条注在 _001），编号跨文件共享，
不要当广告残片删；只有**整篇只剩空 body** 的 `_split_000` 才是广告残片。

**生僻字图人工确认工作流**（本书即用此法，140 处一次替换完）：

1. 把行内图拼成若干张带编号的对照表（PIL，每张 5×5、放大到 240px）**自查字形**；
2. 逐张记录「图 → 拟定字 + 把握度（确定/较可信/存疑/未知）+ 上下文线索」；
3. 生成一个**交互式确认页**（`rare_review.html`，一行一张图：图 ｜ 判定+线索+上下文 ｜ 勾选「确认」/ 输入框填正确字，
   顶部有进度、全选、**导出结果**按钮把 JSON 复制到剪贴板）；
4. 用浏览器面板打开（本地 `python -m http.server` 提供 http 地址，file:// 不被接受）；
5. 收回确认结果 → 写成 `<dir>/rare_map.json`（键是 **img 的 src 全名**如 `Image00003.jpg`）→ 重跑 profile 即替换并计数。

**注意**：`content.opf` 的 manifest 需把旧 css 项换成 `OEBPS/styles.css`；`.html→.xhtml` 与删除广告残片后要同步 opf/ncx
（ncx 里 `.html#锚点` 也要改，别只改 `.html"` 结尾的）；文本完整性核对时要把 `rare_map` 的值从两侧剔除（属预期新增）。

**删广告残片时别顺手删目录条目**：源 ncx/opf 里常有指向广告残片的条目（本书「序言」「绪论」两条 navPoint 都指向
被删的 `text00004_split_000`，而真正的内容在同名 `_split_001`／下一文件）。**先看 navLabel 是不是真实内容**：
是则把 src **改指**真实文件（本书：序言→`text00004_split_001.xhtml`、绪论→`text00005.xhtml`），删完记得重排
`playOrder`、并把 `guide` 里的 `type="text"`(Start) 一并改指。判据：源 ncx 的形状不一定可信（「绪论」那条本来就指错）。

## InDesign EPUB3 新版 profile 约定（epub_clean_indesign_epub3.py）

源：Adobe InDesign 的 **EPUB3 导出**（一般由 `ebookredo` 之类工具过手），zh-TW/zh-CN 皆见。
与老式 InDesign（`f_1`/`_idfootnotelink`/`<div type="footnote">`）不同：正文/标题/行内全都靠
`ff_serif`/`ff_sans`/`ff_cursive` × `fz_*`（字号）× `ti_*`/`ta_*`（缩进/对齐）× `fw_900`/`fs_italic` 这类**组合类**；
脚注用 EPUB3 语义（`role="doc-noteref"`、`epub:type="endnotes"`）。
`<body id="…">` + 一层**无 class 的 `<div>`** 包裹；css 链 `css/YYYY.N.h.css`；同目录通常另有规范版 `styles.css`。
常见「一页一文件」（`BK7026X-1..NNN.xhtml`），文本完整、不跨文件截断，但阅读体验差 → **先按 h1 合并成章**再清洗。

映射（统一到同目录 `styles.css`）：

- css 链 → `styles.css`；`<body>` 去 class（保留 id）；**无 class 的 `<div>` 深度计数解包**（带 class 的不动）
- `<title>` 改成该文件第一个 `h1` 的文字（源里常被自动填成正文首句）
- `h1.ff_serif.fz_1-9em…` → `<h1>`（保留 `id="_idParaDest-N"`，`toc.xhtml`/`toc.ncx` 按它跳转）；
  **h1 内的 span**：**只有「分行」才用 `<span class="subtitle">`**——即该 span 后紧跟 `<br/>`（如 `<span>導讀</span>　<br/>書名…`），
  或以 `──`/`——` 开头的副题；其余（如 `<h1><span>前言</span></h1>`、`<span>I　出入愛戀</span>`）**一律拆掉**，`<br/>` 保留
- 正文 `p.ff_serif.fz_1-0em.ti_2em`（及 `mg-str_2-0em`）→ `p.bodytext`；`.ta_left` → `p.bodytext-noindent`；`.ta_right` → `p.right`
- 楷体引文（连续 `p.ff_cursive.fz_1-0em.mg-str_2-0em`）→ `<blockquote>` + 各段 `p.bodytext`；
  **整段 `<b>` 包着的引文段 + 紧随其后的 `p.right` 以 `──`/`——` 开头（落款）→ `<blockquote class="intro">`**（落款留在 blockquote 外；
  已在 blockquote 内的不再套，避免误伤手工结构）
- `p.ff_serif.fz_1-6em.ta_left`（如「參考書目」）→ `<h3>`；`p.ff_sans.fz_1-0em.ta_center` → `<p class="sprt">`
- 行内：`span.ff_serif|ff_sans.fw_900` → `<b>`；`span.ff_cursive.fs_italic` → `<i>`（+fw_900 则 `<b><i>`）；`span.ff_cursive` → `<span class="kai">`；
  其余 span 去 class（**兜底不要把 `kai`/`italic`/`bold`/`small`/`subtitle` 也剥掉**）
- 脚注：ref `<span class="ff_sans fz_0-6em va_super"><span><a id="footnote-NNN-backlink" class="_idFootnoteLink" role="doc-noteref" epub:type="noteref" href="FILE#footnote-NNN">NN</a></span></span>`
  → `<sup><a epub:type="noteref" href="#foot-K" id="back-K">[K]</a></sup>`；
  注文 `<section class="_idFootnotes">…<li id="footnote-NNN" class="_idFootnote"><p><a class="_idFootnoteAnchor" …>NN</a>：注文</p></li>…`
  → **收掉所有 `<hr class="HorizontalRule-1">` 与 section/ol 壳，末尾只留一个 `<hr/>` + 一串
  `<p class="fnote" id="foot-K"><a href="#back-K">[K]</a> 注文</p>`**（**去掉注文外层的 `<p>`**，否则 XML 断裂；`：` 分隔符去掉）；
  **每文件（= 合并后每章）从 1 重排**
- 图 `<div class="mg-str_10pr mg-end_10pr" id="_idContainer*">` → `<div class="chatu"><p class="image"><img …/></p></div>`
- 引文框 `<div class="bd-w_1px … box" id="_idContainer*">` → **`<blockquote class="intro">`**（含配对的 `</div>`→`</blockquote>`，深度计数；
  里面通常是整段引文，故用 `intro` 而非保留 `<div class="box">`）
- 空行段 `<p class="…">　</p>` → `<p class="bodytext"><br/></p>`（连续折为一个）；
  **blockquote 前后紧邻的空行段删掉**（blockquote 自带间距，源里常在引文前后各留一个空行）
- 未在映射里的 `p.ff_*` 兜底为 `bodytext` 并计数（process 日志会列出，便于补规则）
- 尾注 append 时若末尾**已是** `<hr/>` 则不再补一根（避免双 hr）

**处理顺序**：css → title → headings → footnotes → quotes → paras → spans → intro → figures → box → spacers → unwrap → body → tidy → append

**校验**：XML 良构；无残留（`ff_*`/`fz_*`/`ti_*`/`ta_*`/`_idFootnote*`/`HorizontalRule`/`footnote-NNN` id/旧 css）；
id 唯一；**源 id 不丢**（`_idContainer*` 随解包消失可除外）；ref↔注 配对；`styles.css` 已链。

**合并章节**：见「Kindle-cn」一节同样的做法——按 `h1` 分组，把每文件的正文拼接、**各文件的 `<hr/>`+尾注 section 统一收到章末**，
删掉其余文件，再同步 `content.opf`（删 manifest item + spine itemref）与确认 `toc.xhtml`/`toc.ncx` 只引用保留文件（本书正好只引用 7 章，无需改）。

## 人民邮电 / 得到（`p.content` 系）profile 约定（epub_clean_ptpress.py）

源：人民邮电出版社授权「得到」电子版（`xml:lang="zh-hans"`），`../Styles/stylesheets.css`；
标题/段落靠 `firstTitle` / `content*` class，注释是 `super`+`annot` 锚点。

映射（脚本内 CONFIG 可调）：

- `<p class="content">` → `<p class="bodytext">`
- `<p class="content_100|101|102">`（术语/小结、必读书目、原理名）→ `<h3>`
- `<p class="content_103|107">`（译者署名/日期、`——` 题词落款）→ `<p class="right">`
- `<p class="content_105">`（引文/原理陈述）→ `<blockquote><p class="bodytext">`，连续段合并；
  **「小结」段（`>小结<` 之后）内的 content_105 不包 blockquote**，直接 `<p class="bodytext">`（`step_summary` 兼容拆掉旧输出里的）；
  **章末最后一条 content_105**（其后不再有正文段落）同样不包 blockquote → `<p class="bodytext">`
- 引文 blockquote **后紧跟的** `——落款`(content_107) → 并入该 blockquote，并把 blockquote 标成 `class="intro"`
  （`step_intro_sig`；对已生成的旧输出同样生效）
- `<p class="content_108">`（括注）→ `<p class="center">`；
  **紧跟在 `</h1>` 后的一条** → 并入 h1 作第二段副标题 `<br/><span class="subtitle">…</span>`（`step_h1`）
- `<p class="content_110">`（索引条目）→ `<p class="bodytext-noindent">`
- `div.pic`（img + `imgtitle`/`imgtitle1`/`imgdescript` 图注）→ `<div class="chatu">…<p class="caption">`
  （图注可多行 `<br/>` 合并；**图注也可能排在 img 之前**，须整块提取而非顺序匹配）
- `<span class="kt_104|kt_106">` → `<span class="kai">`（楷体强调）
- `<h1 class="firstTitle" id="sigil_toc_id_N">` → 去 class、保留 id；`<span class="xiao">第X章</span>` → `<span class="subtitle">`
- `<span class="super">`（剩余、数学上标）→ `<sup>`
- 注释：`<span class="super" id="refN"><a href="#annotN">[K]</a></span>`
  → `<sup><a epub:type="noteref" href="#annotN" id="refN">[K]</a></sup>`；
  文末 `<p class="noindent" id="annotN"><a href="#refN">[K].</a>注文</p>`
  → `<p class="fnote" id="annotN"><a href="#refN">[K]</a> 注文</p>`（保留 `<hr/>`）
- css → `styles.css`（删除 `stylesheets.css` 与内联 `<style>`）

**处理顺序固定不可变**：css → footnotes → figures → quotes → summary → headings → right → intro_sig → center → noindent → bodytext → kai → h1 → super → tidy
（footnotes 必须先于 super：注释标记 `super#refN` 先被消费，剩下的 `super` 才是数学上标；
quotes/summary 先于 headings；intro_sig 须在 right 之后，才能把落款并入 blockquote）。

**保留不动**：`p.banquan2` / `p.yingwen2`（版权页）、`span.bold`/`italic`、`cover.xhtml` 的 SVG、`lang` 属性。

**校验**：XML 良构、无残留（`content*` / `pic` / `imgtitle*` / `kt_104/106` / `super` / 内联 style / 旧 css）、
id 唯一、`ref↔annot` 锚点可解析、图片存在、注释标记数 == 尾注数。



## bookcrafter 生成版 profile 约定（epub_clean_bookcrafter.py）

源：由「bookcrafter」类工具生成的 EPUB（磨铁 / Z-Library 分发版常见），结构极简、无任何语义类：
一文件一章，正文全是 `p.bookcrafter-body-paragraph`，没有 span / img / br / blockquote。

识别特征：

- `<html … xml:lang="zh-CN" lang="zh-CN">`（无 `xmlns:epub`）
- `<link rel="stylesheet" type="text/css" href="../Styles/style.css"/>` + 内联
  `<style>body p.bookcrafter-body-paragraph { text-indent: 2.00em !important; duokan-text-indent: … }</style>`
- `<h1 style="font-size: 1.45em; text-align: center; font-weight: bold; …">标题</h1>`（样式全是内联）
- 正文 `<p class="bookcrafter-body-paragraph">…</p>`
- **脚注为纯文本编号，没有任何链接/锚点/id**：
  正文引用 `…“团块世代”  (1)  ，两人…`；
  章末尾注 `<p class="bookcrafter-body-paragraph">(1) 　注文</p>`（连续成块、编号 1..N、与 TOC 无关）
- 目录页 `body-toc.xhtml`：`<div class="toc-list"><p><a href="chapterNNN.xhtml">标题</a></p>…</div>`

处理（脚本 STEPS，顺序不可乱）：css → headings → footnotes → toc → body → tidy

1. **css**：删 `../Styles/style.css` 链接与**全部内联 `<style>`**，加同目录 `styles.css`
2. **标题**：`<h1 style="…">` → `<h1>`（去内联样式）；
   **占位标题归一**：`正文 28` / `正文28` → `28`，同步改 `<title>` 与目录项
   （规则见 `CONFIG["placeholder_title_re"]`，换书占位式样不同就改这里；
   `序幕` / `尾声` / `版权信息` 等非占位标题原样保留）
3. **脚注**：从文末**倒序**收集「整段以 `(N)` 开头」的连续段落（须为 1..N 连续，否则报错）；先删这些段，
   再把正文 `(N)` → `<sup><a epub:type="noteref" href="#footnote-N" id="noteref-N">[N]</a></sup>`，
   最后在 `</body>` 前插 `<hr/>` + `<p class="fnote" id="footnote-N"><a href="#noteref-N">[N]</a> 注文</p>`。
   源文件缺 `xmlns:epub` 时脚本自动补到 `<html>` 上
4. **目录页**：解包 `div.toc-list`，`<p><a …>` → `<p class="toc1"><a …>`（`styles.css` 已有 `.toc1` 与 `a{text-decoration:none}`）
5. **正文**：`class="bookcrafter-body-paragraph"` → `class="bodytext"`
6. **收尾**：压缩 head/body 空行、去行首缩进

**孤儿注**：本书 `正文5/正文20/正文21/正文27` 各有 1–2 条尾注在正文里**没有对应引用**（源书如此）。
脚本仍保留为尾注，但**不加回链**（输出 `<p class="fnote" id="footnote-N">[N] 注文</p>`），
编号沿用源书数字，不做压缩——否则正文里的 `[3]` 会与尾注编号错位。`process` 报告里的「孤儿注」列即此数。

⚠ 源书 h1 是「正文1 / 正文 2 / …」这类**占位标题**（生成工具留下）：脚本按
`CONFIG["placeholder_title_re"]`（默认 `^正文[ \t]*(\d+)$`）把整条标题归一为纯数字 `N`，
h1、`<title>`、目录项三处同步；非占位标题（序幕/尾声/版权信息/目录）不动。

**校验**：XML 良构、无残留（`bookcrafter` / 内联 style / `<style>` / 旧 css / `toc-list` / `div` / `(N)`）、
`styles.css` 链接存在、id 唯一、`href="#…"` 均可解析、noteref 均有对应 fnote。

## 文景 / 上海人民 profile 约定（epub_clean_bodycontent.py，跨文件注）

源：《北欧神话》一类上海人民出版社·世纪文景版。语义标签已就位，只挂 `bodyContent-*` 系 class；
锚点 id 以 `isbn…` / `pos…` / `pre…` 开头。

识别特征：

- `<html … xml:lang="zh-cn">`、`../Styles/stylesheet.css` + `stylesheet-1.css`
- 标题：`h1.chaptertitle-c`（章）/ `parttitle-c`（部）/ `prefacetitle-c`（序、目录）/ `backtitle-c(-2)`（附录、译名表）；
  `h3.txtheading-1-c`（节）/ `h4.txtheading-2-c`（小节）——**源书就是 h1→h3→h4、跳过 h2**
- 正文 `p.bodyContent-1`（变体 `-top` / `-top-2` / `-1-c`）、`p.noindent-copyContent-1(-top/-topbot)`（版权页）、
  `p.hang-bodyContent-1`（译名对照表，一行一条）
- 楷体引文 `p.bodyContent-2-kaiti` / `-kaiti-top-4` / `-kaiti-top`
- **跨文件脚注**（锚点成对，编号按章连续、不按文件重排）：
  正文 `<a href="part0023.xhtml#jz_1_319" id="jzyy_1_319"><sup>(11)</sup></a>`
  注文 `<p class="fnContent-1"><a href="part0018.xhtml#jzyy_1_234" id="jz_1_234">(1)</a> 注文</p>`
  注文常集中在少数「注释文件」（如 part0023 / part0027）里，与正文同文件；每处注文前源已带 `<hr/>`
- 图 `div.chatu_img` / `chatu_img-l-9` / `title_img` > `img.pic-img*`
- 目录 `p.contents-1|2|3`（三级）
- 零星 `span.songti`（宋体标点）、`span.space`

处理（脚本 STEPS）：css → figures → footnotes → quotes → headings → toc → body → spans → imgs → tidy

1. **css**：`stylesheet.css` / `stylesheet-1.css` → 同目录 `styles.css`
2. **图**：`chatu_img / chatu_img-l-9 / title_img` → `<div class="chatu"><p class="image"><img src alt/></p></div>`
3. **脚注**：ref → `<sup><a epub:type="noteref" href="[file]#jz_X" id="jzyy_X">[N]</a></sup>`；
   注文 → `<p class="fnote" id="jz_X"><a href="[file]#jzyy_X">[N]</a> 注文</p>`。
   **保留源编号与跨文件 href**（注释文件与正文分离，重排会打断跨文件链）；源有的 `<hr/>` 保留
4. **引文**：`bodyContent-2-kaiti*` 连续段 → 一个 `<blockquote>`，块内每段 `<p class="bodytext">`
5. **标题**：只去 class，**保留 h1/h3/h4 原层级**（用户口径：不补齐 h2）与 id
6. **目录**：`contents-1` → `p.toc1`、`contents-2` → `p.toc2`、`contents-3` **删除**（用户口径：只留前两级）
7. **正文**：`bodyContent-*` / `noindent-copyContent-*` / `hang-bodyContent-*` → `<p class="bodytext">`
8. **span**：`span.songti` / `span.space` 去标签（宋体为默认）；`img` 只留 src/alt
9. **收尾**：压缩 body 空行

**校验**：XML 良构、无残留源 class / 内联 style / 旧 css、id 唯一、文件内 `#锚点` 可解析，
外加**目录级跨文件校验**（每个 `file#anchor` 必须有对应实体 id，`noteref` 总数 == `fnote` 总数）。

## 八旗文化 profile 约定（epub_clean_baqi.py，繁中 InDesign 导出）

源：八旗文化（台湾）繁体中文书，InDesign 导出、类名极简；正文 `<p>` 甚至连 class 都没有。

识别特征：

- `<html … xmlns:epub="…">`（无 lang）、`../Styles/Style.css`（版權頁另有 `Copyright.css`）
- 标题（`title` 属性重复全文；章号/副题是 `display:block` 的 span）：
  `<h1 title="第一章 機械人與女巫──塔羅斯與美蒂亞"><span class="num">第一章</span>機械人與女巫<span class="num2">──塔羅斯與美蒂亞</span></h1>`
  `<h2 title="推薦序：…"><span class="num">推薦序</span>希臘神話的科技工藝想像</h2>`、`<h3 class="h3 sigil_not_in_toc">節</h3>`
- 正文 `<p>`（**无 class**）；`<p class="author">`；`<p class="noindent"><span class="kai">題詞</span></p>`
- 引文 `<p class="kai">` / 整块 `<div class="kai"><p>…</p></div>`（楷体、藍色）
- 分隔 `<p class="sec">* * *</p>`
- 图 `<div class="pic|pic-c"><img/><span class="caption">图说</span></div>`（caption 是 span 不是 p）
- 脚注（章末 `<ol>`，源 CSS 带 border-top）：
  正文 `<a class="footnote" href="#fnX-1" id="fX-1">[1]</a>`
  章末 `<ol class="footnote"><li id="fnX-1">注文<a href="#fX-1"><img class="pw" alt="back" src="../Images/back.png"/></a></li>…</ol>`
  ⚠ `img.pw` 只是**回链箭头**（`alt="back"`，1em 宽），不是生僻字图
- 其它：`<p class="ref">`（參考書目，悬挂缩进）、`<p class="title">`+`<p class="item">`（名詞釋義）、
  `<div class="boxend">`（灰底专栏）、`<div class="main">`+`<span class="book-title-main/original">`（版權頁）、
  `<html class="vrtl">`（版權頁直排）、`<p><br/></p>` 空段、`<a id="section_N">`/`<a id="_idTextAnchorNNN">` 空锚点

处理（脚本 STEPS）：css → figures → footnotes → quotes → headings → misc → unwrap → body → tidy

1. **css**：`Style.css` / `Copyright.css` → 同目录 `styles.css`
2. **图**：`div.pic`/`pic-c` → `<div class="chatu"><p class="image"><img src alt/></p><p class="caption">…</p></div>`
3. **脚注**：ref → `<sup><a epub:type="noteref" href="#fnX-N" id="fX-N">[N]</a></sup>`；
   `<ol class="footnote">` → `<hr/>` + `<p class="fnote" id="fnX-N"><a href="#fX-N">[N]</a> 注文</p>`
   （丢弃 `<img class="pw">` 回链箭头；编号取 id 尾数，每章 1..N）
4. **引文**：`div.kai` 整块 → `<blockquote>`（块前无正文段时加 `class="intro"`，如謝詞题词）；
   `p.kai` → `<blockquote>` + `<p class="bodytext">`；`span.kai`（行内楷体）**保留**
5. **标题**：`span.num` → `<span class="subtitle">…</span><br/>`；`span.num2` → `<br/><span class="subtitle">…</span>`；
   `h3` 只保留 `sigil_not_in_toc` 标记（去掉多余的 `h3` 类）；`title` 属性保留
6. **杂项**：`p.sec` → `p.sprt`；`p.ref`/`p.item`/`p.title`/`p.noindent` → `p.bodytext-noindent`；
   `<html class="vrtl">` 去 class；`p.author`、`p.center` 保留
7. **解包**：`div.boxend`、`div.main`、`span.book-title-*`
8. **正文**：`<p>`（无 class）→ `<p class="bodytext">`
9. **收尾**：删 `<p><br/></p>` 空段、压缩 body 空行

**校验**：XML 良构、无残留源 class / 图 div / 注列表 / `pw` 箭头 / 旧 css、id 唯一、
`#锚点` 可解析、noteref 数 == fnote 数。

⚠ `<span class="kai">` 是合法的行内楷体（styles.css 已定义），残留检查只针对 `<p class="kai">`。

## 人工精修清单（用户手动改过的口径，脚本不自动做）

出版书清洗完，用户会再手工过一遍。以下是已确认的偏好，遇到同类内容照做：

- **居中的题记 / 献词 / 标语** → `<p class="center">`（不是 bodytext）
- **「本书获誉 / 赞誉」页**：每条书评＝`<p class="bodytext">书评</p>` + `<p class="right">——某某，某书作者</p>`，**条与条之间插一行空段 `<p class="bodytext"><br/></p>`**（最后一条后面不插）
- **推荐序 / 序跋的署名行**（「某某（职称）、某某（职称）」或单独姓名＋身份，紧跟标题/正文之后）→
  `<p class="author">`（居中楷体、下边距 1.4em）；**不要用 `p.center`**（center 只给出题记、标语这类整句）
- **信件称呼行**（如「我亲爱的庞德先生：」）→ `<p class="left">`
- **作者简介的「人名 + 外文名」两行** → 合并成
  `<h3>人名<br/><span class="subtitle">外文名（生卒年）</span></h3>`
- **引文性内容整体包 `<blockquote>`**：报纸标题+报道正文、邀请函、手稿片段、信件等；
  引文里的标题/落款行用 `<p class="center">`（可含 `<b>`）
- **正文里引用的古籍/文献原文** → `<blockquote><p class="bodytext">原文</p></blockquote>`：
  不加 class（**不用 `intro`**）、**不用 `span.kai`**、块内不出现 `<br/>`（多行原文每行一个 `p.bodytext`）
- **章首「内容概述」（小节标题 + 一句话提要的列表）** → 整块包 `<blockquote class="intro">`：
  每条的标题写成 `<p class="center"><b>一 平民家世</b></p>`，提要正文紧跟 `<p class="bodytext">…</p>`；
  块内**不再用 `<h3>`**（真正的节标题在正文里另有 `<h2>`）
- **插图一律不得用 `<table>` 包裹**：双图并排也做成一个 `<div class="chatu">` 里两条 `<p class="image">`；
  纯数据表（年表、月表等）保留 `<table>`
- **章首/篇末题词（带落款）** →
  `<blockquote class="intro"><p class="bodytext">题词</p><p class="right">——落款</p></blockquote>`
- **「原文 + 今译」对照的列传体**：原文 `<p class="bodytext">…</p>`（不加楷体）；
  今译 `<p class="bodytext"><span class="kai">…</span></p>`（楷体）；每对之间插 `<p class="bodytext"><br/></p>` 空行段
- **年表 / 大事记**：年与条目行用加粗独立段 `<p class="bodytext"><b>秦昭王元年</b></p>`
  （表内一人称年表可写成 `<p class="bodytext"><b>秦王政九年</b>&#160;&#160;34岁，…</p>`），
  条目正文用 `p.bodytext`，每组之间插 `<p class="bodytext"><br/></p>`；**不要做成 `h3/h4`，也不要 `bodytext-noindent`**
- **成对交替的对照内容（如「朝代」「皇帝」两段一组）** → 左右两列表格：表头取两段各自的小标题（`<tr><th>朝代</th><th>皇帝</th></tr>`），每对一行
  `<tr><td><b>秦朝</b><br/>（西元前二二一—二〇六年）</td><td>秦始皇（西元前二二一—二一〇年）</td></tr>`；段落开头重复的小标题（如每段的 `<b>皇帝</b><br/>`）删掉，段间空行段一并删除
- **参考文献条目**同样用 `<p class="bodytext">`（不另设悬挂缩进类）
- **节标题「一、xxx」**：编号与标题合成一行 `<h2>一、吕不韦真的是秦始皇父亲吗？</h2>`；
  只有**真正的副题**（与标题内容重复/补充说明的两行结构）才用 `<span class="subtitle">`
- **图注** `<p class="caption">` 只用纯文本，不加 `<b>`/`<i>`
- 源码里无 class 的 `<p>书分享V：XXXX</p>` 这类**盗版水印段**整段删除（去掉后不必再校验）
- **逐字拆开的拉丁词**（源码里被拆成 `i P a d`、`V-2 火箭`）要合成 `iPad`、`V-2火箭`
  —— 这类是内容本身的错排，脚本不猜，人工改
- 段落在源码里被 `</p>\t<p>` 挤在一行的，拆成一行一段（脚本已自动做）

## Kindle→calibre 第二套类号 profile 约定（epub_clean_kindle_calibre2.py）

与 profile Q 同源（AZW3 经 calibre 转码），但类号分配不同，**标题被 calibre 转成了 blockquote**：

- 章：`<blockquote id="fileposNNN" class="calibre_13"><span class="calibre2"><span class="bold">
  <span class="calibre_14">第一章</span></span></span></blockquote>` +
  `<blockquote class="calibre_15"><span class="calibre7"><span class="bold">章名</span></span></blockquote>`
  → `<h1 id="fileposNNN"><span class="subtitle">第一章</span><br/>章名</h1>`；
  单条（導論/結語/參考書目/誌謝）→ `<h1>标题</h1>`；`id` 必须留在 h1 上（ncx / 书内目录按它跳转）。
- 节：`<p id="fileposNNN" class="calibre_4">…<span class="bold">节名</span>…</p>` → `<h2 id="fileposNNN">节名</h2>`；
  文件中第一个 `p.calibre_4` 且前面没有章标题时（推荐序 / 导论）作 `<h1>`。`p.calibre_28` 也是二级标题（参考文献小节）。
- 正文 `p.calibre_7/_8/_16/_20/_26/_30` → `p.bodytext`；推荐序/序跋署名 `p.calibre_6` → `p.author`（居中楷体，不用 `p.center`）；
  `p.calibre_23`、`p.calibre_31` 的空段直接丢。
- 图：单独一行的 `<p class="calibre_">|calibre_NN` 里放 `<img>`，紧跟 `<blockquote class="calibre_18">图注</blockquote>`
  → `<div class="chatu"><p class="image"><img/></p><p class="caption">…</p></div>`（图注也可能是 `p.calibre_23`）。
- 尾注：`<ol class="calibre_11"><li value="N" id="fileposNNN" class="calibre_12">注文
  <a href="#fileposNNN"><span class="calibre6">↺</span></a></li>…</ol>`（回链符号是 **U+21BA**，不是 U+21A9）
  → 注文抽到章末 `<hr/>` + `<p class="fnote" id="foot-K"><a href="#noteref-K">[K]</a> …</p>`，
  每文件 1..K 重编号；正文 `<sup class="calibre3"><small id="fileposNNN"><a href="#fileposNNN">
  <span…>[N  ]</span></a></small></sup>` → `<sup><a epub:type="noteref" href="#foot-K" id="noteref-K">[K]</a></sup>`
  （按注文 id 对应，编号里的空格去掉）。
- `ol.calibre_11` 里若是 `li.calibre_25`，是**有序引文清单**（如白皮书四點）→ 保留 `<ol><li>`，编号即内容，不能改成段落。
- 参考文献：`p.calibre_28`/`p.calibre_4` 是小节 → h2；`ul.calibre_29 > li.calibre_25` 是条目 → 逐条 `p.bodytext`
  （`ul` 没有编号，改段落不丢内容）。
- 书内目录页：`p.calibre_31`「Table of Contents」→ `<h1>目次</h1>`，`ol.calibre_33>li.calibre_34` → `p.toc1`，
  内层 `ol.calibre_35>li.calibre_34` → `p.toc2`，`<a href="…">` 原样保留。
- 封面 `titlepage.xhtml`（内含 `<style>@page` + 只放封面 SVG）→ `<body class="cover">` + `<img src="images/calibre_cover.jpg"/>`。
- 清理：`<a></a>`（calibre 空锚，几千个）、`div.calibre_10|24|32`（空壳）、`div.mbp_pagebreak`、
  `span.calibre*` 去壳、`span.bold`→`<b>`、`span.italic`→`<i>`、`br class="calibreN"`→`<br/>`。
- 文件名 `.html` → `.xhtml`（同步 opf / ncx / 目录页链接）；`stylesheet.css`+`page_styles.css` → 单一 `styles.css`。
- 若开头有一页与封面**字节相同**的重复图页（如 `index_split_000`，图片同一文件），按用户口径删掉该页与那张图，
  同时从 opf/spine 摘除。

**校验**：XML 良构、无 `class="calibre*"` 残留、无空锚、noteref 数 == fnote 数且回链一致、chatu 必有图、
class 全在白名单、逐文件文本与源相同（`sup`/`[N]`/`↺` 不计入比对，目录页把 `Table of Contents` 与 `目次` 互抵）。

## 旧成果收尾 profile 约定（epub_clean_legacy.py）

源：**本 skill 早期输出**（当年处理到一半的书），不是出版社原始格式。特征都是旧约定：

- `<p class="content">`、`<div class="picture"><img/><p class="imgIntro">图注</p></div>`
- 注：`<sup><a id="chN" href="file#chN-back">[N]</a></sup>` + 章末 `<hr/>` +
  `<p class="fnotecontent"><a id="chN-back" href="file#chN">[N]</a>注文</p>`（链接后**没有空格**）
- 目录 `<p class="contents1|2">`、题词 `<blockquote><p>…</p><p class="inscribe">——某某</p></blockquote>`
- 版权页 `<div class="copyright margin-left2">…</div>`（内含 `<hr/>`）
- 书名页 `<div class="bookTitle"></div><div class="booksubname">…</div><div class="author">…</div><div class="publish"><img/></div>`
- 标题 h1 / h2 / h3.sigil_not_in_toc、`<link href="../Styles/style0001.css"/>`

升级到最新约定：`content`→`bodytext`；`picture`(+`imgIntro`)→`chatu`(+`caption`；
`contents1/2`→`toc1/toc2`；注号/注文→标准 noteref/fnote（补齐链接后空格、重编 noteref-N）；
题词 blockquote → `class="intro"` + 落款 `<p class="right">`；版权页→`bodytext-noindent`（独占一行的 `<hr/>` 保留）；
书名页→`<h1>书名</h1>` + `p.author` + chatu；其余交给 `postprocess()`（NBSP/中英空格/逐字 i 合并/chatu 去重/chatu 间 sprt）。

**校验**：XML 良构、无残留旧 class（content/fnotecontent/picture/imgIntro/contents1-2/inscribe/copyright…）、
旧 css、id 唯一、`#锚点` 可解析、noteref 数 == fnote 数。

## Google Books 增强版 profile 约定（epub_clean_gbs.py，`ops:switch` 固定版式页）

源：Google Books 加工过的 EPUB3（`GBSEpubSource`），正文是好的，但夹了大量谷歌扫描件留下的东西：

- **扫描页码锚点**：`<a id="GBS.0059.02"/>`（行内）与 `<div style="display:none;"><a id="GBS.…"/></div>`（整块）。
  全书 4000+ 个，**没有任何 href 指向它们** → 一律删除（脚注 id、标题 id 全部保留）。
- **固定版式页**（封面 / 书名页 / 部扉页）：
  `<ops:switch><ops:case><svg><image xlink:href="image/part01.jpg"/></svg></ops:case>
   <ops:default><img src="inserted_file_…_svg_raster.jpeg"/></ops:default></ops:switch>`
  → 改成流式图片页，用 `image/part0X.jpg`（真图），封面 `body.cover`、其余 `div.chatu`；
  `inserted_file_*_svg_raster.jpeg` 只是同一页的栅格化副本，全删。
- **opus 级清理**：spine 的 `page-map` 属性、`_page_map_.xml`、itemref 的
  `rendition:layout-pre-paginated …` 属性、manifest 里 xhtml 的 `properties="svg switch"`、
  `GBS*` meta 全部去掉；`css/styles.css + fixed.css + copyright.css` 换成单一 `styles.css`。
- **正文**：`<p>` 无 class → `p.bodytext`；`p.sans0/sans/skai`（蔣經國日記等引文）连续若干段
  → 合并成一个裸 `<blockquote>`（块内每段一个 `<p>`）；`p.p1`（一、二、三 分条）按正文段。
- **章号**：`<p class="leading">第一</p>` + `<h2>章名</h2>` →
  `<h2><span class="subtitle">第一</span><br/>章名</h2>`（不加「章」字）。
- **尾注**：`<p class="footnote" id="foot-N"><a href="文件#back-N"><span class="no">N</span></a>注文</p>`
  → `<p class="fnote" id="foot-N"><a href="#back-N">[N]</a> 注文</p>`；
  正文 `<a class="ref" href="文件#foot-N" id="back-N">N</a>` →
  `<sup><a epub:type="noteref" href="#foot-N" id="back-N">[N]</a></sup>`；`<hr/>` 保留在注文块前。
  编号**每个文件各自 1..N**，链接全部改成同文件 `#锚点`。
- **插图**：`<div class="picbox"><p class="pic"><img class="w100" src="image/picNNN.jpg"/></p>
  <p class="caption">…</p></div>` → `<div class="chatu"><p class="image"><img/></p><p class="caption">…</p></div>`
  （`w100` 丢弃；图注纯文本）。
- **书内目录** `contents.xhtml`：`p.chapter`（篇）与 `p.part`（章）→ `p.toc1`，节 → `p.toc2`，
  `h3.p0` 目次 → `h1`；EPUB3 nav（`toc.xhtml`）原样保留。
- **年表**：两列「日期｜记事」数据表**保留 `<table>`**（去掉 `<colgroup>`/`<tbody>`、单元格里的 `<p>` 壳）。
- 行内 `span.italic` → `<i>`；`span.dash`（负字距）/`span.space2`/`span.sans`/`span._2-斜體` → 去壳留字。
- 版权页 `p.serif/p.booktitle/h5` → `p.center`（h5 加 `<b>`），其余行 `p.bodytext-noindent`。
- 参考文献（`epilogue03`）：`p.s0/p.s1`（档案机构名）→ `p.bodytext-noindent`，
  `p.p02`（下属卷宗）→ `p.bodytext`；`h4`（一、二、三、四）保留。

**校验**：XML 良构、无 GBS 残锚 / `display:none` / `ops:switch` / `svg` / 源 class、noteref 数 == fnote 数、
每条注文回链能对上、chatu 必有图、`class` 全在白名单内、全书文本与源逐字相同（`[N]` 视为原数字）、
链接与锚点全部可解析。

## calibre 简类号 profile 约定（epub_clean_calibre_simple.py）

源：社科文献·甲骨文一类的 calibre 转换稿，class 很少，靠结构区分：

- 正文 `<p>`（无 class）→ `p.bodytext`；`<p class="left">` → `p.bodytext-noindent`
- 引文/条文 `<p class="block">`（连续若干段，如「三大纪律八项注意」）→ 一个 `<blockquote>`，
  段内 `<p class="bodytext">`；若某段以「——」开头且不长（引文落款）→ `<p class="right">`
- 图 `<p class="center"><img …/></p>`（+紧跟 `<p class="img">图１ …</p>`）→ `<div class="chatu">` + `caption`
- 题词页：`<p class="center1">题词</p>` + `<p class="lk">——某人，某书</p>` →
  `<blockquote class="intro"><p class="bodytext">…</p><p class="right">——…</p></blockquote>`
- 书评页（本书获誉）：书评 `p.bodytext` + 落款 `p.right`（不包 blockquote，用户口径）
- 脚注：`<a id="wN"></a><a href="文件#mN"><sup>[N]</sup></a>` →
  `<sup><a epub:type="noteref" href="#mN" id="wN">[N]</a></sup>`；
  注文 `<p class="note"><a id="mN"></a><a href="文件#wN">[N]</a> …</p>` →
  `<p class="fnote" id="mN"><a href="#wN">[N]</a> …</p>`（原 id 全保留，不改编号）
- 书内目录 `<ul><li><a href="partNNNN.xhtml#aNNN">`（两级）→ `p.toc1`（部/章）/ `p.toc2`（节）
- 版权页（含「图书在版编目」）→ `p.bodytext-noindent`，保留每行的「——」副题文字
- 空标题 `<h1 class="front"></h1>`（版权页/题词页占位）→ 删除；`h1/h2` 只留 `id`（ncx 按 id 跳转）
- 封面 `cover_page.xhtml`（内联 `<style>` + SVG `<image xlink:href>`）→ `<body class="cover">` + `<img>`；
  前折口/书名页/后折口/封底 纯图页 → 单个 chatu
- css：`Styles/style0001.css` → `Text/styles.css`（opf 里 href 要写 `Text/styles.css`），删旧 css 文件；
  封面 manifest 项补 `properties="cover-image"`

**校验**：XML 良构、无 `p.note`/`p.block` 残留、无空锚 `a#w`、noteref 数 == fnote 数且 `mN↔wN` 一一对应、
chatu 必有图、class 白名单、逐文件文本与源一致（`sup` 与 `[N]` 不计）。

## 竖排 EPUB3 profile 约定（epub_clean_vertical.py）

源：繁体竖排 EPUB3（`xml:lang="zh-TW"`），KADOKAWA 式三件套 CSS，但结构比 profile D 干净得多。

- `<html class="vrtl|hltr">`、`<body class="bodymatter" epub:type="bodymatter">`
- 正文 `<p>`（无 class）、首段 `<p id="fp">`
- `<h1 id="toc_index_N"><span class="tcy">9.</span><br/> 标题<br/> <small>副题</small></h1>`
- `<span class="tcy">数字</span>`（縦中横，全书 1000+ 处；尾注编号也用它）
- 题词 `<p class="kfont">…</p>` + `<p class="kfont text-right">──落款</p>`；年表 `<p class="t4 kfont">`
- 分隔图 `<p class="sep"><img src="../Images/sep.jpg"/></p>`；题图 `<img class="full"/>`
- 尾注 `<a id="fnref_N" href="#fn_N" rel="footnote" class="noteref" epub:type="noteref">N</a>`
  + `<div class="footnotes"><hr/><div id="fn_N" class="footnote"><p><span class="tcy">N</span>注文&#160;
  <a href="#fnref_N" role="doc-backlink">↩</a></p></div>…</div>`
- 整页图版：`<body><svg viewBox="0 0 1444 2048"><image xlink:href="../Images/NNN.jpg"/><title>图注</title></svg></body>`

**用户口径（2026-10-31）**：① **改成横排**；② **整页图版保留 `<svg><image>`**，只清外层类/属性。

处理：css → layout（去 `vrtl/hltr`、`bodymatter`、内联 `<style>`、`<meta viewport>`、`conmi/flex` 包装）
→ footnotes → quotes（`kfont` → `blockquote.intro` + `p.right`；紧跟 h1 的已有 `<blockquote>` 也标 `intro`）
→ headings（`span.tcy`/`<small>` → `span.subtitle`）→ misc（`t4`→bodytext、`sep`→sprt、`img.full`→chatu）
→ tcy（去壳留数字）→ body（`<p>`→bodytext）→ postprocess。

`nav.xhtml` 只做轻处理（去 `vrtl`、去 `tcy` 壳、换 css），保留其 EPUB3 nav 结构。

**纯图片部扉页**按 `nav.xhtml` 的目录链接文字加 `<h1>` 包裹：
`<svg id="toc_index_1">…</svg>` → `<h1 id="toc_index_1" title="One　前奏"><svg …/></h1>`（`step_plate_heading`）。文字取目录项（保留全角空格），`id` 从 `svg` 移到 `h1`，nav/ncx 的锚点照旧可解析；只认带 `#锚点` 的目录链接（封面「封面」、正文起点「內文」这类 landmarks 不算），页面有可见文字或已有 `h1` 的不动。

**标题级别跟 nav 层级走**（`step_heading_level`）：`nav.xhtml` 里顶层 `<li>` 的页面用 `h1`，嵌在部下面的 `<ol>` 里的章（深度 ≥ 2）一律改 `h2`（保留 `id="toc_index_N"` 与内部 `span.subtitle`/`br/`）。

**校验**：XML 良构、无 `vrtl/hltr/bodymatter/tcy/kfont/sep/t4/full/conmi/flex` 残留、无内联 `<style>`、
旧 css、id 唯一、`#锚点` 可解析、noteref 数 == fnote 数。

## 已知陷阱（脚本已处理，分析报告出现异常时按此排查）

- **章号与章名是两个连续 `<h1>`**（各自包在 `div.header0` 里，如《第三帝国的生与死》第一~四章）：`h_fix`/`unwrap`
  之后用 custom 钩子（`custom_steps_position: "post"`）合并为
  `<h1><span class="subtitle">第一章</span><br/>章名</h1>`；这类文件常常**整篇只有标题、没有正文**，
  按「纯标题页」口径并入下一节文件（本文档已确认），合并后要把 opf 的 item/itemref、ncx、nav 里的指向改到新文件。
- **calibre/InDesign 导出的 opf 里 `<item id="…" href="…"/>` 是 id 在 href 之前**：删 manifest 项时按 `href` 匹配没问题，
  但删 `itemref` 要按 **id**（id 常等于文件名，如 `Section0001_0003.xhtml`），否则 spine 里会留下指向已删文件的死项。
- **标题/目录行可能丢掉开头或结尾的「」**：Kindle→calibre、Google Books 的转换偶尔会吃掉
  `「`（《意外的國度》第十章「中華民國在台灣」的永久化，正文 h1、书内目录、ncx 三处全缺左引号）。
  profile T/U 的 `verify` 已加检查：`h1/h2(/h3)` 与 `p.toc1/toc2` 里 `「` 与 `」` 必须成对，
  发现后按同一句在书内目录/ncx 里补回（三处要一致）。
- 插图 div 的 img 和 `</div>` 在同一行（`alt=""/></div>`），`</div>` 不单独成行。
- 同一 footnote id 可对应多条**内容不同**的 aside，靠 noteref 的 alt 文本区分。
- 段落可能跨多行（内嵌 SVG 生僻字），p 级转换禁用行锚定正则（脚本用 dotall 非锚定）。
- div 最后一个子元素的行尾常带 `</p></div>`（同行的闭合 div）。
- chatu caption 无论 span 带不带样式都按 `<p><span[^>]*>…</span></p>` 提取。
- h 标签内检查 `<b>` 残留时必须排除 `<br/>`（`"<b" in content` 是错的）。
- 字图辨识要核对引文：同一段古籍引文在不同章节重复出现时，替换字应一致
  （曾出现同一句引文在两章被辨成不同字、其中一个是错的情况）。
- 改 class 值时用 `class="X(?=[\s"])` 前瞻 + 替换成**不带收尾引号**的 `class="Y`；
  写成 `class="Y"` 会多出一个引号（`class="bodytext""`），破坏 XML。
- 处理嵌套 span（外层无 class、内层有 class）必须用**平衡匹配**，非贪婪 `(.*?)</span>`
  会在内层 `</span>` 处截断，导致标签错乱。
- 路径含中文时不要用 PowerShell `-Command` 内联 Python/正则（引号与编码会被破坏）；
  逻辑写进 `.ps1`（UTF-8 with BOM）或 `.py` 文件再执行。
- KADOKAWA 竖排书：两位数的注号常被 `<span class="tcy">`（縦中横）包裹；Kobo 导出版本还会被
  `<span class="koboSpan">` 再包一层。注释编号正则应容忍这两层，否则 `10` 以上全部漏加方括号。
- 部分 Kobo 导出的 KADOKAWA 文件**源本身就不是良构 XML**（如 `<span><span>41</a>`）；
  XML 校验应「源可解析才要求结果可解析」，否则会把源的问题误判为自己的。

## 其他源格式（cookbook）

- `<figure><img/><figcaption>` → chatu：pattern
  `<figure id="([^"]+)"><img src="([^"]+)"[^>]*/><figcaption>(.*?)</figcaption>\s*</figure>`
- `<section class="epigraphs">` 章首引文 → `<blockquote class="intro">` + `<p class="right">` 落款
- `<section class="endnotes"><ol>` → fnote 列表（配 backlink）
- calibre 源：`<p class="bodytext">` 可能已就位，只需 chatu/脚注规则；用 analyze 先看
以上写进 `custom_clean.py` 即可复用主流程的校验。

## 命令速查

```
$py = "python"                      # 或 py -3 / 真实解释器完整路径
$sk = "<本 skill 目录>/scripts"
$sc  = "$sk/epub_clean.py"          # profile A 得到/中华书局
$sc2 = "$sk/epub_clean_calibre.py"  # profile B calibre+duokan
$sc3 = "$sk/epub_clean_weread.py"   # profile C 微信读书/QQ阅读
$sc4 = "$sk/epub_clean_kadokawa.py" # profile D KADOKAWA（阶段二；Kobo 版加 --strip-kobo --drop-scripts --drop-kobo-style）
$sc5 = "$sk/epub_clean_duokan.py"   # profile E 多看原生（图片式注释标记）
$sc6 = "$sk/epub_clean_indesign.py" # profile F InDesign/Adept
$sc7 = "$sk/epub_clean_ptpress.py"  # profile G 人民邮电/得到（p.content 系）
$sc8 = "$sk/epub_clean_duokan_biaoti.py" # profile H 多看原生·内文/标题（neiwen/biaoti）
$sc9 = "$sk/epub_clean_kobo.py"     # profile I Kobo 导出·多看式排版（koboSpan）
$sc10= "$sk/epub_clean_indesign_calibre.py" # profile J InDesign→calibre 繁中重注本（_idParaDest/div.foot）
$sc11= "$sk/epub_clean_zhangyue.py" # profile K 掌阅 ZHANGYUE（text-title-*/noteref_N，已语义化稿）
$sc12= "$sk/epub_clean_kindle_cn.py" # profile L Kindle-cn 亚马逊中国（kindle-cn-*/chatu_img 广告）
$sc13= "$sk/epub_clean_indesign_epub3.py" # profile M InDesign EPUB3 新版导出（ff_serif/fz_*/ti_*）
$sc14= "$sk/epub_clean_bookcrafter.py" # profile N bookcrafter 生成版（bookcrafter-body-paragraph + 纯文本 (N) 尾注）
$sc15= "$sk/epub_clean_bodycontent.py" # profile O 文景/上海人民（bodyContent-1 + 跨文件 jz/jzyy 注）
$sc16= "$sk/epub_clean_baqi.py"  # profile P 八旗文化繁中（p.kai / ol.footnote fnX- / img.pw 回链箭头）
$sc17= "$sk/epub_clean_legacy.py" # profile R 旧成果收尾（content/picture/fnotecontent）
$sc18= "$sk/epub_clean_gbs.py"    # profile T Google Books 增强版（GBS 页码锚点 / ops:switch 固定版式页）
$sc19= "$sk/epub_clean_kindle_calibre2.py" # profile U Kindle→calibre 第二套类号（标题是 blockquote）
$sc20= "$sk/epub_clean_calibre_simple.py"  # profile V calibre 简类号社科书（p.note/p.block）
$sc21= "$sk/epub_clean_vertical.py"        # profile W 竖排 EPUB3（vrtl/tcy/noteref，转横排）
& $py -X utf8 $sc  analyze <dir> -o <tmp>/report.txt   # 体检（只读）
& $py -X utf8 $sc  process <dir> --dry-run             # 试处理→临时目录
& $py -X utf8 $sc  process <dir>                       # 正式处理（自动备份+校验）
& $py -X utf8 $sc  verify <dir>                        # 独立复检
```

**通用后处理**（对任意已清洗目录补跑共同规则，如「删 chatu 之间的 sprt」）：

```
& $py -X utf8 "$sk/epub_clean_fix.py" process <dir> [--dry-run]
& $py -X utf8 "$sk/epub_clean_fix.py" verify  <dir>
```

共同规则集中在 `scripts/epub_clean_common.py`，各 profile 已自动调用；`epub_clean_fix.py` 用于旧成果补跑。
