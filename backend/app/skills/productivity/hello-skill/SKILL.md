---
name: hello-skill
description: 最小可用示例技能，演示 SKILL.md 目录结构、frontmatter 字段与脚本调用方式。
keywords:
  - 示例
  - 入门
---

# hello-skill

这是一个最小可用示例技能，用来演示一个 skill 的标准目录结构：

```text
hello-skill/
├── SKILL.md          # 技能说明（本文件），frontmatter 提供 name/description/keywords
├── _meta.json        # 可选：slug / version / examples / dependencies / max_steps
└── scripts/          # 可执行脚本
    └── hello.py
```

## 使用方式

```bash
python scripts/hello.py --name 世界
```

## 何时使用

- 想快速了解一个 skill 应该长什么样
- 想把自己的一段脚本/流程封装成可被智能体调用的技能

## 输出

脚本会打印一句问候语，证明技能脚本可以在工作区沙箱里被正常执行。
