#!/usr/bin/env python3
"""hello-skill 示例脚本：打印一句问候语。

用法：
    python scripts/hello.py --name 世界
"""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="打印一句问候语")
    parser.add_argument("--name", default="world", help="要问候的对象")
    args = parser.parse_args()
    print(f"Hello, {args.name}! 这是一个 SKILL.md 示例技能的脚本。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
