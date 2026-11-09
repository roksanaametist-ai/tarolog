from pathlib import Path

INIT = '''"""Public exports for the tarolog bot_core package."""

from bot_core.attribution import (
    build_campaign_payload,
    build_partner_payload,
    parse_start_attribution,
)
from bot_core.backups import BackupManager, daily_backup_loop
from bot_core.fsm_sqlite import SqliteStorage
from bot_core.json_store import atomic_write_json
from bot_core.operational_store import OperationalStore
from bot_core.paths import BOT_DATA_DIR, data_file, resolve_bot_data_dir
from bot_core.payment_stats import PaymentStatsStore
from bot_core.share_cards import generate_share_card

__all__ = [
    "BOT_DATA_DIR",
    "BackupManager",
    "OperationalStore",
    "PaymentStatsStore",
    "SqliteStorage",
    "atomic_write_json",
    "build_campaign_payload",
    "build_partner_payload",
    "daily_backup_loop",
    "data_file",
    "generate_share_card",
    "parse_start_attribution",
    "resolve_bot_data_dir",
]
'''

path = Path("/root/tarolog/bot_core/__init__.py")
path.write_text(INIT, encoding="utf-8")
print("wrote", path, path.stat().st_size)
