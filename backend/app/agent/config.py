"""模型与运行配置（环境变量驱动）。"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("DASHSCOPE_BASE_URL")
    or "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("BUDDY_DEFAULT_MODEL") or "qwen-plus"

# 单个会话最大执行步数（安全网，非业务流控）；AGENT_MAX_TURNS 为旧名，向后兼容
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS") or os.getenv("AGENT_MAX_TURNS") or "100")

# 上下文预算：超过该字符数触发历史压缩；压缩时保留最近 N 条消息
SUMMARY_TRIGGER_CHARS = int(os.getenv("SUMMARY_TRIGGER_CHARS", "60000"))
SUMMARY_KEEP_MESSAGES = int(os.getenv("SUMMARY_KEEP_MESSAGES", "8"))


def is_configured() -> bool:
    return bool(LLM_API_KEY)