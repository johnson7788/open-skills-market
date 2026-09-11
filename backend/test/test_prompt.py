"""prompt 拼装单元测试。"""
from app.agent.prompt import build_system_prompt, dependencies_section
from app.agent.skill_index import SKILLS_ROOT, SkillInfo, build_index


def test_system_prompt_contains_skill_list_and_rules():
    index = build_index()
    sp = build_system_prompt(index, None, None)
    assert "可用 skills" in sp
    assert "使用规则" in sp
    # 内置示例技能应出现在技能清单里
    assert "hello-skill" in sp


def test_focused_skill_full_text_injected():
    index = build_index()
    focused = index["hello-skill"]
    sp = build_system_prompt(index, focused, "FAKE_SKILL_BODY_XYZ")
    assert "当前聚焦技能" in sp
    assert "FAKE_SKILL_BODY_XYZ" in sp


def test_dependencies_section_lists_closure():
    # 用合成索引测依赖闭包渲染，避免依赖具体技能的 _meta.json
    a = SkillInfo(slug="skill-a", name="A", description="", dir=SKILLS_ROOT, dependencies=["skill-b"])
    b = SkillInfo(slug="skill-b", name="B", description="B 的描述", dir=SKILLS_ROOT)
    index = {"skill-a": a, "skill-b": b}

    section = dependencies_section("skill-a", index)
    assert "关联/依赖技能" in section
    assert "`skill-b`" in section
    assert "B 的描述" in section


def test_dependencies_section_empty_without_deps():
    solo = SkillInfo(slug="solo", name="Solo", description="", dir=SKILLS_ROOT)
    assert dependencies_section("solo", {"solo": solo}) == ""
