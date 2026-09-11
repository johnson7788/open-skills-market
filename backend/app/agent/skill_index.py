"""启动时扫描 skills 目录，建立 slug → 元数据/依赖 索引，并提供依赖闭包展开。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


@dataclass
class SkillInfo:
    slug: str
    name: str
    description: str
    dir: Path
    dependencies: list[str] = field(default_factory=list)
    requires_bins: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)
    max_steps: int | None = None

    def files(self) -> list[str]:
        """相对 skill 目录的文件路径（相对路径，供 read_file/list_files 使用）。"""
        out = []
        for p in self.dir.rglob("*"):
            if p.is_file():
                out.append(p.relative_to(self.dir).as_posix())
        return sorted(out)


def _parse_frontmatter(content: str) -> dict:
    m = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def build_index(root: Path = SKILLS_ROOT) -> dict[str, SkillInfo]:
    index: dict[str, SkillInfo] = {}
    for md_path in sorted(root.rglob("SKILL.md")):
        content = md_path.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(content)
        meta = _read_json(md_path.parent / "_meta.json")

        slug = meta.get("slug") or fm.get("name") or md_path.parent.name
        name = meta.get("name") or fm.get("name") or slug
        description = meta.get("description") or fm.get("description") or ""

        # 依赖：_meta.json.dependencies 优先
        dependencies = meta.get("dependencies") or []

        # 运行要求：_meta.json.requires 优先，回退 SKILL.md metadata.openclaw.requires
        req = meta.get("requires") or {}
        bins = req.get("bins") or []
        env = req.get("env") or []
        oc = (fm.get("metadata") or {}).get("openclaw") or {}
        oc_req = oc.get("requires") or {}
        if not bins:
            bins = oc_req.get("bins") or []
        if not env:
            env = oc_req.get("env") or []

        # 单次对话最大执行步数（可选，覆盖全局默认）
        _ms = meta.get("max_steps")
        max_steps = _ms if isinstance(_ms, int) and _ms > 0 else None

        index[slug] = SkillInfo(
            slug=str(slug),
            name=str(name),
            description=str(description),
            dir=md_path.parent,
            dependencies=[str(d) for d in dependencies],
            requires_bins=[str(b) for b in bins],
            requires_env=[str(e) for e in env],
            max_steps=max_steps,
        )
    return index


def expand_dependencies(slug: str, index: dict[str, SkillInfo]) -> list[str]:
    """返回 [slug] + 其依赖闭包（先根后依赖、去重、环检测）。"""
    seen: set[str] = set()
    order: list[str] = []

    def dfs(s: str) -> None:
        if s in seen:
            return
        if s not in index:
            return
        seen.add(s)
        order.append(s)
        for d in index[s].dependencies:
            dfs(d)

    dfs(slug)
    return order