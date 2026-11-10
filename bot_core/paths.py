from __future__ import annotations

import os
from pathlib import Path


def resolve_bot_data_dir() -> Path:
    configured = Path(os.getenv("BOT_DATA_DIR", "/data"))
    if configured.exists():
        return configured
    return Path(__file__).resolve().parents[1]


BOT_DATA_DIR = resolve_bot_data_dir()
BOT_DATA_DIR.mkdir(parents=True, exist_ok=True)


def data_file(name: str) -> str:
    return str(BOT_DATA_DIR / name)
