"""工具与安全单元测试：路径边界、读写、子进程受限。"""
import asyncio

import pytest

from app.agent.tools import Workspace


@pytest.fixture()
def ws(tmp_path):
    skills = tmp_path / "skills"
    (skills / "foo").mkdir(parents=True)
    (skills / "foo" / "SKILL.md").write_text("# foo\n", encoding="utf-8")
    workspace = tmp_path / "ws"
    return Workspace(workspace, skills, {"foo": skills / "foo"})


def test_read_skill_file(ws):
    out = ws.read_file("/skills/foo/SKILL.md")
    assert "# foo" in out


def test_write_and_read_workspace(ws):
    assert "已写入" in ws.write_file("/workspace/out.txt", "hello")
    assert ws.read_file("/workspace/out.txt") == "hello"


def test_path_traversal_rejected(ws):
    with pytest.raises(PermissionError):
        ws.resolve("/etc/passwd")
    with pytest.raises(PermissionError):
        ws.resolve("/skills/foo/../../etc/passwd")


def test_list_files(ws):
    out = ws.list_files("/skills/foo")
    assert "SKILL.md" in out


def test_run_command_executes(ws):
    out = asyncio.run(ws.run_command("echo hello"))
    assert "hello" in out


def test_run_command_dangerous_rejected(ws):
    out = asyncio.run(ws.run_command("rm -rf /"))
    assert "拒绝执行" in out


def test_run_command_missing_bin_reported(tmp_path):
    skills = tmp_path / "skills"
    (skills / "bar").mkdir(parents=True)
    ws = Workspace(
        tmp_path / "ws2",
        skills,
        {"bar": skills / "bar"},
        {"bar": ["definitely-not-a-real-bin-xyz"]},
    )
    out = asyncio.run(ws.run_command("echo x", cwd="/skills/bar"))
    assert "依赖缺失" in out
    assert "definitely-not-a-real-bin-xyz" in out