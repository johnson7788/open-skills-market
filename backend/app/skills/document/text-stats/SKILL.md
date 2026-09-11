---
name: text-stats
description: 统计文本文件的行数、字符数、词数与高频词，零第三方依赖。
keywords:
  - 文本
  - 统计
---

# text-stats

对纯文本文件做基础统计，输出行数、字符数、词数以及出现频率最高的若干词。

## 用法

```bash
python scripts/text_stats.py /workspace/input.txt
python scripts/text_stats.py /workspace/input.txt --top 20
```

## 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `path` | 待统计的文本文件路径 | 必填 |
| `--top` | 输出高频词的数量 | `10` |

## 输出

人类可读的统计结果。词统计按空白切分，忽略大小写。

## 何时使用

- 快速了解一份文档的规模与主题分布
- 处理日志、语料前的预处理检查
