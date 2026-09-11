"""对话路由：POST /api/chat（SSE 流式）+ 历史/会话列表/产物读取（按登录用户隔离）。"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..agent import config
from ..agent.agent_loop import run_agent
from ..agent.chat import manager
from ..agent.prompt import build_system_prompt
from ..agent.skill_index import SKILLS_ROOT, build_index
from ..agent.tools import workspace_for
from ..auth import get_current_user

router = APIRouter(prefix="/api", tags=["chat"])

_index_cache: dict = {}

# 正在运行的对话任务："{user_id}:{cid}" -> asyncio.Task（供「停止」取消）
_running_tasks: dict[str, asyncio.Task] = {}


def get_index() -> dict:
    if not _index_cache:
        _index_cache["index"] = build_index(SKILLS_ROOT)
    return _index_cache["index"]


def _task_key(user_id: int, cid: str) -> str:
    return f"{user_id}:{cid}"


def _resolve_cid(conversation_id: str | None) -> str:
    return conversation_id or uuid.uuid4().hex


def _workspace_dir(user_id: int, cid: str) -> Path:
    base = Path(__file__).resolve().parent.parent.parent / ".workspaces"
    return base / str(user_id) / cid


def _title_of(messages: list[dict]) -> str | None:
    """用第一条用户消息生成会话标题。"""
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            text = " ".join(str(m["content"]).split())
            return text[:40] + ("…" if len(text) > 40 else "")
    return None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    slug: str | None = None
    conversation_id: str | None = None
    messages: list[ChatMessage] = []


@router.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    user_id: int = user["id"]
    index = get_index()

    # 聚焦 skill：预注入其 SKILL.md 全文；依赖闭包由 prompt 层展开
    focused = index.get(req.slug) if req.slug else None
    focused_text = None
    if focused and (focused.dir / "SKILL.md").exists():
        focused_text = (focused.dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")

    system_prompt = build_system_prompt(index, focused, focused_text)

    # 单次对话最大执行步数：聚焦 skill 的 _meta.json.max_steps 优先，否则全局默认
    max_steps = focused.max_steps if (focused and focused.max_steps) else config.AGENT_MAX_STEPS

    # 前端每次发送完整历史（含最新 user 消息）
    history = [
        {"role": m.role if m.role in ("user", "assistant") else "user", "content": m.content}
        for m in req.messages
    ]

    cid = _resolve_cid(req.conversation_id)
    slug = req.slug or ""
    title = _title_of(history)
    ws = workspace_for(user_id, cid, SKILLS_ROOT, index)

    async def event_stream():
        q: asyncio.Queue = asyncio.Queue()

        async def emit(event: str, data: dict) -> None:
            await q.put((event, data))

        if not config.is_configured():
            msg = "未配置 LLM_API_KEY（或 DASHSCOPE_API_KEY）"
            yield f"event: error\ndata: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n"
            return

        async def runner() -> None:
            try:
                public = await run_agent(system_prompt, history, ws, emit, max_steps=max_steps)
                manager.save(user_id, cid, slug, title, public)
            except asyncio.CancelledError:
                pass  # 被停止：不保存、不报错，finally 统一收尾
            except Exception as e:  # noqa: BLE001
                await q.put(("error", {"message": str(e)}))
            finally:
                await q.put(("__end__", {}))

        task = asyncio.create_task(runner())
        _running_tasks[_task_key(user_id, cid)] = task
        try:
            while True:
                event, data = await q.get()
                if event == "__end__":
                    break
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            # 客户端断开或流结束后，回收/取消后台任务，避免悬挂任务泄漏
            _running_tasks.pop(_task_key(user_id, cid), None)
            if not task.done():
                task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001
                pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chat/stop")
async def stop_chat(
    slug: str = "",
    conversation_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> dict:
    """停止某个会话正在进行的流式回复。"""
    cid = _resolve_cid(conversation_id)
    task = _running_tasks.get(_task_key(user["id"], cid))
    if task and not task.done():
        task.cancel()
        return {"stopped": True}
    return {"stopped": False}


@router.get("/chat/history")
def chat_history(
    slug: str = "",
    conversation_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> dict:
    cid = _resolve_cid(conversation_id)
    return {"messages": manager.get(user["id"], cid)}


@router.get("/chat/conversations")
def chat_conversations(
    slug: str = "",
    user: dict = Depends(get_current_user),
) -> dict:
    """当前用户的会话列表（可按 slug 过滤，最近更新在前）。"""
    items = manager.list(user["id"], slug or None)
    return {"items": items}


@router.get("/chat/artifacts")
def chat_artifacts(
    slug: str = "",
    conversation_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> dict:
    cid = _resolve_cid(conversation_id)
    ws_dir = _workspace_dir(user["id"], cid)
    files = []
    if ws_dir.exists():
        for p in sorted(ws_dir.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                st = p.stat()
                files.append({
                    "path": p.relative_to(ws_dir).as_posix(),
                    "size": st.st_size,
                    "mtime": int(st.st_mtime),
                })
    return {"files": files}


@router.get("/chat/artifact")
def chat_artifact(
    slug: str = "",
    path: str = "",
    conversation_id: str | None = None,
    user: dict = Depends(get_current_user),
):
    cid = _resolve_cid(conversation_id)
    ws_dir = _workspace_dir(user["id"], cid).resolve()
    target = (ws_dir / path).resolve()
    if not str(target).startswith(str(ws_dir) + "/") and target != ws_dir:
        raise HTTPException(status_code=400, detail="非法路径")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(target, filename=target.name)
