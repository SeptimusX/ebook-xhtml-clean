# ebook-xhtml-clean

把各类来源的电子书章节 XHTML 清洗为统一的语义化格式（`bodytext` / `fnote` / `chatu` / `blockquote` + `styles.css`）。
An opencode skill / CLI for cleaning EPUB xhtml from four common Chinese e-book sources.

## 支持的源格式（四套 profile）

| profile | 脚本 | 典型特征 |
|---|---|---|
| 得到 / 中华书局 | `scripts/epub_clean.py` | `<aside epub:type="footnote">注文</aside>`、仿宋引文、`<p><span style="…">` 内联样式 |
| calibre + 多看(duokan) | `scripts/epub_clean_calibre.py` | `calibreN` 类、duokan 脚注 `<ol><li>`、`<div class="calibre13">` 图 |
| 微信读书 / QQ阅读 | `scripts/epub_clean_weread.py` | `readerChapterContent`、`data-wr-footernote`、`p.content` / `p.quotation` |
| KADOKAWA 竖排 / 固定版式 | `scripts/epub_clean_kadokawa.py` | `book-style.css`、`kfont` 引文、`key1`/`key2` 注释锚点 |

先跑 `analyze` 判断属于哪一套，再选脚本。

## 主要能力

- **脚注 → 尾注**：`[N]` 编号 + 双向回链，章末 `<hr/>` 后集中列出；符号注（`[*]`、`[†]`…）自动分组
- **插图 → chatu**：装饰性重复小图自动删除（或降级为 `sprt`），真插图保留图注
- **引文 → blockquote**：连续引文段合并为一个块
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

KADOKAWA 的 Kobo 导出版本额外加 `--strip-kobo --drop-scripts --drop-kobo-style`。

## 要求

- Python 3（只用标准库，无第三方依赖）
- 目标目录为书籍解包后的 `<项目>/xhtml`，同目录应有 `styles.css`
- 脚本会自动把原文件备份到系统临时目录；目录里的 `.bak` 只读跳过

## 文档

完整约定（各 profile 的处理顺序、默认输出格式、已知陷阱）见 [`SKILL.md`](SKILL.md)。
