---
name: csv-to-markdown
description: 把 CSV 文件转换成 Markdown 表格，支持分隔符与编码参数，零第三方依赖。
keywords:
  - CSV
  - Markdown
---

# csv-to-markdown

把 CSV 文件转换成 Markdown 表格，便于直接粘贴进 Markdown 文档或对话回复。

## 用法

```bash
python scripts/csv_to_md.py /workspace/data.csv
python scripts/csv_to_md.py /workspace/data.csv --delimiter ";" --output /workspace/table.md
```

## 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `path` | CSV 文件路径 | 必填 |
| `--delimiter` | 列分隔符 | `,` |
| `--output` | 输出 Markdown 文件；不填则打印到 stdout | 无 |

## 输出

标准 Markdown 表格；单元格内的 `|` 会被转义，空值显示为空字符串。

## 何时使用

- 需要把表格数据贴进 Markdown 文档或聊天回复
- 想快速预览一个 CSV 的结构与内容
