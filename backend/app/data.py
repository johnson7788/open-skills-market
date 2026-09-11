"""市场目录：扫描 `app/skills/` 下的 SKILL.md，生成技能列表与分类。"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel

_SKILLS_ROOT = Path(__file__).parent / "skills"


class Skill(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    tags: list[str]
    usage_count: int
    icon: str
    category_id: str
    category_name: str
    is_used: bool
    examples: list[str] = []


class Category(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    order: int


def _load_categories() -> dict[str, Category]:
    path = _SKILLS_ROOT / "categories.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        c["id"]: Category(
            id=c["id"],
            name=c["name"],
            icon=c.get("icon", "📦"),
            description=c.get("description", ""),
            order=c.get("order", 99),
        )
        for c in data["categories"]
    }


def _parse_frontmatter(content: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def _usage_count(slug: str) -> int:
    """确定性伪随机使用次数：同一个 slug 永远得到同一个值（演示用）。

    用 md5 而不是内置 hash()，因为 str 的 hash 带随机盐、跨进程不稳定。
    """
    digest = hashlib.md5(slug.encode("utf-8")).hexdigest()
    return 800 + (int(digest[:8], 16) % 2800)


def _load_skills(categories: dict[str, Category]) -> list[Skill]:
    skills_root_path = _SKILLS_ROOT
    raw_cats_path = skills_root_path / "categories.json"
    with open(raw_cats_path, encoding="utf-8") as f:
        raw_cats = json.load(f)["categories"]

    # 目录名 -> 分类 id（分类可用 path 字段自定义目录名）
    dir_to_cat: dict[str, str] = {}
    for c in raw_cats:
        dir_to_cat[c.get("path", c["id"])] = c["id"]

    def _order(cat_dir: str) -> int:
        cat = categories.get(dir_to_cat.get(cat_dir, cat_dir))
        return cat.order if cat else 99

    # 按分类 order 排序目录，保证技能 id 稳定
    sorted_dirs = sorted(
        (d for d in os.listdir(skills_root_path) if os.path.isdir(skills_root_path / d)),
        key=_order,
    )

    skills: list[Skill] = []
    idx = 0

    for cat_dir in sorted_dirs:
        cat_id = dir_to_cat.get(cat_dir, cat_dir)
        cat = categories.get(cat_id)
        if cat is None:
            continue
        cat_path = skills_root_path / cat_dir

        # 远程技能目录是两层（_remote/<namespace>/<slug>），普通分类是一层
        if cat_dir == "_remote":
            skill_dirs = sorted(
                {md.parent for md in cat_path.rglob("SKILL.md")},
                key=lambda p: p.as_posix(),
            )
        else:
            skill_dirs = [cat_path / d for d in sorted(os.listdir(cat_path))]

        for skill_path in skill_dirs:
            if not skill_path.is_dir():
                continue
            skill_md = skill_path / "SKILL.md"
            meta_json = skill_path / "_meta.json"
            if not skill_md.exists():
                continue

            with open(skill_md, encoding="utf-8") as f:
                content = f.read()
            fm = _parse_frontmatter(content)

            meta: dict = {}
            if meta_json.exists():
                with open(meta_json, encoding="utf-8") as f:
                    meta = json.load(f)

            # 技能可用 _meta.json 的 category_id 覆盖所在目录的分类
            if meta.get("category_id") in categories:
                cat_id = meta["category_id"]
                cat = categories[cat_id]

            slug = meta.get("slug") or fm.get("name") or skill_path.name

            # 示例问题（供前端「试用」入口展示，最多 3 条）
            examples = [str(e).strip() for e in (meta.get("examples") or []) if str(e).strip()][:3]

            # Display name: prefer metadata.short-description, then fm.name, then slug
            fm_meta = fm.get("metadata") or {}
            if isinstance(fm_meta, dict):
                short_desc = fm_meta.get("short-description") or ""
            else:
                short_desc = ""
            display_name = short_desc or fm.get("name") or slug

            # Build tags from keywords field or fallback to category name
            raw_keywords = fm.get("keywords") or []
            if isinstance(raw_keywords, list):
                tags = [str(k) for k in raw_keywords[:2]]
            else:
                tags = [str(raw_keywords)][:2]
            if len(tags) < 2:
                tags.append(cat.name)
            if len(tags) < 2:
                tags.append(slug)

            idx += 1
            skills.append(
                Skill(
                    id=idx,
                    slug=slug,
                    name=display_name,
                    description=str(fm.get("description") or "")[:120],
                    tags=tags[:2],
                    usage_count=_usage_count(slug),
                    icon=cat.icon,
                    category_id=cat_id,
                    category_name=cat.name,
                    is_used=False,
                    examples=examples,
                )
            )

    return skills


_CATEGORIES = _load_categories()
SKILLS = _load_skills(_CATEGORIES)


def _tab_counts(used_slugs: set[str] | None = None) -> dict[str, int]:
    used_slugs = used_slugs or set()
    return {
        "all": len(SKILLS),
        "used": sum(1 for s in SKILLS if s.slug in used_slugs),
    }


def store_payload(search: str = "", tab: str = "all", category: str = "",
                  used_slugs: set[str] | None = None) -> dict:
    used_slugs = used_slugs or set()
    items = SKILLS[:]

    if tab == "used":
        items = [s for s in items if s.slug in used_slugs]

    if category:
        items = [s for s in items if s.category_id == category]

    if search:
        needle = search.lower()
        items = [
            s for s in items
            if needle in s.name.lower()
            or needle in s.slug.lower()
            or needle in s.description.lower()
            or any(needle in t.lower() for t in s.tags)
            or needle in s.category_name.lower()
        ]

    # 返回时按当前用户标记 is_used（不改模块级 SKILLS，避免并发状态串味）
    def _dump(s: Skill) -> dict:
        d = s.model_dump()
        d["is_used"] = s.slug in used_slugs
        return d

    return {
        "items": [_dump(s) for s in items],
        "total": len(items),
        "tabs": _tab_counts(used_slugs),
        "categories": list_categories(),
    }


def list_categories() -> list[dict]:
    """按 order 返回全部可用分类（供市场与前端侧边栏使用）。"""
    return [
        {"id": c.id, "name": c.name, "icon": c.icon, "description": c.description}
        for c in sorted(_CATEGORIES.values(), key=lambda x: x.order)
    ]


def get_skill_by_slug(slug: str) -> Skill | None:
    for s in SKILLS:
        if s.slug == slug:
            return s
    return None
