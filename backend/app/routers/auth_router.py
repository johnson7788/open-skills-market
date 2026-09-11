"""鉴权路由：登录 / 当前用户 / 退出。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import auth, bearer_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str


def _validate_username(username: str) -> str:
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(username) > 32:
        raise HTTPException(status_code=400, detail="用户名过长（最多 32 字符）")
    return username


@router.post("/login")
def login(req: LoginRequest) -> dict:
    username = _validate_username(req.username)
    user = auth.get_or_create_user(username)
    return {
        "token": user["token"],
        "user": {"id": user["id"], "username": user["username"]},
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": {"id": user["id"], "username": user["username"]}}


@router.post("/logout")
def logout(
    user: dict = Depends(get_current_user),
    raw: str | None = Depends(bearer_token),
) -> dict:
    if raw:
        auth.delete_session(raw)
    return {"ok": True}
