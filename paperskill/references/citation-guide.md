# Citation Guide

本文件只描述当前脚本链路认可的引用语法、cite-key 规则和核验边界。

## Core Rule

- 不得编造 cite-key 对应的文献实体
- 不得把 `verification_status = unverifiable` 的条目当成高强度核心证据
- 不得为了一致性伪造 DOI、页码、卷期或作者

## Syntax

| 语法 | 用途 | 示例 |
|------|------|------|
| `[@cite-key]` | 引用文献 | `[@smith2024design]` |
| `[@key1, @key2]` | 同位置引用多篇 | `[@smith2024design, @jones2023impl]` |
| `{{fig:asset-id}}` | 引用图片 | `{{fig:arch-overview}}` |
| `{{tab:asset-id}}` | 引用表格 | `{{tab:use-cases}}` |
| `[[sec:chapter-id]]` | 章节交叉引用 | `[[sec:ch3]]` |
| `[TODO: 描述]` | 待补充内容 | `[TODO: 补充测试依据]` |

## Cite-Key Rule

建议格式：`第一作者姓氏小写 + 年份 + 首个实词小写`

示例：

- `smith2024design`
- `wang2023arch`
- `chen2022analysis`

约束：

- 全小写
- 不含空格
- 中文作者用拼音或稳定可复现的转写方式
- 同作者同年份用 `a`、`b`、`c` 后缀区分

## metadata.json Entry Shape

```json
{
  "id": "smith2024design",
  "source": "semantic-scholar",
  "type": "journal",
  "title": "Design and implementation of a web-based management system",
  "authors": ["John Smith", "Alice Wang"],
  "year": 2024,
  "venue": "International Journal of Software Engineering",
  "doi": "10.1234/ijse.2024.1.0123",
  "url": "https://doi.org/10.1234/ijse.2024.1.0123",
  "abstract": null,
  "language": "en",
  "verification_status": "verified"
}
```

关键字段：

- `id`: 草稿里 `[@key]` 使用的 cite-key
- `title` / `authors` / `year` / `type`: 被引用时的关键字段
- `language`: `zh` 或 `en`
- `verification_status`: 推荐值为 `verified` 或 `unverifiable`

## Validation Path

### Mid-draft

```bash
python scripts/literature_check_cite.py --draft drafts/01-introduction.md --strict
```

实际效果：

- cite-key 不存在时直接报错
- `--strict` 下，`unverifiable` 条目会被作为 warning 提示

### Preflight

`scripts/run_preflight.py` 会进一步检查：

- 不存在的 cite-key
- 被引用条目缺关键字段
- 高频引用 `unverifiable` 文献
- 高频引用但没有摘要也没有全文的文献
- DOI 格式异常

## Layout Behavior

`layout_generate_docx.py` 会：

1. 扫描所有草稿，按首次出现顺序为 cite-key 分配编号
2. 把正文中的 `[@key]` 转成 `[N]`
3. 在“参考文献”章节中按编号顺序输出条目

完整字段格式见 `references/citation-format.md`。

## Practical Guidance

- 研究现状章节优先引用已验证文献
- 同一段落不要重复引用同一篇文献
- 不要为凑引用量把不相关文献硬塞进段落
- 如果文献只有标题、没有摘要、没有全文，就不要让它承担关键论证
