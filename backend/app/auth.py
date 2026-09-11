"""轻量身份：用户名登录（无密码）+ 服务端 session token。

说明：
- 本项目采用「仅用户名」的轻量登录，不做密码校验，适合本地/内网演示；
- 登录即返回一个不透明 token（存 sessions 表），后续请求用 Authorization: Bearer 携带；
  产物图片等无法带 header 的场景，允许用 ?token= 查询参数兜底。
- 会话存储（chat.db）与这里共用同一个 SQLite 文件，但表互相独立。
"""
from __future__ import annotations

import secrets
import sqlite3
import threading
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chat.db"

_bearer = HTTPBearer(auto_error=False)


class AuthManager:
    def __init__(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS users "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, "
                "created_at TEXT NOT NULL)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS sessions "
                "(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL)"
            )

    def get_or_create_user(self, username: str) -> dict:
        """按用户名查找，不存在则创建，并签发一个新的 session token。"""
        username = username.strip()
        with self._lock, self._conn() as c:
            row = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if row is None:
                cur = c.execute(
                    "INSERT INTO users(username, created_at) VALUES(?, datetime('now'))",
                    (username,),
                )
                uid = cur.lastrowid
            else:
                uid = row["id"]

            token = secrets.token_hex(32)
            c.execute(
                "INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,datetime('now'))",
                (token, uid),
            )
        return {"id": uid, "username": username, "token": token}

    def user_for_token(self, token: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT u.id, u.username FROM sessions s "
                "JOIN users u ON u.id = s.user_id WHERE s.token=?",
                (token,),
            ).fetchone()
        return {"id": row["id"], "username": row["username"]} if row else None

    def delete_session(self, token: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))


auth = AuthManager()


def bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    token: str | None = None,
) -> str | None:
    """优先取 Authorization 头，否则取 ?token= 查询参数（供图片/文件链接使用）。"""
    if credentials is not None:
        return credentials.credentials
    return token


def get_current_user(raw: str | None = Depends(bearer_token)) -> dict:
    if not raw:
        raise HTTPException(status_code=401, detail="未登录")
    user = auth.user_for_token(raw)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


def get_optional_user(raw: str | None = Depends(bearer_token)) -> dict | None:
    """可选鉴权：带有效 token 返回用户，否则返回 None（匿名）。"""
    if not raw:
        return None
    return auth.user_for_token(raw)
