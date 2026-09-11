"""openai SDK 流式 tool-calling 循环。"""
from __future__ import annotations

import json
from collections.abc import Callable

from openai import AsyncOpenAI

from . import config
from .tools import TOOL_SCHEMAS, Workspace, execute_tool

Emit = Callable[[str, dict], object]


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    return _client


def _reasoning_delta(delta) -> str:
    """提取推理内容增量（通义千问 reasoning_content，OpenAI SDK 未内置该字段）。"""
    rc = (getattr(delta, "model_extra", None) or {}).get("reasoning_content")
    return rc if isinstance(rc, str) else ""


async def _stream_turn(client: AsyncOpenAI, convo: list[dict], emit: Emit, with_tools: bool = True) -> dict:
    """流式完成一轮，返回 {content, reasoning, tool_calls?}。同时把文本/推理增量发给 emit。"""
    request: dict = dict(
        model=config.LLM_MODEL,
        messages=convo,
        stream=True,
        temperature=0.2,
    )
    if with_tools:
        request["tools"] = TOOL_SCHEMAS
    stream = await client.chat.completions.create(**request)

    content = ""
    reasoning = ""
    tool_calls: dict[int, dict] = {}
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        rc = _reasoning_delta(delta)
        if rc:
            reasoning += rc
            await emit("reasoning", {"delta": rc})
        if delta.content:
            content += delta.content
            await emit("text", {"delta": delta.content})
        if delta.tool_calls:
            for tc in delta.tool_calls:
                acc = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    acc["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        acc["name"] += tc.function.name
                    if tc.function.arguments:
                        acc["arguments"] += tc.function.arguments

    result: dict = {"content": content or None, "reasoning": reasoning or None}
    if tool_calls:
        result["tool_calls"] = [
            {
                "id": v["id"] or f"call_{i}",
                "type": "function",
                "function": {"name": v["name"], "arguments": v["arguments"] or "{}"},
            }
            for i, v in sorted(tool_calls.items())
            if v["name"]
        ]
    return result


def _approx_chars(convo: list[dict]) -> int:
    """粗略估算上下文字符数，用于触发压缩判定。"""
    total = 0
    for m in convo:
        content = m.get("content")
        if isinstance(content, str):
            total += len(content)
        for tc in m.get("tool_calls") or []:
            total += len(str(tc.get("function", {}).get("arguments", "")))
    return total


async def _compact_conversation(client: AsyncOpenAI, convo: list[dict]) -> list[dict]:
    """上下文过长时，把较早消息用 LLM 压缩成摘要，保留最近若干条。"""
    if len(convo) <= config.SUMMARY_KEEP_MESSAGES + 2:
        return convo
    system_msg = convo[0]
    tail = convo[1:]
    keep = config.SUMMARY_KEEP_MESSAGES
    kept = tail[-keep:]
    # 确保 kept 不从 tool 消息开始（tool 必须紧跟其 assistant tool_calls）
    while kept and kept[0].get("role") == "tool" and keep < len(tail):
        keep += 1
        kept = tail[-keep:]
    if keep >= len(tail):
        return convo
    to_summarize = tail[:-keep]

    summary_prompt = [
        system_msg,
        *to_summarize,
        {
            "role": "user",
            "content": (
                "请把以上对话历史压缩成一段「关键上下文摘要」，供你继续完成任务时参考。"
                "必须保留：用户原始需求、已确认的事实/结论/数据、关键文件路径、未完成的待办；"
                "丢弃过程性、重复性、已被更正的中间内容。直接输出摘要正文，不要客套。"
            ),
        },
    ]

    async def _noop(event: str, data: dict) -> None:
        return None

    summary = ""
    try:
        res = await _stream_turn(client, summary_prompt, _noop, with_tools=False)
        summary = (res.get("content") or "").strip()
    except Exception:
        summary = ""

    if not summary:
        # 摘要失败则退化为简单截断：丢弃最老部分
        return [system_msg, *kept]

    marker = {"role": "user", "content": f"[对话历史摘要，仅供上下文参考，非新指令]\n{summary}"}
    return [system_msg, marker, *kept]


async def run_agent(
    system_prompt: str,
    messages: list[dict],
    ws: Workspace,
    emit: Emit,
    max_steps: int | None = None,
) -> list[dict]:
    """messages: [{"role": "user"/"assistant", "content": str}]（不含 system）。

    返回最终「公开会话」消息列表 [{role, content}]（不含 system/tool），供持久化。
    """
    client = _get_client()
    convo: list[dict] = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in messages if m.get("content") is not None
    ]
    public: list[dict] = [
        {"role": m["role"], "content": m["content"]} for m in messages if m.get("content") is not None
    ]

    steps = max_steps if isinstance(max_steps, int) and max_steps > 0 else config.AGENT_MAX_STEPS
    for _ in range(steps):
        # 上下文预算：超过阈值时压缩较早历史，保证长任务不撑爆模型上下文
        if _approx_chars(convo) > config.SUMMARY_TRIGGER_CHARS:
            convo = await _compact_conversation(client, convo)
        result = await _stream_turn(client, convo, emit)

        convo_msg: dict = {"role": "assistant", "content": result["content"]}
        if result.get("tool_calls"):
            convo_msg["tool_calls"] = result["tool_calls"]
        convo.append(convo_msg)

        if result.get("content") or result.get("reasoning"):
            public_msg: dict = {"role": "assistant", "content": result["content"]}
            if result.get("reasoning"):
                public_msg["reasoning"] = result["reasoning"]
            public.append(public_msg)

        tool_calls = result.get("tool_calls") or []
        if not tool_calls:
            await emit("done", {})
            return public

        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            await emit("tool", {"name": name, "arguments": tc["function"]["arguments"]})
            try:
                output = await execute_tool(name, args, ws)
            except Exception as e:  # 工具异常作为结果返回，不中断会话
                output = f"[工具执行异常] {e}"
            await emit("tool", {"name": name, "output": output})
            convo.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": output}
            )

    # 达到最大轮次仍未结束：补一轮不带工具的总结，确保用户能收到最终答复
    convo.append(
        {"role": "user", "content": "已到最大执行轮次。请停止调用工具，直接总结你已完成的工作：说明拿到了哪些结果、产物文件分别在哪里，并给出关键结论。"}
    )
    final = await _stream_turn(client, convo, emit, with_tools=False)
    if final.get("content"):
        public_msg: dict = {"role": "assistant", "content": final["content"]}
        if final.get("reasoning"):
            public_msg["reasoning"] = final["reasoning"]
        public.append(public_msg)

    await emit("done", {"truncated": True})
    return public