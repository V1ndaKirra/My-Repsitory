# Format Spec

`template/format-contract.json` 是论文模板契约文件，但当前 `layout_generate_docx.py` 只真正消费其中一部分字段。这个文档的重点是把“已经生效的字段”和“当前只是约定/预留的字段”分开写清楚。

## Current Reality

不要再把它描述成“排版脚本的唯一格式配置源”。当前情况更准确地说是：

- `run_preflight.py` 会把 `status == "confirmed"` 当作模板契约已确认的前置条件
- `layout_generate_docx.py` 会读取部分分页与目录字段
- 字体、标题样式、参考文献字号等大量格式仍写死在脚本里

## Fields Consumed Today

下表是当前脚本已经核对过、确实会读取的字段：

| 字段 | 消费位置 | 说明 |
|------|----------|------|
| `status` | `run_preflight.py` | 不是排版脚本读，而是预检时要求为 `confirmed` |
| `page.margins_cm.*` | `layout_generate_docx.py` | 设置页面边距 |
| `page.header_distance_cm` | `layout_generate_docx.py` | 设置页眉距顶端 |
| `page.footer_distance_cm` | `layout_generate_docx.py` | 设置页脚距底端 |
| `page.binding_offset_cm` | `layout_generate_docx.py` | 设置装订线偏移 |
| `front_matter.toc.levels` | `layout_generate_docx.py` | 控制 TOC 级数 |
| `header_footer.body_footer_pattern` | `layout_generate_docx.py` | 正文页脚文本模板 |

## Fields Stored As Contract Targets

这些字段今天可以保留在 `format-contract.json` 里，作为学校模板契约或后续开发目标，但不要在文档里写成“修改后立刻会影响排版”：

- `fonts.*`
- `paragraph.*`
- `headings.numbering`
- `headings.*_alignment`
- `front_matter.cover.fields`
- `front_matter.abstract_zh.enabled`
- `front_matter.abstract_en.enabled`
- `body_order`
- `references.style`
- `page_numbers.*`
- `header_footer.front_matter`
- `header_footer.different_odd_even`

## Recommended Structure

```json
{
  "status": "confirmed",
  "source_template": "template/original.docx",
  "parsed_at": "2026-05-26T09:00:00+00:00",
  "page": {
    "size": "A4",
    "orientation": "portrait",
    "margins_cm": {
      "top": 2.5,
      "right": 2.5,
      "bottom": 2.5,
      "left": 2.5
    },
    "header_distance_cm": 1.5,
    "footer_distance_cm": 1.75,
    "binding_offset_cm": 0.0
  },
  "front_matter": {
    "toc": {
      "enabled": true,
      "levels": 3
    }
  },
  "header_footer": {
    "body_footer_pattern": "第 {PAGE} 页 共 {NUMPAGES} 页"
  }
}
```

## Notes For Future Alignment

如果你后续想让 `format-contract.json` 真正成为唯一配置源，优先把这些硬编码抽出去：

1. 正文与标题字体
2. 题注字号
3. 前导部分页码格式
4. 参考文献字号与缩进
5. 封面字段布局

在这些字段尚未抽离前，文档必须诚实地写成“当前部分生效，部分只是契约目标”。
