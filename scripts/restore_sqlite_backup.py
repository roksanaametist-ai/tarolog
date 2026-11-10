#!/usr/bin/env python3
"""Validate and restore one SQLite backup.

Stop the bot service before running this command.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_core.backups import backup_sqlite, sqlite_integrity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required: replace the target database",
    )
    args = parser.parse_args()

    backup = args.backup.resolve()
    target = args.target.resolve()
    if not backup.exists():
        raise SystemExit(f"Backup not found: {backup}")
    result = sqlite_integrity(backup)
    if result.lower() != "ok":
        raise SystemExit(f"Backup is corrupt: {result}")
    if not args.confirm:
        print(f"Backup valid: {backup}")
        print(f"Target: {target}")
        print("Re-run with --confirm after stopping the bot service.")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety_copy = target.with_name(f"{target.name}.pre-restore-{stamp}")
        backup_sqlite(target, safety_copy)
        print(f"Current database saved: {safety_copy}")

    temporary = target.with_suffix(target.suffix + ".restore.tmp")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(backup, timeout=30)) as source:
        with closing(sqlite3.connect(temporary, timeout=30)) as destination:
            source.backup(destination)
    restored_integrity = sqlite_integrity(temporary)
    if restored_integrity.lower() != "ok":
        temporary.unlink(missing_ok=True)
        raise SystemExit(f"Restored copy is corrupt: {restored_integrity}")
    os.replace(temporary, target)
    print(f"Restored: {target}")
    print("Integrity: ok")


if __name__ == "__main__":
    main()
