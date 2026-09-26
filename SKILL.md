---
name: ebook-xhtml-clean
description: 电子书 EPUB xhtml 清洗流水线（五套 profile：得到/中华书局、calibre+多看、微信读书/QQ阅读、KADOKAWA 竖排、多看原生图片式注释）——脚注提取为 fnote 尾注列表（[N] 编号、双向回链、符号注分组）、插图 div 转 chatu（装饰图删除/降级）、引文段合并转 blockquote、内嵌 SVG 生僻字图替换为实际字符、正文加 bodytext、章副标题并入 h1、解包 header/part div、h 标签去 b、链接 styles.css、全角转半角与注释编号方括号化，并自动校验 XML/链接/编号/正文完整性。当用户说『按照 2do.md 处理 xhtml』、『处理/提取脚注（尾注、注释）』、『清洗/规范化 EPUB xhtml』、『微信读书导出清理』、『KADOKAWA 竖排书处理』，或提到 fnote、bodytext、chatu、noteref、data-wr-footernote、duokan-footnote、note.png、kfont、key1/key2 时使用。
---

# EPUB xhtml 清洗流水线

把 EPUB 的 xhtml 转换为标准格式（`bodytext` / `fnote` / `chatu` / `blockquote` + `styles.css`）。
目标目录通常是书籍解包后的 `<项目>/xhtml` 或 `<项目>/EPUB/xhtml`（同目录应已有 `styles.css`）。

## 五套 profile（先 analyze 判断，再选脚本）

| 源格式 | 脚本 | 特征 |
|---|---|---|
| 得到/中华书局（纯文本 aside） | `scripts/epub_clean.py` | `<aside epub:type="footnote" id="…">注文</aside>`、`<div style="display: block;text-align:center;">` 图、FZFangSong 引文、`<p><span style="…">` 内联样式、`.bak` 原始文件 |
| calibre + 多看(duokan) | `scripts/epub_clean_calibre.py` | `<body class="calibre2">`、`<p class="calibre7"><span class="calibre10">`、`calibre23` 引文、`<aside…><ol class="duokan-footnote-content"><li>` 脚注、`<div class="calibre13">` 图 |
| 微信读书 / QQ阅读 | `scripts/epub_clean_weread.py` | `<section class="readerChapterContent"><div data-wr-bd="1">`、`<span data-wr-id="layout">`、`<p class="content">` / `<p class="quotation">`、`<span class="reader_footer_note" data-wr-footernote="注释">`、`styles/common.css` + 内联 `<style>` |
| KADOKAWA 竖排/固定版式 | `scripts/epub_clean_kadokawa.py`（**只做阶段二**） | `<html … xml:lang="zh-TW" class="hltr">`、`../style/book-style.css`、`<p class="mfont font-1em10">` 空段、`<p>　　<br/></p>` 版式空行、`class="kfont"` 引文、`class="key1"/"key2"` 注释锚点、`mokuji-` 锚点 |
| 多看原生（图片式注释标记） | `scripts/epub_clean_duokan.py` | `<p class="text">`、`<h2 class="chapter-title2" id="sigil_toc_id_N">`、`../Styles/stylesheet.css` + `oxenfont.css`、正文 `<a class="duokan-footnote" …><img src="../Images/note.png"/></a>`、文末 `<ol class="duokan-footnote-content">` |

**注意**：KADOKAWA 书几乎没有语义标签，需**先人工做阶段一语义化重排**（规则见下），脚本只做阶段二
（全角→半角 + 注释编号方括号化）。

五套脚本的子命令、备份、校验机制相同（analyze / process / verify，`--dry-run` 试跑）。

## 环境要点

- 用 `python -X utf8` 运行（Windows 上若 PATH 里的 `python` 是 Microsoft Store 假桩、
  静默无输出，改用 `py -3` 或 `where python` 找到的真实解释器完整路径）。
- 控制台输出中文可能乱码：`analyze` 用 `-o 报告路径` 写文件再读；process/verify
  的输出行以 ASCII 为主，可直接看。
- 文件一律 UTF-8 无 BOM、LF 行尾（脚本已按此读写，保持原样）。
- 目录里的 `.bak` 是保留的原始文件，**只读、绝不修改、处理时自动跳过**。
- 处理前脚本自动把原文件备份到系统临时目录 `<TEMP>/opencode/epub-clean/<目录名>-<时间戳>/`。

## 工作流

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

- 脚注：正文 `<sup><a epub:type="noteref" href="#footnote-x" id="noteref-N">[N]</a></sup>`；
  章末 `<hr/>` 后 `<p class="fnote" id="footnote-x"><a href="#noteref-N">[N]</a> 注文</p>`；
  编号每文件从 [1] 重新开始；重复的 footnote id 输出时加 `-2`/`-3` 后缀消歧
  （noteref→aside 按 alt 文本精确配对，aside 正文为权威文本）。
- 插图：`<div class="chatu">` + `<p class="image"><img src=... alt=""/></p>` + `<p class="caption">`。
- 引文：整段 FZFangSong 仿宋引文，连续段合并为一个 `<blockquote>`，内部段落保留
  `class="bodytext"`，段内 noteref 保留。
- 章副标题：h1 后紧跟的居中样式段并入 h1 →
  `<h1>标题<br/><span class="subtitle">——副题</span></h1>`（h1 内原有 span/b 标签去掉）。
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
  unwrap → h1_subtitle → bold_bodytext → bodytext → join_multiline_p → h_fix →
  css → append（chatu 先于引文规则消费 fangsong caption；footnotes 先于引文规则
  以免 aside 割裂连续性；unwrap 先于 bodytext/h1_subtitle）。

## calibre + duokan profile 约定（epub_clean_calibre.py）

映射（脚本内 CONFIG 可调）：

- `calibre10` / `calibre26` → `<p class="bodytext">`（去 span）
- `calibre23`（连续整段）→ `<blockquote>` + `<p class="bodytext">`；
  **紧跟插图的 `calibre23`（配图说明）→ 并入该 `<div class="chatu">` 的 `<p class="caption">`**
- `calibre19` / `calibre27` / `calibre28` → 去 span，保留 `<i>`（行内英文书名）
- `calibre17` → `<h3>`；`calibre24` / `calibre29` → `<h4>`（span 上的 id 移到标题上）
- `calibre21` / `calibre22` → **`<p class="right">`**（正文底部署名/日期，右对齐），
  并在正文与署名之间插入一个 `<p class="bodytext"><br/></p>` 空行段
- `calibre13` 图 div → **先判装饰图**：尺寸小于 `ornament_max_bytes`（默认 50KB）
  或列在 `drop_images` 名单 → 视为装饰图；**紧邻标题(h1–h4)前后 → 整块删除**，
  否则 → `<p class="sprt"><img/></p>`；其余（真插图）→ `<div class="chatu">`
  （analyze 会列出引用图片及尺寸，供确定阈值/名单）
- 仅含一图的包裹 div（扉页）→ 按同一装饰图判断，否则 chatu
- h1 文字型 → `<h1>文本</h1>`（保留 id，去 span/b/class）；
  **h1 包图型 → 加 `title="<title>内容"`**，去 class，img 只留 src/alt
- duokan `aside`（`<ol><li>`）→ 章末 `<hr/>` + `<p class="fnote">`；noteref → `[N]` + 双向回链
- css 链接 → `styles.css`（删除 calibre 的 stylesheet.css / page_styles.css）
- `<body class="calibre2">` → `<body>`；`<div class="calibre3">` 解包；清理空行与行首缩进
- 源文件可能是 **CRLF**，脚本读取时统一为 LF
- 装饰图常见形态：同一张很小的图（十几 KB）在小节标题后重复出现；真照片通常 ≥ 80KB。
  阈值以 `analyze` 报告的图片尺寸为准。删除装饰图后注意 `tidy` 会清掉留下的空行
- 编辑判断（不自动化，遇到时照做）：诗歌引文若与相邻正文诗行混标（如 calibre10+calibre23
  同一首诗）→ 统一处理；图片页（无 h1）可手工加 `<h1 title="栏目名"></h1>`

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

## 已知陷阱（脚本已处理，分析报告出现异常时按此排查）

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
& $py -X utf8 $sc  analyze <dir> -o <tmp>/report.txt   # 体检（只读）
& $py -X utf8 $sc  process <dir> --dry-run             # 试处理→临时目录
& $py -X utf8 $sc  process <dir>                       # 正式处理（自动备份+校验）
& $py -X utf8 $sc  verify <dir>                        # 独立复检
```
