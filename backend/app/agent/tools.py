"""智能体工具：read_file / list_files / write_file / run_command（子进程受限）。"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from . import safety

# 读文件上限
READ_LIMIT = 8000
LIST_LIMIT = 200


class Workspace:
    """会话工作区：/workspace 可写，/skills/<slug> 只读引用。"""

    def __init__(self, workspace: Path, skills_root: Path, slug_dir: dict[str, Path], slug_bins: dict[str, list[str]] | None = None):
        self.workspace = workspace
        self.skills_root = skills_root
        self.slug_dir = slug_dir
        self.slug_bins = slug_bins or {}
        self.workspace.mkdir(parents=True, exist_ok=True)

    # ── 虚拟路径 → 真实路径 ──
    def resolve(self, path: str, *, write: bool = False) -> tuple[Path, Path]:
        """返回 (真实路径, cwd 用于运行)。"""
        p = Path(path)
        parts = p.parts
        if path.startswith("/"):
            if len(parts) >= 3 and parts[1] == "skills":
                slug = parts[2]
                real_dir = self.slug_dir.get(slug)
                if real_dir is None:
                    raise PermissionError(f"未知 skill：{slug}")
                rel = Path(*parts[3:])
                abs_path = safety.resolve_within(str(rel) if str(rel) else ".", [real_dir.resolve()], real_dir.resolve())
                return abs_path, real_dir.resolve()
            if parts[1] == "workspace":
                rel = Path(*parts[2:])
                abs_path = safety.resolve_within(str(rel) if str(rel) else ".", [self.workspace.resolve()], self.workspace.resolve())
                return abs_path, self.workspace.resolve()
            raise PermissionError(f"仅允许 /skills/<slug> 或 /workspace 绝对路径，收到：{path}")
        # 相对路径：落在工作区
        abs_path = safety.resolve_within(path, [self.workspace.resolve()], self.workspace.resolve())
        return abs_path, self.workspace.resolve()

    def _virtual(self, real: Path) -> str:
        """真实路径 → 虚拟路径（用于展示）。"""
        try:
            rel = real.relative_to(self.workspace)
            return "/workspace/" + rel.as_posix()
        except ValueError:
            for slug, d in self.slug_dir.items():
                try:
                    rel = real.relative_to(d)
                    return f"/skills/{slug}/" + rel.as_posix()
                except ValueError:
                    continue
        return str(real)

    # ── 工具实现 ──
    def list_files(self, path: str = "/workspace") -> str:
        real, _ = self.resolve(path)
        if not real.is_dir():
            return f"目录不存在：{path}"
        lines = []
        for p in sorted(real.iterdir()):
            if p.name.startswith("."):
                continue
            lines.append(self._virtual(p) + ("/" if p.is_dir() else ""))
            if len(lines) >= LIST_LIMIT:
                lines.append("…(更多)")
                break
        return "\n".join(lines) if lines else "(空目录)"

    def read_file(self, path: str) -> str:
        real, _ = self.resolve(path)
        if not real.is_file():
            return f"文件不存在：{path}"
        try:
            text = real.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"读取失败：{e}"
        if len(text) > READ_LIMIT:
            text = text[:READ_LIMIT] + "\n…[内容截断]"
        return text

    def write_file(self, path: str, content: str) -> str:
        real, _ = self.resolve(path, write=True)
        try:
            real.parent.mkdir(parents=True, exist_ok=True)
            real.write_text(content, encoding="utf-8")
        except Exception as e:
            return f"写入失败：{e}"
        return f"已写入 {self._virtual(real)}（{len(content)} 字符）"

    async def run_command(self, command: str, cwd: str = "/workspace") -> str:
        _, run_cwd = self.resolve(cwd)
        # 若在某个 skill 目录下执行，校验它声明的 requires.bins
        skill_slug = self._slug_of(run_cwd)
        if skill_slug:
            missing = [b for b in self.slug_bins.get(skill_slug, []) if not shutil.which(b)]
            if missing:
                return f"[依赖缺失] 技能 `{skill_slug}` 需要以下程序但当前环境没有：{', '.join(missing)}；请改用其它工具或安装后重试。"
        # 把命令里的虚拟路径 /skills/<slug> 替换为真实绝对路径，便于脚本直接运行
        for slug, real_dir in self.slug_dir.items():
            command = command.replace(f"/skills/{slug}", str(real_dir))
        command = command.replace("/workspace", str(self.workspace))
        return await asyncio.to_thread(safety.run_subprocess, command, run_cwd)

    def _slug_of(self, path: Path) -> str | None:
        for slug, d in self.slug_dir.items():
            try:
                path.resolve().relative_to(d.resolve())
                return slug
            except ValueError:
                continue
        return None


def workspace_for(user_id: int, conversation_id: str, skills_root: Path, index) -> Workspace:
    # 按用户分目录，避免不同用户的工作区产物互相可见
    base = Path(__file__).resolve().parent.parent.parent / ".workspaces"
    ws = base / str(user_id) / conversation_id
    slug_dir = {slug: info.dir for slug, info in index.items()}
    slug_bins = {slug: info.requires_bins for slug, info in index.items() if info.requires_bins}
    return Workspace(ws, skills_root, slug_dir, slug_bins)


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出目录内容（/workspace 或 /skills/<slug>）",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录虚拟路径，默认 /workspace"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件（SKILL.md / references / 脚本 / 工作区文件）",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件虚拟路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "在工作区写文本文件（结果/产物）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "/workspace/ 下路径"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在工作区（或指定 skill 目录）执行 shell 命令，运行脚本产出结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "cwd": {"type": "string", "description": "工作目录虚拟路径，默认 /workspace"},
                },
                "required": ["command"],
            },
        },
    },
]


TOOL_OUTPUT_INLINE_LIMIT = 4000  # 注入上下文的工具输出最大字符数，超出则卸载到工作区文件


def _offload_large_output(ws: Workspace, name: str, output: str) -> str:
    """过长工具输出不塞进模型上下文，而是写到工作区文件，只回传标记 + 前段预览。"""
    if len(output) <= TOOL_OUTPUT_INLINE_LIMIT:
        return output
    import hashlib
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()[:12]
    rel = Path("_tool_results") / f"{name}-{digest}.txt"
    target = ws.workspace / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output, encoding="utf-8")
    preview = output[:500]
    return (
        f"[工具输出过长（{len(output)} 字符）已截断：完整结果保存到 /workspace/{rel.as_posix()}]\n"
        f"前 500 字预览：{preview}" + ("…" if len(output) > 500 else "")
    )


async def execute_tool(name: str, args: dict, ws: Workspace) -> str:
    if name == "list_files":
        out = ws.list_files(args.get("path", "/workspace"))
    elif name == "read_file":
        out = ws.read_file(args["path"])
    elif name == "write_file":
        out = ws.write_file(args["path"], args.get("content", ""))
    elif name == "run_command":
        out = await ws.run_command(args["command"], args.get("cwd", "/workspace"))
    else:
        out = f"[未知工具] {name}"
    return _offload_large_output(ws, name, out)