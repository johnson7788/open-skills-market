"""会话存储：SQLite 持久化，按 (user_id, conversation_id) 隔离。

每个用户只看到自己的会话；conversation_id 由前端生成（UUID），
服务端用 (user_id, cid) 联合唯一，绝不信任裸 cid 做跨用户隔离。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "chat.db"


class ConversationManager:
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
            cols = [r["name"] for r in c.execute("PRAGMA table_info(conversations)").fetchall()]
            if cols and "user_id" not in cols:
                # 旧表只有 cid/data/updated_at，没有用户维度，无法归属；改名保留，不丢数据
                c.execute("ALTER TABLE conversations RENAME TO conversations_legacy")
                cols = []
            if not cols:
                c.execute(
                    "CREATE TABLE conversations ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "user_id INTEGER NOT NULL,"
                    "cid TEXT NOT NULL,"
                    "slug TEXT NOT NULL,"
                    "title TEXT,"
                    "data TEXT NOT NULL,"
                    "updated_at TEXT NOT NULL,"
                    "created_at TEXT NOT NULL,"
                    "UNIQUE(user_id, cid)"
                    ")"
                )
                c.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")

    def get(self, user_id: int, cid: str) -> list[dict]:
        with self._conn() as c:
            row = c.execute(
                "SELECT data FROM conversations WHERE user_id=? AND cid=?",
                (user_id, cid),
            ).fetchone()
        return json.loads(row["data"]) if row else []

    def save(
        self,
        user_id: int,
        cid: str,
        slug: str,
        title: str | None,
        messages: list[dict],
    ) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO conversations"
                "(user_id, cid, slug, title, data, updated_at, created_at) "
                "VALUES(?,?,?,?,?,datetime('now'),datetime('now')) "
                "ON CONFLICT(user_id, cid) DO UPDATE SET "
                "slug=excluded.slug, "
                "title=COALESCE(excluded.title, conversations.title), "
                "data=excluded.data, updated_at=datetime('now')",
                (user_id, cid, slug, title, json.dumps(messages, ensure_ascii=False)),
            )

    def list(self, user_id: int, slug: str | None = None) -> list[dict]:
        sql = "SELECT cid, slug, title, updated_at FROM conversations WHERE user_id=?"
        args: list = [user_id]
        if slug:
            sql += " AND slug=?"
            args.append(slug)
        sql += " ORDER BY updated_at DESC"
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def used_slugs(self, user_id: int) -> set[str]:
        """当前用户用过的技能 slug 集合（去重）。"""
        with self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT slug FROM conversations WHERE user_id=?",
                (user_id,),
            ).fetchall()
        return {r["slug"] for r in rows if r["slug"]}


manager = ConversationManager()
