"""子进程与路径安全：危险命令黑名单、工作区边界校验。"""
from __future__ import annotations

import os
import shlex
from pathlib import Path

# 危险命令前缀/片段（交集命中即拒绝）
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "sudo",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "shutdown",
    "reboot",
    "chmod 777",
    "> /dev/sda",
    "curl http://169.254.169.254",  # 云元数据探测
]

OUTPUT_LIMIT = 102400  # 100KB
RUN_TIMEOUT = 30  # 秒


def is_dangerous(cmd: str) -> tuple[bool, str]:
    lowered = cmd.lower()
    for pat in DANGEROUS_PATTERNS:
        if pat in lowered:
            return True, pat
    return False, ""


def parse_cmd(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd)
    except ValueError:
        return ["/bin/sh", "-c", cmd]


def resolve_within(path: str, allowed_roots: list[Path], cwd: Path) -> Path:
    """把相对路径解析到 cwd 下；绝对路径需落在 allowed_roots 内，否则报错。"""
    p = Path(path)
    if not p.is_absolute():
        p = (cwd / p).resolve()
    else:
        p = p.resolve()
    # 必须落在某个 allowed root 内
    for root in allowed_roots:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise PermissionError(f"路径越界：{path} 不在允许范围内")


# 允许透传给 skill 脚本子进程的凭证/配置环境变量（白名单，其余 os.environ 不下发）。
# 需要给技能脚本额外下发变量时，用 SKILL_ENV_PASSTHROUGH 追加（逗号分隔）。
TOKEN_ENV_VARS = (
    "LLM_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY",
    "SKILLHUB_TOKEN", "SKILLHUB_URL",
)


def _passthrough_env_vars() -> list[str]:
    extra = os.getenv("SKILL_ENV_PASSTHROUGH", "")
    return [n.strip() for n in extra.split(",") if n.strip()]


def run_subprocess(cmd: str, cwd: Path, env: dict | None = None, network: bool = False) -> str:
    """在 cwd 下执行命令，返回裁剪后的 stdout+stderr。"""
    import subprocess

    ok, pat = is_dangerous(cmd)
    if ok:
        return f"[拒绝执行] 命令命中危险规则：{pat}"

    # 白名单环境：只保留必要项 + 显式允许的凭证变量（供 skill 脚本读取）
    base_env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(cwd)}
    for _name in (*TOKEN_ENV_VARS, *_passthrough_env_vars()):
        _val = os.environ.get(_name)
        if _val:
            base_env[_name] = _val
    if env:
        base_env.update(env)

    try:
        proc = subprocess.run(
            parse_cmd(cmd),
            cwd=str(cwd),
            env=base_env,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"[超时] 命令超过 {RUN_TIMEOUT}s 被终止"
    except FileNotFoundError as e:
        return f"[错误] 命令不存在：{e}"

    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > OUTPUT_LIMIT:
        out = out[:OUTPUT_LIMIT] + f"\n…[输出截断，共 {len(out)} 字节]"
    if not out:
        out = f"(退出码 {proc.returncode}，无输出)"
    return out