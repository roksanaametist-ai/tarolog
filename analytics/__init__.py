"""SQLite-backed analytics for the Telegram bot."""

from .admin import build_admin_dashboard
from .store import AnalyticsStore

__all__ = ["AnalyticsStore", "build_admin_dashboard"]
