"""Persistent FSM storage for aiogram 3 (SQLite). Survives bot restarts."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aiogram.exceptions import DataNotDictLikeError
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey


def _key_str(key: StorageKey) -> str:
    return ":".join(
        [
            str(key.bot_id),
            str(key.chat_id),
            str(key.user_id),
            str(key.thread_id or 0),
            str(key.business_connection_id or ""),
            str(key.destiny or "default"),
        ]
    )


class SqliteStorage(BaseStorage):
    """SQLite-backed FSM: state + data persist across restarts."""

    def __init__(self, path: str | Path, *, ttl_days: int = 14) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = max(1, int(ttl_days)) * 86400
        self._lock = threading.RLock()
        self._last_prune = 0.0
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fsm (
                        key TEXT PRIMARY KEY,
                        state TEXT,
                        data TEXT NOT NULL DEFAULT '{}',
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_fsm_updated ON fsm(updated_at)"
                )
                conn.commit()

    def _maybe_prune(self, conn: sqlite3.Connection) -> None:
        now = time.time()
        if now - self._last_prune < 3600:
            return
        self._last_prune = now
        cutoff = now - self.ttl_seconds
        conn.execute("DELETE FROM fsm WHERE updated_at < ?", (cutoff,))
        # Пустые записи без state тоже можно чистить
        conn.execute(
            "DELETE FROM fsm WHERE (state IS NULL OR state = '') AND data = '{}'"
        )

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_value = state.state if isinstance(state, State) else state
        k = _key_str(key)
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT data FROM fsm WHERE key = ?", (k,)
                ).fetchone()
                data = row[0] if row else "{}"
                conn.execute(
                    """
                    INSERT INTO fsm(key, state, data, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        state = excluded.state,
                        updated_at = excluded.updated_at
                    """,
                    (k, state_value, data, now),
                )
                # Если state сброшен и data пустая — удаляем строку
                if not state_value:
                    data_obj = json.loads(data or "{}")
                    if not data_obj:
                        conn.execute("DELETE FROM fsm WHERE key = ?", (k,))
                self._maybe_prune(conn)
                conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        k = _key_str(key)
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT state FROM fsm WHERE key = ?", (k,)
                ).fetchone()
        if not row:
            return None
        return row[0]

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if not isinstance(data, dict):
            msg = f"Data must be a dict or dict-like object, got {type(data).__name__}"
            raise DataNotDictLikeError(msg)
        k = _key_str(key)
        now = time.time()
        payload = json.dumps(data, ensure_ascii=False, default=str)
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT state FROM fsm WHERE key = ?", (k,)
                ).fetchone()
                state_value = row[0] if row else None
                if not data and not state_value:
                    conn.execute("DELETE FROM fsm WHERE key = ?", (k,))
                else:
                    conn.execute(
                        """
                        INSERT INTO fsm(key, state, data, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET
                            data = excluded.data,
                            updated_at = excluded.updated_at
                        """,
                        (k, state_value, payload, now),
                    )
                self._maybe_prune(conn)
                conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        k = _key_str(key)
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT data FROM fsm WHERE key = ?", (k,)
                ).fetchone()
        if not row or not row[0]:
            return {}
        try:
            raw = json.loads(row[0])
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    async def close(self) -> None:
        # Connections are per-call; nothing sticky to close.
        return
