"""system prompt 拼装：全量 skill 列表 + 聚焦 skill 全文 + 使用规则。"""
from __future__ import annotations

from .skill_index import SkillInfo, expand_dependencies

MAX_LIST_ITEMS = 200


def skill_list_section(index: dict[str, SkillInfo]) -> str:
    lines = ["## 可用 skills（通过读取对应 SKILL.md 即可使用）"]
    for info in list(index.values())[:MAX_LIST_ITEMS]:
        desc = (info.description or "").replace("\n", " ").strip()
        lines.append(f"- **{info.name}** (`{info.slug}`)：{desc if desc else '（无描述）'}")
    if len(index) > MAX_LIST_ITEMS:
        lines.append(f"- …（其余 {len(index) - MAX_LIST_ITEMS} 个请在需要时用 list_files 查看 /skills 目录）")
    return "\n".join(lines)


def usage_rules() -> str:
    return (
        "## 使用规则\n"
        "- 每个 skill 是一个目录，SKILL.md 是其核心说明，references/ 是参考，scripts/ 是可执行脚本。\n"
        "- 需要某个 skill 时：先用 `read_file` 读 `/skills/<slug>/SKILL.md`，必要时读 references。\n"
        "- 需要真正执行时：用 `run_command` 在工作区运行脚本；产物用 `write_file` 写到 `/workspace/`。\n"
        "- 先读说明，再动手；不确定时就 `list_files` 查看目录结构。\n"
        "- 回答用中文，给出关键步骤与结果。"
    )


def focused_section(info: SkillInfo | None, full_text: str | None) -> str:
    if not info or not full_text:
        return ""
    header = f"## 当前聚焦技能：{info.name}（{info.slug}）\n"
    header += "下面是该技能的 SKILL.md 全文，优先基于它回答用户：\n\n"
    return header + full_text


def dependencies_section(slug: str, index: dict[str, SkillInfo]) -> str:
    """聚焦 skill 的依赖闭包（不含自身），标注为可选用的关联技能。"""
    closure = expand_dependencies(slug, index)[1:]
    if not closure:
        return ""
    lines = ["## 关联/依赖技能（当前技能依赖它们，可按需读取）"]
    for s in closure:
        info = index[s]
        desc = (info.description or "").replace("\n", " ").strip()
        lines.append(f"- **{info.name}** (`{s}`)：{desc if desc else '（无描述）'}")
    return "\n".join(lines)


def build_system_prompt(
    index: dict[str, SkillInfo],
    focused: SkillInfo | None = None,
    focused_text: str | None = None,
) -> str:
    parts = [
        "你是 Skill Market 的智能助手，擅长调用已挂载的 skills 完成用户交给你的任务。",
        skill_list_section(index),
        usage_rules(),
    ]
    fs = focused_section(focused, focused_text)
    if fs:
        parts.append(fs)
    if focused:
        ds = dependencies_section(focused.slug, index)
        if ds:
            parts.append(ds)
    return "\n\n".join(parts)