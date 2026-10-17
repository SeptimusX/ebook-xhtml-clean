# ebook-xhtml-clean

把各类来源的电子书章节 XHTML 清洗为统一的语义化格式（`bodytext` / `fnote` / `chatu` / `blockquote` + `styles.css`）。
An opencode skill / CLI for cleaning EPUB xhtml from sixteen common Chinese e-book sources.

## 支持的源格式（十六套 profile）

| # | profile | 脚本 | 典型特征 |
|---|---|---|---|
| A | 得到 / 中华书局 | `scripts/epub_clean.py` | `<aside epub:type="footnote">注文</aside>`、仿宋引文、`<p><span style="…">` 内联样式 |
| B | calibre + 多看(duokan) | `scripts/epub_clean_calibre.py`（**配置驱动**：`<dir>/clean_config.json`，`calibreNN` 类号逐书不同） | `calibreN` 类、duokan 脚注 `<ol><li>`、`<div class="calibre13">` 图 |
| C | 微信读书 / QQ阅读 | `scripts/epub_clean_weread.py` | `readerChapterContent`、`data-wr-footernote`、`p.content` / `p.quotation` |
| D | KADOKAWA 竖排 / 固定版式 | `scripts/epub_clean_kadokawa.py` | `book-style.css`、`kfont` 引文、`key1`/`key2` 注释锚点 |
| E | 多看原生（图片式注释标记） | `scripts/epub_clean_duokan.py` | `p.text`、`h2.chapter-title2`、`../Styles/*.css`、`a.duokan-footnote` + `note.png` |
| F | InDesign / Adept | `scripts/epub_clean_indesign.py` | `<h1 class="f_" id="_idParaDest-N">`、`p.f_1`/`f_2`/`f_4`、`_idfootnotelink`、`<div type="footnote">`、`<div class="mg_l_*">` 图 |
| G | 人民邮电 / 得到（`p.content` 系） | `scripts/epub_clean_ptpress.py` | `h1.firstTitle#sigil_toc_id_N`、`p.content` / `content_100..110`、`div.pic`+`imgtitle`、`span.kt_104`、`span.super[id=refN]`+`p.noindent[id=annotN]` |
| H | 多看原生 · 内文/标题（`neiwen`/`biaoti`） | `scripts/epub_clean_duokan_biaoti.py` | `p>span.neiwen`（变体 `neiwen2/2_1/3/4/5/6`）、`h1>span.biaoti1`+`biaoti2`、`h2>span.biaoti3`/`biaoti5`、`div.duokan-image-single`+`maintitle`/`subtitle`、`a.duokan-footnote`+`note.png`、`ol.duokan-footnote-content`、`hr.xian`、`p.whitespace` |
| I | Kobo 导出 · 多看式（`koboSpan`） | `scripts/epub_clean_kobo.py` | `style.kobostylehacks` + `../Styles/css.css`、`div#book-columns>div#book-inner`、每段文字被 `span.koboSpan[id=kobo.N.M]` 包裹、`h1.h2`(章)/`h1.h1`(后记)/`h2`(节)、`p.kh`(楷体引文)、`p.no.fs`(年表)、`div.hr`(题词)、`a.duokan-footnote`+`06.png`、`aside`+`ol.duokan-footnote-content` |
| J | InDesign→calibre 繁中重注本（`_idParaDest`） | `scripts/epub_clean_indesign_calibre.py` | `body#story-N.calibre2` + `div.calibre3`、`h1[id=_idParaDest-N].calibre4>span.small`、`h5.calibre8`/`h6.h6_b`、`p.calibre5`/`p_`/`calibre11`、`p.end`/`end_k`、`p.kai_n`/`kai_nb`、`div.container`+`img.fit`+`p.caption`、`table.calibre9`、`img.pw`(生僻字图)、`div.foot`+`hr.calibre6`+`p.footnote`+`a.ref1`(章内注)、`a.calibre7`(跨文件引用注) |
| K | 掌阅 ZHANGYUE（`text-title-*`，已语义化稿） | `scripts/epub_clean_zhangyue.py` | `h1.text-title-1-c/-r`、`div.zhangyue-c80>h2.text-title-2[id=sigil_toc_id_N]`、`h3.text-title-3`、`p.bodytext`(本已语义化)、`sup>a[href=#note_N][id=noteref_N]` + 文末 `pre>code` `[注释]`、`p.bodytext>span>a[id=note_N]`、`div.zhangyue-c>img.zhangyue-img`+`p.bodytext-no`+`p.img-note`、`span.fangsong`、`../Styles/Style0001.css`+`jianrong.css`、内联 style |
| L | Kindle-cn 亚马逊中国（`kindle-cn-*`） | `scripts/epub_clean_kindle_cn.py` | `body.calibre`、`../stylesheet.css`+`../page_styles1.css`、`h1.kindle-cn-heading[id=calibre_pb_0]`、`h2.kindle-cn-heading2`(内嵌空锚 `a[id=sec001].calibre6`)、`h3.kindle-cn-heading3`、`p.calibre1`/`p.kindle-cn-para-2em-indent`/`-no-indent(1)`、`p.kindle-cn-poem-left`、`p.kindle-cn-signature(1)`、尾注 `a[id=chN-back][href=file#chN]>sup.calibre5` + `p.fnote>a[id=chN]`、`div.empty`+20×U+2014、`div.kindle-cn-toc-level(1)`、`div.kindle-cn-bodycontent-div-alone`、`img.kindle-cn-inline-character`、`div.chatu_img`+`gaiword.png` |
| M | InDesign EPUB3 新版（`ff_serif/fz_*/ti_*`） | `scripts/epub_clean_indesign_epub3.py` | `body#BK7026X-N` + 无 class 外层 `div`、`css/YYYY.N.h.css`、`h1.ff_serif.fz_1-9em.ta_left[id=_idParaDest-N]`、`p.ff_serif.fz_1-0em.ti_2em`、`p.ff_cursive.fz_1-0em.mg-str_2-0em`、`ta_right`、`p.ff_serif.fz_1-6em`、`p.ff_sans.fz_1-0em.ta_center`、`span.ff_serif/ff_sans.fw_900`、`span.ff_cursive.fs_italic`、`a._idFootnoteLink[role=doc-noteref]` + `hr.HorizontalRule-1` + `section._idFootnotes>ol>li._idFootnote>a._idFootnoteAnchor`、`div.mg-str_10pr.mg-end_10pr`、`div[class~=box]`、`<p>　</p>` |
| N | bookcrafter 生成版（磨铁 / Z-Library） | `scripts/epub_clean_bookcrafter.py` | `../Styles/style.css` + 内联 `<style>`(duokan-text-indent)、`h1[style]`、`p.bookcrafter-body-paragraph`、**纯文本编号脚注**（正文 `(1)`、章末 `p.bookcrafter-body-paragraph` 以 `(N)` 开头）、目录页 `div.toc-list` |
| O | 文景 / 上海人民（`bodyContent-1`，跨文件注） | `scripts/epub_clean_bodycontent.py` | `../Styles/stylesheet.css`+`stylesheet-1.css`、`h1.chaptertitle-c/parttitle-c/prefacetitle-c/backtitle-c[id=isbn…]`、`h3.txtheading-1-c`/`h4.txtheading-2-c`、`p.bodyContent-1(-top/-top-2/-c)`、`p.noindent-copyContent-1`、`p.hang-bodyContent-1`、`p.bodyContent-2-kaiti(-top-4)`、跨文件注 `a[href=partNNNN.xhtml#jz_X][id=jzyy_X]>sup.(N)` + `p.fnContent-1>a[id=jz_X]`、`div.chatu_img/title_img>img.pic-img`、`p.contents-1/2/3` |
| P | 八旗文化（繁中 InDesign，`p.kai`/`ol.footnote`） | `scripts/epub_clean_baqi.py` | `../Styles/Style.css`(+`Copyright.css`)、`h1/h2[title]` 内 `span.num`+`span.num2`、`h3.h3.sigil_not_in_toc`、正文 `<p>` 无 class、`p.kai`/`div.kai`、`p.sec`、`div.pic/pic-c>img+span.caption`、`a.footnote[href=#fnX-N][id=fX-N]` + `ol.footnote>li[id=fnX-N]`(+`img.pw` 回链箭头)、`p.ref`、`p.title`+`p.item`、`div.boxend`、`<p><br/></p>` |

先跑 `analyze` 判断属于哪一套，再选脚本。类名对不上时：改该脚本顶部的 `CONFIG`（若能覆盖）或另立一套。

## 输出规范（所有 profile 统一）

- **只做语义化 + 同目录 `styles.css`**；不内联 CSS、不留源 class（`calibre*` / `kindle-cn-*` / `ff_*` / `fz_*` / `zhangyue-*` …）
- **正文** → `<p class="bodytext">`；顶格段 → `bodytext-noindent`；右对齐署名 → `p.right`；章首作者行 → `p.author`
- **脚注 → 章末尾注**：正文 `<sup><a epub:type="noteref" href="#foot-N" id="back-N">[N]</a></sup>`，
  章末 `<hr/>` + `<p class="fnote" id="foot-N"><a href="#back-N">[N]</a> 注文</p>`，**双向回链成对**
- **引文 → `<blockquote>`**：连续引文段合并成一个块；楷体引文不加 `span.kai`；题词/引文 + `──落款` → `<blockquote class="intro">`（落款留在块外）；诗句 → `<blockquote class="poem">`
- **插图 → `<div class="chatu"><p class="image"><img/></p>…</div>`**；图注 → `p.caption`；图片页同格式；
  **两个 `chatu` 之间不放 `p.sprt`**（有则删），由 `scripts/epub_clean_common.py` 统一处理
- **标题**：章 `h1`、节 `h2`/`h3`（按源层级归一到 h1–h4）；`span.subtitle` **只在"分行"时用**（标签 span 后紧跟 `<br/>`，或以 `──`/`──` 开头的副题）；`<h1><span>前言</span></h1>` 这类一律拆成纯文本
- **空行段**：保留源书空行（`<p class="bodytext"><br/></p>`），但**连续多个折一个**、**blockquote 前后紧邻的删掉**
- **编号**：同一本书两套脚注用**不同数字体系**区分（如文件内小写罗马 / 跨文件阿拉伯）；单一体系时每文件（= 每章）从 `[1]` 重排
- **锚点必须保留**：`_idParaDest-N` / `secNNN` / `sigil_toc_id_N` / `calibre_pb_0` / `_idContainer*`（后者可随解包消失）——`toc` / `ncx` 按它们跳转
- **正字与细节**：`○`(U+25CB) → `〇`(U+3007)；`<img>` 一律自闭合并统一属性顺序；必要处给 `<html>` 补 `xmlns:epub`

## 通用机制与校验

每套脚本子命令一致：`analyze`（只读体检）｜`process`（自动备份 + 校验，`--dry-run` 试跑到临时目录）｜`verify`（独立复检）。
**校验不过就不写回**；原文件备份到 `%TEMP%/opencode/`，目录里的 `.bak` 只读跳过。

校验项：XML 良构、无残留源 class / 内联 style、id 唯一、**源 id 一个不丢**（J/K/L/M 有）、`ref↔fnote` 配对、`styles.css` 已链。
另有库外的**全文文本完整性**比对（逐字 diff，允许预期新增：如生僻字替换）。

## 主要能力

- **脚注 → 尾注**：`[N]` 编号 + 双向回链；符号注（`[*]`、`[†]`…）自动分组
- **插图 → chatu**：装饰性重复小图自动删除（或降级为 `sprt`），真插图保留图注
- **引文 → blockquote**：连续引文段合并；块内每行独立成 `p.bodytext`
- **正文 → bodytext**：章副标题并入 `h1`、`h` 标签去 `b`、CSS 链接统一为 `styles.css`
- **杂项**：内嵌 SVG/图片生僻字图替换为实际字符、全角字母/数字转半角、注释编号方括号化

## 两条工作流（需要人参与的部分）

**① 按 h1 合并章节**（源常是"一页一文件"，如 `BK7026X-1..106.xhtml`）：
按 `h1` 分组 → 各文件正文拼接、**每个文件的 `<hr/>`+尾注 section 统一收到章末** → 删掉其余文件 →
同步 `content.opf`（删 manifest item 与 spine itemref）→ 复核 `toc.xhtml`/`toc.ncx` 只引用保留文件。
**注意**：`_split_000` 之类不一定是垃圾——`text00014_split_000/001` 就是一整章被拆两半（ref 在 _000、注在 _001，编号跨文件共享）；
只有整篇只剩空 body 的才是广告残片。

**② 生僻字图人工确认**：拼成带编号的对照表（PIL，每张 5×5、放大到 240px）**自查字形** →
生成**交互式确认页**（一行一张图：图 ｜ 判定+线索+上下文 ｜ 勾选确认 / 输入框填正确字，顶部有进度、全选、**导出结果**）→
浏览器面板用 `python -m http.server` 提供 http 地址打开（`file://` 不被接受）→ 收回确认结果写成 `<dir>/rare_map.json`
（键是 **img 的 `src` 全名**如 `Image00003.jpg`）→ 重跑 profile 即替换并计数。

## 已知边界

- 各 profile 靠**特征类名**匹配；新变体要另立 profile 或改 `CONFIG`（B、M 的 `CONFIG` 较完整）
- **生僻字增补平面字**（U+2xxxx）在部分阅读器/字体中无字形、会显示成方框——可把这些改回保留图片
- **删广告残片**后 `opf`/`ncx` 需同步；**指向被删文件的目录条目要"改指"真实内容文件，不能连带删**（否则整章丢出目录）
- 清洗完仍建议在 Sigil 里过一遍（TOC 重排、字体嵌入、`opf` 校验）

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

通用后处理（对任意已清洗目录补跑共同规则，例如「删 chatu 之间的 `p.sprt`」）：

```bash
python scripts/epub_clean_fix.py process <dir> [--dry-run]
python scripts/epub_clean_fix.py verify  <dir>
```

## 要求

- Python 3（只用标准库，无第三方依赖；生僻字拼图自查需 Pillow）
- 各 profile 会 `from epub_clean_common import strip_sprt_between_chatu`，**请连同 `scripts/epub_clean_common.py` 一起安装**（`epub_clean_fix.py` 同样依赖它）
- 目标目录为书籍解包后的文本目录，同目录应有 `styles.css`
- 脚本会自动把原文件备份到系统临时目录；目录里的 `.bak` 只读跳过

## 文档

完整约定（各 profile 的处理顺序、默认输出格式、已知陷阱）见 [`SKILL.md`](SKILL.md)。

## 变更记录（本轮）

- **通用规则：两个 `chatu` 之间不放 `p.sprt`**（有则删）—— 实现于 `scripts/epub_clean_common.py`，16 个 profile 写出前自动调用；旧成果可用 `scripts/epub_clean_fix.py process <dir>` 补跑
- **新增 profile P**（八旗文化 繁中 InDesign）：无 class 的 `<p>` 正文、`span.num/num2`→subtitle 分行、`p.kai`/`div.kai`→blockquote、`ol.footnote`+`img.pw` 回链箭头→`hr`+fnote、`p.sec`→sprt、`p.ref/item/title`→bodytext-noindent
- **新增 profile O**（文景/上海人民 `bodyContent-1`）：跨文件 `jz_X`/`jzyy_X` 脚注原样保留并双向化、楷体引文→blockquote、`contents-1/2`→toc1/toc2（三级只留前两级）、标题保持 h1/h3/h4 原层级；新增**目录级跨文件锚点校验**
- **新增 profile N**（bookcrafter 生成版 / 磨铁·Z-Library）：`p.bookcrafter-body-paragraph`、纯文本 `(N)` 脚注（含孤儿注保留不回链）、占位标题 `正文 28`→`28`、`div.toc-list` → `p.toc1`
- **新增 profile J**（InDesign→calibre 繁中重注本）、**K**（掌阅）、**L**（Kindle-cn，含 `rare_map.json`）、**M**（InDesign EPUB3 新版）
- 脚注编号体系：文件内 vs 跨文件用不同数字体系区分；注文去掉外层 `<p>` 与 `：`
- 章首作者行 → `p.author`；h1 内 `span.subtitle` 收紧为"仅分行"；引文/图注/脚注内不用 `span.kai`
- 空行段：保留 + 连续折叠 + blockquote 旁删除；双 `<hr/>` 去重
- `○`(U+25CB) → `〇`(U+3007) 整体替换
- 删除广告残片时同步 `opf`/`ncx`，并把指向它的目录条目改指真实内容
- 各脚本新增"**源 id 不丢**"守护；`process` 日志补充兜底类清单，便于补规则
