# GB/T 7714-2015 参考文献格式补充说明

排版脚本 `layout_generate_docx.py` 中的 `format_gbt7714()` 会按这里的字段约定输出参考文献。下面只列这次和期刊 / 论文集补全相关的要求。

## 1. 学术期刊 [J]

格式：

```text
序号 作者. 题名[J]. 刊名, 出版年份, 卷号(期号): 起页-止页.
```

英文文献要求：

- 检索得到的英文期刊文献，尽量自动补齐 `volume`、`issue`、`pages`
- 参考文献输出时应尽量达到 `volume(issue): pages`
- 如果自动检索后仍缺失，`run_preflight.py` 会报出缺字段，提醒继续补录

字段映射：

- `authors` -> 作者
- `title` -> 题名
- `venue` -> 刊名
- `year` -> 出版年份
- `volume` -> 卷号
- `issue` -> 期号
- `pages` -> 起页-止页
- `doi` -> `DOI:...`

中文文献要求：

- 中文期刊文献如果缺 `volume`、`issue`、`pages`，不强制自动补齐
- 由用户根据知网 / 万方 / 原始 PDF 手工核对并补齐

## 2. 论文集 / 会议文献 [C]

格式：

```text
序号 作者. 题名[C]. In: 主编/eds. 论文集名. 出版地: 出版社, 出版年: 起页-止页.
```

英文文献要求：

- 对英文会议 / 论文集文献，优先通过 CrossRef 自动补齐：
  - `booktitle`
  - `publisher`
  - `pub_place`
  - `pages`
  - `isbn`
  - `editors`
- 如果是带 ISBN 的论文集，参考文献里应尽量体现 `In:`、主编 / `eds.`、论文集名、出版地、出版社、出版年、起止页
- 如果自动检索后仍缺字段，`run_preflight.py` 会报出缺字段

字段映射：

- `authors` -> 作者
- `title` -> 题名
- `editors` -> 主编 / `eds.`
- `booktitle` -> 论文集名
- `pub_place` -> 出版地
- `publisher` -> 出版社
- `year` -> 出版年
- `pages` -> 起页-止页
- `isbn` -> ISBN

中文文献要求：

- 中文论文集文献如果缺主编、论文集名、出版地、出版社、起止页等字段，不要求 Agent 自动编造
- 由用户根据原始论文集封面页、版权页、目录页手工补齐

## 3. BibTeX 导出

`literature_search.py` 和 `literature_import_pdfs.py` 重建 `library/references.bib` 时，当前会保留这些字段：

- 期刊：`journal`、`volume`、`number`、`pages`
- 论文集：`booktitle`、`editor`、`publisher`、`address`、`isbn`、`pages`

这样后续重新导入中文 PDF 时，不会把已经补好的英文论文集字段冲掉。
