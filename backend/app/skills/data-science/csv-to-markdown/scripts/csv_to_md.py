#!/usr/bin/env python3
"""csv-to-markdown 脚本：CSV → Markdown 表格。

用法：
    python scripts/csv_to_md.py data.csv [--delimiter ,] [--output table.md]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _cell(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", " ").strip()


def to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, *body = rows
    lines = [
        "| " + " | ".join(_cell(c) for c in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV 转 Markdown 表格")
    parser.add_argument("path", help="CSV 文件路径")
    parser.add_argument("--delimiter", default=",", help="列分隔符（默认 ,）")
    parser.add_argument("--output", help="输出 Markdown 文件路径；不填则打印到 stdout")
    args = parser.parse_args()

    p = Path(args.path)
    if not p.is_file():
        print(f"文件不存在：{args.path}")
        return 1

    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=args.delimiter))

    markdown = to_markdown(rows)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        print(f"已写入 {out}（{len(rows)} 行）")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
