"""skill_index 单元测试：索引构建 + 依赖闭包。"""
from app.agent.skill_index import SKILLS_ROOT, SkillInfo, build_index, expand_dependencies


def test_index_builds_bundled_example_skills():
    index = build_index()
    assert len(index) >= 3, "应至少扫描到内置示例技能"
    assert "hello-skill" in index
    assert "text-stats" in index
    assert "csv-to-markdown" in index


def test_slug_and_fields_populated():
    index = build_index()
    info = index["hello-skill"]
    assert info.slug == "hello-skill"
    assert info.name
    assert info.description
    assert info.dir.is_dir()
    assert "SKILL.md" in info.files()


def test_dependency_closure_with_synthetic_index():
    a = SkillInfo(slug="a", name="A", description="", dir=SKILLS_ROOT, dependencies=["b"])
    b = SkillInfo(slug="b", name="B", description="", dir=SKILLS_ROOT, dependencies=["c"])
    c = SkillInfo(slug="c", name="C", description="", dir=SKILLS_ROOT)
    index = {"a": a, "b": b, "c": c}

    closure = expand_dependencies("a", index)
    assert closure == ["a", "b", "c"]


def test_expand_missing_slug_returns_empty():
    assert expand_dependencies("no-such-skill", {}) == []


def test_expand_cycle_safe():
    # 构造环：a -> b -> a
    a = SkillInfo(slug="a", name="A", description="", dir=SKILLS_ROOT, dependencies=["b"])
    b = SkillInfo(slug="b", name="B", description="", dir=SKILLS_ROOT, dependencies=["a"])
    index = {"a": a, "b": b}
    closure = expand_dependencies("a", index)
    assert closure == ["a", "b"]  # 环不重复、不卡死
