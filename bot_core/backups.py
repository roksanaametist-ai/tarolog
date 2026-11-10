from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from .json_store import atomic_write_json


log = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")


def sqlite_integrity(path: str | Path) -> str:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=15)) as conn:
        return str(conn.execute("PRAGMA integrity_check").fetchone()[0])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_sqlite(source: str | Path, destination: str | Path) -> dict:
    src = Path(source)
    dest = Path(destination)
    if not src.exists():
        raise FileNotFoundError(src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(src, timeout=30)) as source_conn:
            with closing(sqlite3.connect(temporary, timeout=30)) as backup_conn:
                source_conn.backup(backup_conn)
        result = sqlite_integrity(temporary)
        if result.lower() != "ok":
            raise RuntimeError(f"backup integrity check failed: {result}")
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "source": str(src),
        "backup": str(dest),
        "bytes": dest.stat().st_size,
        "sha256": _sha256(dest),
        "integrity": "ok",
    }


class BackupManager:
    def __init__(
        self,
        databases: Iterable[str | Path],
        backup_dir: str | Path,
        *,
        retention_days: int = 14,
    ) -> None:
        self.databases = [Path(path) for path in databases]
        self.backup_dir = Path(backup_dir)
        self.retention_days = max(2, int(retention_days))

    def run_daily(self, now: datetime | None = None) -> dict:
        now = now.astimezone(MOSCOW) if now and now.tzinfo else (now or datetime.now(MOSCOW))
        day = now.strftime("%Y-%m-%d")
        day_dir = self.backup_dir / day
        entries: list[dict] = []
        for database in self.databases:
            if not database.exists():
                continue
            target = day_dir / database.name
            if target.exists() and sqlite_integrity(target).lower() == "ok":
                entries.append(
                    {
                        "source": str(database),
                        "backup": str(target),
                        "bytes": target.stat().st_size,
                        "sha256": _sha256(target),
                        "integrity": "ok",
                        "existing": True,
                    }
                )
            else:
                entries.append(backup_sqlite(database, target))
        manifest = {
            "created_at": now.isoformat(timespec="seconds"),
            "retention_days": self.retention_days,
            "databases": entries,
        }
        day_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(day_dir / "manifest.json", manifest)
        removed = self.prune(now=now)
        manifest["removed_old_backups"] = removed
        atomic_write_json(day_dir / "manifest.json", manifest)
        return manifest

    def prune(self, now: datetime | None = None) -> list[str]:
        now = now.astimezone(MOSCOW) if now and now.tzinfo else (now or datetime.now(MOSCOW))
        cutoff = now.date() - timedelta(days=self.retention_days - 1)
        removed: list[str] = []
        if not self.backup_dir.exists():
            return removed
        for child in self.backup_dir.iterdir():
            if not child.is_dir():
                continue
            try:
                backup_day = datetime.strptime(child.name, "%Y-%m-%d").date()
            except ValueError:
                continue
            if backup_day >= cutoff:
                continue
            for path in sorted(child.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            child.rmdir()
            removed.append(str(child))
        return removed


async def daily_backup_loop(
    manager: BackupManager,
    *,
    check_interval_seconds: int = 3600,
) -> None:
    last_day: str | None = None
    while True:
        now = datetime.now(MOSCOW)
        day = now.strftime("%Y-%m-%d")
        if day != last_day:
            try:
                manifest = await asyncio.to_thread(manager.run_daily, now)
                log.info("SQLite daily backup complete: %s", json.dumps(manifest))
                last_day = day
            except Exception:
                log.exception("SQLite daily backup failed")
        await asyncio.sleep(max(60, int(check_interval_seconds)))
