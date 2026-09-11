#!/usr/bin/env python3
"""text-stats 脚本：统计文本文件的行数/字符数/词数与高频词。

用法：
    python scripts/text_stats.py input.txt [--top 10]
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

WORD_RE = re.compile(r"[A-Za-z0-9']+|[\u4e00-\u9fff]")


def main() -> int:
    parser = argparse.ArgumentParser(description="统计文本文件基础指标")
    parser.add_argument("path", help="待统计的文本文件路径")
    parser.add_argument("--top", type=int, default=10, help="输出高频词数量（默认 10）")
    args = parser.parse_args()

    p = Path(args.path)
    if not p.is_file():
        print(f"文件不存在：{args.path}")
        return 1

    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    words = WORD_RE.findall(text.lower())

    print(f"文件：{p}")
    print(f"行数：{len(lines)}")
    print(f"字符数：{len(text)}")
    print(f"词数：{len(words)}")

    if words and args.top > 0:
        print(f"\n高频词 Top {args.top}：")
        for word, count in Counter(words).most_common(args.top):
            print(f"  {word}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
