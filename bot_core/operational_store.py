from __future__ import annotations

import copy
import json
import logging
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .json_store import atomic_write_json


log = logging.getLogger(__name__)


class OperationalStore:
    """Canonical SQLite storage for legacy JSON-shaped bot state.

    Existing classes can keep their public APIs and in-memory shapes. Reads
    prefer SQLite; an existing JSON file is imported once. Writes commit to
    SQLite first and optionally refresh a JSON compatibility snapshot.
    """

    SCHEMA_VERSION = "1"

    def __init__(self, path: str | Path, *, mirror_json: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.mirror_json = bool(mirror_json)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'runtime'
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
                (self.SCHEMA_VERSION,),
            )

    @staticmethod
    def _read_legacy(path: Path, default: Any) -> Any:
        if not path.exists():
            return copy.deepcopy(default)
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            log.exception("legacy JSON load failed: %s", path)
            return copy.deepcopy(default)

    def load_document(
        self,
        name: str,
        *,
        legacy_path: str | Path,
        default: Any,
    ) -> Any:
        document_name = str(name).strip()
        if not document_name:
            raise ValueError("document name is required")
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload FROM documents WHERE name=?",
                (document_name,),
            ).fetchone()
        if row is not None:
            try:
                return json.loads(str(row["payload"]))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Corrupt SQLite document: {document_name}"
                ) from exc

        legacy = Path(legacy_path)
        data = self._read_legacy(legacy, default)
        self.save_document(
            document_name,
            data,
            legacy_path=legacy,
            source="legacy_json" if legacy.exists() else "default",
        )
        return copy.deepcopy(data)

    def document_revision(self, name: str) -> int:
        document_name = str(name).strip()
        if not document_name:
            return 0
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT revision FROM documents WHERE name=?",
                (document_name,),
            ).fetchone()
        return int(row["revision"]) if row is not None else 0

    def update_document(
        self,
        name: str,
        mutator,
        *,
        legacy_path: str | Path | None = None,
        source: str = "runtime",
        default: Any = None,
    ) -> Any:
        """Read-modify-write one document under BEGIN IMMEDIATE.

        `mutator(current) -> updated`. Used so the live bot can merge RAM
        onto the latest sqlite payload instead of clobbering external grants.
        """
        document_name = str(name).strip()
        if not document_name:
            raise ValueError("document name is required")
        if default is None:
            default = {}
        legacy = Path(legacy_path) if legacy_path is not None else None
        with self._lock, closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT payload FROM documents WHERE name=?",
                    (document_name,),
                ).fetchone()
                if row is not None:
                    try:
                        current = json.loads(str(row["payload"]))
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"Corrupt SQLite document: {document_name}"
                        ) from exc
                elif legacy is not None:
                    current = self._read_legacy(legacy, default)
                else:
                    current = copy.deepcopy(default)
                updated = mutator(current)
                if updated is None:
                    updated = current
                payload = json.dumps(
                    updated,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                )
                updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                conn.execute(
                    """
                    INSERT INTO documents(name, payload, revision, updated_at, source)
                    VALUES(?, ?, 1, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        payload=excluded.payload,
                        revision=documents.revision + 1,
                        updated_at=excluded.updated_at,
                        source=excluded.source
                    """,
                    (document_name, payload, updated_at, source),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        if self.mirror_json and legacy is not None:
            try:
                atomic_write_json(legacy, updated)
            except Exception:
                log.exception("JSON mirror write failed: %s", legacy)
        return updated

    def save_document(
        self,
        name: str,
        data: Any,
        *,
        legacy_path: str | Path | None = None,
        source: str = "runtime",
    ) -> int:
        payload = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO documents(name, payload, revision, updated_at, source)
                VALUES(?, ?, 1, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload=excluded.payload,
                    revision=documents.revision + 1,
                    updated_at=excluded.updated_at,
                    source=excluded.source
                """,
                (name, payload, updated_at, source),
            )
            revision = int(
                conn.execute(
                    "SELECT revision FROM documents WHERE name=?", (name,)
                ).fetchone()["revision"]
            )

        if self.mirror_json and legacy_path is not None:
            try:
                atomic_write_json(legacy_path, data)
            except Exception:
                # SQLite already committed. Compatibility export can be retried.
                log.exception("JSON mirror write failed: %s", legacy_path)
        return revision

    def export_document(self, name: str, path: str | Path) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload FROM documents WHERE name=?", (name,)
            ).fetchone()
        if row is None:
            return False
        atomic_write_json(path, json.loads(str(row["payload"])))
        return True

    def list_documents(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT name, revision, updated_at, source, length(payload) AS bytes
                FROM documents ORDER BY name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def integrity_check(self) -> str:
        with closing(self._connect()) as conn:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])

    def checkpoint(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
