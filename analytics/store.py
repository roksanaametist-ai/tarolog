from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from zoneinfo import ZoneInfo


log = logging.getLogger(__name__)
MOSCOW = ZoneInfo("Europe/Moscow")


class AnalyticsStore:
    """Append-only event store and metric queries.

    The bot's operational JSON files remain untouched. SQLite is the canonical
    analytics store: writes are atomic, concurrent-safe and do not have a
    retention cap.
    """

    SCHEMA_VERSION = "1"

    def __init__(self, path: str | Path, *, channel: str = "telegram") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.channel = channel
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    local_date TEXT NOT NULL,
                    user_id INTEGER,
                    channel TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    value INTEGER NOT NULL DEFAULT 1,
                    properties TEXT NOT NULL DEFAULT '{}',
                    dedupe_key TEXT UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_events_name_date
                    ON events(event_name, local_date);
                CREATE INDEX IF NOT EXISTS idx_events_user_date
                    ON events(user_id, local_date);
                CREATE INDEX IF NOT EXISTS idx_events_occurred
                    ON events(occurred_at);
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
    def _normalize_time(
        occurred_at: datetime | str | None,
    ) -> tuple[str, str]:
        if occurred_at is None:
            local = datetime.now(MOSCOW)
        elif isinstance(occurred_at, datetime):
            local = occurred_at
            if local.tzinfo is None:
                local = local.replace(tzinfo=MOSCOW)
            else:
                local = local.astimezone(MOSCOW)
        else:
            raw = str(occurred_at).strip()
            parsed: Optional[datetime] = None
            for parser in (
                datetime.fromisoformat,
                lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M:%S"),
            ):
                try:
                    parsed = parser(raw)
                    break
                except (TypeError, ValueError):
                    continue
            if parsed is None:
                local = datetime.now(MOSCOW)
            elif parsed.tzinfo is None:
                local = parsed.replace(tzinfo=MOSCOW)
            else:
                local = parsed.astimezone(MOSCOW)
        utc = local.astimezone(timezone.utc)
        return utc.isoformat(timespec="seconds"), local.date().isoformat()

    def track(
        self,
        event_name: str,
        *,
        user_id: int | None = None,
        properties: Mapping[str, Any] | None = None,
        occurred_at: datetime | str | None = None,
        value: int = 1,
        dedupe_key: str | None = None,
        channel: str | None = None,
    ) -> bool:
        name = str(event_name or "").strip()[:80]
        if not name:
            return False
        ts, local_date = self._normalize_time(occurred_at)
        payload = json.dumps(
            dict(properties or {}), ensure_ascii=False, separators=(",", ":"), default=str
        )
        try:
            with self._lock, closing(self._connect()) as conn, conn:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO events(
                        occurred_at, local_date, user_id, channel,
                        event_name, value, properties, dedupe_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        local_date,
                        int(user_id) if user_id is not None else None,
                        channel or self.channel,
                        name,
                        max(0, int(value)),
                        payload,
                        dedupe_key,
                    ),
                )
                return cur.rowcount > 0
        except Exception:
            log.exception("analytics event write failed: %s", name)
            return False

    def get_metadata(self, key: str) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES(?, ?)",
                (key, value),
            )

    def backfill_legacy(
        self,
        *,
        logs: Iterable[Mapping[str, Any]] = (),
        readings: Iterable[Mapping[str, Any]] = (),
        users: Mapping[str, Mapping[str, Any]] | None = None,
        payment_data: Mapping[str, Any] | None = None,
    ) -> dict[str, int]:
        """Idempotently import existing JSON analytics once."""
        marker = "legacy_json_backfill_v1"
        if self.get_metadata(marker):
            return {"skipped": 1}

        counts: Counter[str] = Counter()
        first_seen: dict[int, str] = {}
        logs_list = [row for row in logs if isinstance(row, Mapping)]
        for idx, row in enumerate(logs_list):
            uid_raw = row.get("user_id")
            try:
                uid = int(uid_raw) if uid_raw is not None else None
            except (TypeError, ValueError):
                uid = None
            at = str(row.get("date") or "")
            command = str(row.get("command") or "")
            if uid is not None and at and (uid not in first_seen or at < first_seen[uid]):
                first_seen[uid] = at
            if self.track(
                "interaction",
                user_id=uid,
                occurred_at=at,
                properties={"command": command, "legacy": True},
                dedupe_key=f"legacy:log:{idx}",
            ):
                counts["interaction"] += 1
            if command.startswith("/start"):
                payload = command.split(maxsplit=1)[1] if len(command.split(maxsplit=1)) > 1 else ""
                if self.track(
                    "bot_started",
                    user_id=uid,
                    occurred_at=at,
                    properties={"payload": payload, "legacy": True},
                    dedupe_key=f"legacy:start:{idx}",
                ):
                    counts["bot_started"] += 1
                if payload.startswith("share_") and self.track(
                    "share_link_started",
                    user_id=uid,
                    occurred_at=at,
                    properties={"payload": payload, "legacy": True},
                    dedupe_key=f"legacy:share-start:{idx}",
                ):
                    counts["share_link_started"] += 1

        for uid, at in first_seen.items():
            if self.track(
                "user_registered",
                user_id=uid,
                occurred_at=at,
                properties={"source": "legacy_first_log"},
                dedupe_key=f"legacy:registered:{uid}",
            ):
                counts["user_registered"] += 1

        for idx, row in enumerate(readings):
            if not isinstance(row, Mapping):
                continue
            try:
                uid = int(row.get("user_id"))
            except (TypeError, ValueError):
                continue
            if self.track(
                "reading_completed",
                user_id=uid,
                occurred_at=str(row.get("at") or ""),
                properties={
                    "kind": str(row.get("kind") or "ask"),
                    "legacy": True,
                },
                dedupe_key=f"legacy:reading:{idx}",
            ):
                counts["reading_completed"] += 1

        for uid_s, row in (users or {}).items():
            if not isinstance(row, Mapping):
                continue
            try:
                uid = int(uid_s)
            except (TypeError, ValueError):
                continue
            referred_at = str(row.get("referred_at") or "")
            if row.get("referred_by") is not None and referred_at:
                if self.track(
                    "referral_signup",
                    user_id=uid,
                    occurred_at=referred_at,
                    properties={
                        "source": str(row.get("referral_source") or "ref"),
                        "referrer_id": row.get("referred_by"),
                        "legacy": True,
                    },
                    dedupe_key=f"legacy:referral:{uid}",
                ):
                    counts["referral_signup"] += 1
                source = str(row.get("referral_source") or "ref")
                source_event = (
                    "referral_share_signup"
                    if source == "share"
                    else "referral_link_signup"
                )
                if self.track(
                    source_event,
                    user_id=uid,
                    occurred_at=referred_at,
                    properties={
                        "referrer_id": row.get("referred_by"),
                        "legacy": True,
                    },
                    dedupe_key=f"legacy:referral-source:{uid}",
                ):
                    counts[source_event] += 1
            share_at = str(row.get("last_share_click_at") or "")
            share_clicks = int(row.get("share_clicks") or 0)
            if share_at and share_clicks:
                if self.track(
                    "share_legacy_total",
                    user_id=uid,
                    occurred_at=share_at,
                    value=share_clicks,
                    properties={"legacy_compacted": True},
                    dedupe_key=f"legacy:share:{uid}",
                ):
                    counts["share_legacy_total"] += share_clicks

        payment_data = payment_data or {}
        amount = int(payment_data.get("total_amount") or 0)
        if amount:
            if self.track(
                "payment_legacy_total",
                value=amount,
                properties={
                    "unit": "kopecks",
                    "subscriptions": payment_data.get("subscriptions") or {},
                },
                dedupe_key="legacy:payments:aggregate",
            ):
                counts["payment_legacy_total"] += amount

        self.set_metadata(marker, datetime.now(MOSCOW).isoformat(timespec="seconds"))
        return dict(counts)

    @staticmethod
    def _period_start(days: int, today: date) -> str:
        return (today - timedelta(days=max(1, int(days)) - 1)).isoformat()

    def _period_metrics(self, days: int, today: date) -> dict[str, Any]:
        start = self._period_start(days, today)
        end = today.isoformat()
        with closing(self._connect()) as conn:
            counts = {
                row["event_name"]: int(row["n"])
                for row in conn.execute(
                    """
                    SELECT event_name, SUM(value) AS n
                    FROM events
                    WHERE local_date BETWEEN ? AND ?
                    GROUP BY event_name
                    """,
                    (start, end),
                )
            }
            unique = {
                row["event_name"]: int(row["n"])
                for row in conn.execute(
                    """
                    SELECT event_name, COUNT(DISTINCT user_id) AS n
                    FROM events
                    WHERE local_date BETWEEN ? AND ? AND user_id IS NOT NULL
                    GROUP BY event_name
                    """,
                    (start, end),
                )
            }
            active = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) AS n FROM events
                    WHERE local_date BETWEEN ? AND ? AND user_id IS NOT NULL
                      AND event_name NOT LIKE 'admin_%'
                      AND event_name NOT LIKE 'broadcast_%'
                      AND event_name NOT LIKE 'winback_%'
                      AND event_name NOT LIKE 'tomorrow_push_%'
                    """,
                    (start, end),
                ).fetchone()["n"]
            )
            kinds_raw = {
                row["kind"]: int(row["n"])
                for row in conn.execute(
                    """
                    SELECT COALESCE(json_extract(properties, '$.kind'), 'ask') AS kind,
                           SUM(value) AS n
                    FROM events
                    WHERE event_name='reading_completed'
                      AND local_date BETWEEN ? AND ?
                    GROUP BY kind
                    ORDER BY n DESC
                    """,
                    (start, end),
                )
            }
            clarify_completed = int(kinds_raw.pop("clarify", 0) or 0)
            kinds = kinds_raw
            reading_completed_total = int(counts.get("reading_completed") or 0)
            reading_completed_core = max(0, reading_completed_total - clarify_completed)
            counts["clarify_completed"] = clarify_completed
            counts["reading_completed_all"] = reading_completed_total
            counts["reading_completed"] = reading_completed_core
            unique_readers_core = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) AS n
                    FROM events
                    WHERE event_name='reading_completed'
                      AND local_date BETWEEN ? AND ?
                      AND user_id IS NOT NULL
                      AND COALESCE(json_extract(properties, '$.kind'), 'ask') != 'clarify'
                    """,
                    (start, end),
                ).fetchone()["n"]
            )
            if "reading_completed" in unique:
                unique["reading_completed_all"] = unique["reading_completed"]
                unique["reading_completed"] = unique_readers_core
            revenue = int(
                conn.execute(
                    """
                    SELECT COALESCE(SUM(
                        CAST(json_extract(properties, '$.amount_kopecks') AS INTEGER)
                    ), 0) AS n
                    FROM events
                    WHERE event_name='payment_succeeded'
                      AND local_date BETWEEN ? AND ?
                    """,
                    (start, end),
                ).fetchone()["n"]
            )
        return {
            "days": days,
            "start": start,
            "end": end,
            "active_users": active,
            "counts": counts,
            "unique": unique,
            "reading_kinds": kinds,
            "revenue_kopecks": revenue,
        }

    def _activation(self, days: int, today: date) -> dict[str, Any]:
        start = self._period_start(days, today)
        end = today.isoformat()
        with closing(self._connect()) as conn:
            registered = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) AS n FROM events
                    WHERE event_name='user_registered'
                      AND local_date BETWEEN ? AND ?
                    """,
                    (start, end),
                ).fetchone()["n"]
            )
            activated = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT r.user_id) AS n
                    FROM events r
                    WHERE r.event_name='user_registered'
                      AND r.local_date BETWEEN ? AND ?
                      AND EXISTS (
                        SELECT 1 FROM events e
                        WHERE e.user_id=r.user_id
                          AND e.event_name='reading_completed'
                          AND julianday(e.occurred_at) >= julianday(r.occurred_at)
                          AND julianday(e.occurred_at) < julianday(r.occurred_at, '+1 day')
                      )
                    """,
                    (start, end),
                ).fetchone()["n"]
            )
        return {
            "registered": registered,
            "activated_24h": activated,
            "rate": round(100 * activated / registered, 1) if registered else 0.0,
        }

    def _retention(self, offset_days: int, today: date, cohort_days: int = 30) -> dict[str, Any]:
        cohort_end = today - timedelta(days=offset_days)
        cohort_start = cohort_end - timedelta(days=cohort_days - 1)
        with closing(self._connect()) as conn:
            cohort = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) AS n FROM events
                    WHERE event_name='user_registered'
                      AND local_date BETWEEN ? AND ?
                    """,
                    (cohort_start.isoformat(), cohort_end.isoformat()),
                ).fetchone()["n"]
            )
            returned = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT r.user_id) AS n
                    FROM events r
                    WHERE r.event_name='user_registered'
                      AND r.local_date BETWEEN ? AND ?
                      AND EXISTS (
                        SELECT 1 FROM events e
                        WHERE e.user_id=r.user_id
                          AND e.local_date=date(r.local_date, ?)
                          AND e.event_name NOT LIKE 'admin_%'
                      )
                    """,
                    (
                        cohort_start.isoformat(),
                        cohort_end.isoformat(),
                        f"+{offset_days} day",
                    ),
                ).fetchone()["n"]
            )
        return {
            "cohort": cohort,
            "returned": returned,
            "rate": round(100 * returned / cohort, 1) if cohort else 0.0,
        }

    def _resurrected(self, days: int, today: date) -> int:
        current_start = today - timedelta(days=days - 1)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=29)
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT current.user_id) AS n
                FROM events current
                WHERE current.local_date BETWEEN ? AND ?
                  AND current.user_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM events old
                    WHERE old.user_id=current.user_id AND old.local_date < ?
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM events recent
                    WHERE recent.user_id=current.user_id
                      AND recent.local_date BETWEEN ? AND ?
                  )
                """,
                (
                    current_start.isoformat(),
                    today.isoformat(),
                    previous_start.isoformat(),
                    previous_start.isoformat(),
                    previous_end.isoformat(),
                ),
            ).fetchone()
        return int(row["n"])

    def _property_breakdown(
        self,
        event_name: str,
        property_name: str,
        *,
        days: int,
        today: date,
        only_new: bool = False,
        limit: int = 12,
    ) -> dict[str, int]:
        start = self._period_start(days, today)
        new_clause = (
            "AND CAST(json_extract(properties, '$.is_new') AS INTEGER)=1"
            if only_new
            else ""
        )
        sql = f"""
            SELECT COALESCE(
                       json_extract(properties, '$.{property_name}'), 'unknown'
                   ) AS property_value,
                   COUNT(DISTINCT user_id) AS n
            FROM events
            WHERE event_name=? AND local_date BETWEEN ? AND ?
              AND user_id IS NOT NULL
              {new_clause}
            GROUP BY property_value
            ORDER BY n DESC
            LIMIT ?
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                sql, (event_name, start, today.isoformat(), max(1, int(limit)))
            ).fetchall()
        return {str(row["property_value"]): int(row["n"]) for row in rows}

    def _broadcast_response(
        self, days: int, today: date, *, window_days: int = 3
    ) -> dict[str, dict[str, int]]:
        """Per broadcast campaign: recipients and how many opened the bot afterwards.

        "Opened" = any own action (not another broadcast/push) within
        ``window_days`` after the message was sent.
        """
        start = self._period_start(days, today)
        sql = """
            SELECT COALESCE(json_extract(b.properties, '$.campaign'), 'без названия') AS campaign,
                   COUNT(DISTINCT b.user_id) AS sent,
                   COUNT(DISTINCT CASE WHEN EXISTS (
                        SELECT 1 FROM events e
                        WHERE e.user_id = b.user_id
                          AND e.local_date >= b.local_date
                          AND julianday(e.occurred_at) > julianday(b.occurred_at)
                          AND julianday(e.occurred_at) <= julianday(b.occurred_at) + ?
                          AND e.event_name NOT LIKE 'broadcast_%'
                          AND e.event_name NOT LIKE 'winback_%'
                          AND e.event_name NOT LIKE 'tomorrow_push_%'
                          AND e.event_name NOT LIKE 'admin_%'
                   ) THEN b.user_id END) AS returned,
                   MAX(b.local_date) AS last_date
            FROM events b
            WHERE b.event_name = 'broadcast_sent'
              AND b.local_date BETWEEN ? AND ?
              AND b.user_id IS NOT NULL
            GROUP BY campaign
            ORDER BY last_date DESC
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                sql, (float(window_days), start, today.isoformat())
            ).fetchall()
        return {
            str(row["campaign"]): {
                "sent": int(row["sent"] or 0),
                "returned": int(row["returned"] or 0),
                "last_date": str(row["last_date"] or ""),
            }
            for row in rows
        }

    def _abandoned_checkouts(self, days: int, today: date) -> dict[str, int]:
        """Users who got a payment link in the period and have no successful payment after it."""
        start = self._period_start(days, today)
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT c.user_id) AS got_link,
                       COUNT(DISTINCT CASE WHEN NOT EXISTS (
                           SELECT 1 FROM events p
                           WHERE p.user_id = c.user_id
                             AND p.event_name = 'payment_succeeded'
                             AND p.local_date >= c.local_date
                       ) THEN c.user_id END) AS abandoned
                FROM events c
                WHERE c.event_name = 'payment_checkout'
                  AND c.local_date BETWEEN ? AND ?
                  AND c.user_id IS NOT NULL
                """,
                (start, today.isoformat()),
            ).fetchone()
        return {
            "got_link": int(row["got_link"] or 0),
            "abandoned": int(row["abandoned"] or 0),
        }

    def _funnel_breakdown(
        self,
        property_name: str,
        events: Mapping[str, str],
        *,
        days: int,
        today: date,
        limit: int = 12,
    ) -> dict[str, dict[str, int]]:
        """Cohort funnel per tracking code.

        ``activated`` counts only users who also have a ``signups`` event for the
        same code — returning visitors no longer inflate activation above 100%.
        ``activated_returning`` is exposed separately for transparency.
        """
        start = self._period_start(days, today)
        end = today.isoformat()
        start_event = events.get("starts")
        signup_event = events.get("signups")
        activated_event = events.get("activated")
        paid_event = events.get("paid")
        prop = property_name

        def _empty() -> dict[str, int]:
            return {
                "starts": 0,
                "signups": 0,
                "activated": 0,
                "activated_returning": 0,
                "paid": 0,
            }

        output: dict[str, dict[str, int]] = {}
        with closing(self._connect()) as conn:

            def _load(event_name: str | None, metric: str) -> None:
                if not event_name:
                    return
                rows = conn.execute(
                    f"""
                    SELECT COALESCE(
                               json_extract(properties, '$.{prop}'), 'unknown'
                           ) AS code,
                           COUNT(DISTINCT user_id) AS n
                    FROM events
                    WHERE event_name=?
                      AND local_date BETWEEN ? AND ?
                      AND user_id IS NOT NULL
                    GROUP BY code
                    """,
                    (event_name, start, end),
                ).fetchall()
                for row in rows:
                    code = str(row["code"] or "unknown")
                    if code.strip().lower() in {"", "unknown", "none", "null"}:
                        continue
                    output.setdefault(code, _empty())[metric] = int(row["n"])

            _load(start_event, "starts")
            _load(signup_event, "signups")
            _load(paid_event, "paid")

            if signup_event and activated_event:
                rows = conn.execute(
                    f"""
                    SELECT COALESCE(
                               json_extract(s.properties, '$.{prop}'), 'unknown'
                           ) AS code,
                           COUNT(DISTINCT s.user_id) AS n
                    FROM events s
                    WHERE s.event_name=?
                      AND s.local_date BETWEEN ? AND ?
                      AND s.user_id IS NOT NULL
                      AND EXISTS (
                        SELECT 1 FROM events a
                        WHERE a.user_id=s.user_id
                          AND a.event_name=?
                          AND a.local_date BETWEEN ? AND ?
                          AND COALESCE(json_extract(a.properties, '$.{prop}'), '')
                              = COALESCE(json_extract(s.properties, '$.{prop}'), '')
                      )
                    GROUP BY code
                    """,
                    (signup_event, start, end, activated_event, start, end),
                ).fetchall()
                for row in rows:
                    code = str(row["code"] or "unknown")
                    if code.strip().lower() in {"", "unknown", "none", "null"}:
                        continue
                    bucket = output.setdefault(code, _empty())
                    bucket["activated"] = int(row["n"])

            if activated_event and signup_event:
                rows = conn.execute(
                    f"""
                    SELECT COALESCE(
                               json_extract(a.properties, '$.{prop}'), 'unknown'
                           ) AS code,
                           COUNT(DISTINCT a.user_id) AS n
                    FROM events a
                    WHERE a.event_name=?
                      AND a.local_date BETWEEN ? AND ?
                      AND a.user_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM events s
                        WHERE s.user_id=a.user_id
                          AND s.event_name=?
                          AND COALESCE(json_extract(s.properties, '$.{prop}'), '')
                              = COALESCE(json_extract(a.properties, '$.{prop}'), '')
                      )
                    GROUP BY code
                    """,
                    (activated_event, start, end, signup_event),
                ).fetchall()
                for row in rows:
                    code = str(row["code"] or "unknown")
                    if code.strip().lower() in {"", "unknown", "none", "null"}:
                        continue
                    bucket = output.setdefault(code, _empty())
                    bucket["activated_returning"] = int(row["n"])

        return dict(
            sorted(
                output.items(),
                key=lambda item: (
                    -int(item[1].get("signups") or item[1].get("starts") or 0),
                    item[0],
                ),
            )[:limit]
        )

    def snapshot(self) -> dict[str, Any]:
        today = datetime.now(MOSCOW).date()
        periods = {
            "today": self._period_metrics(1, today),
            "7d": self._period_metrics(7, today),
            "30d": self._period_metrics(30, today),
        }
        with closing(self._connect()) as conn:
            lifetime = {
                row["event_name"]: int(row["n"])
                for row in conn.execute(
                    "SELECT event_name, SUM(value) AS n FROM events GROUP BY event_name"
                )
            }
            lifetime_unique = {
                row["event_name"]: int(row["n"])
                for row in conn.execute(
                    """
                    SELECT event_name, COUNT(DISTINCT user_id) AS n
                    FROM events WHERE user_id IS NOT NULL GROUP BY event_name
                    """
                )
            }
            legacy_revenue = int(
                conn.execute(
                    """
                    SELECT COALESCE(SUM(value), 0) AS n FROM events
                    WHERE event_name='payment_legacy_total'
                    """
                ).fetchone()["n"]
            )
        return {
            "generated_at": datetime.now(MOSCOW).strftime("%d.%m.%Y %H:%M MSK"),
            "periods": periods,
            "lifetime": lifetime,
            "lifetime_unique": lifetime_unique,
            "legacy_revenue_kopecks": legacy_revenue,
            "activation_7d": self._activation(7, today),
            "activation_30d": self._activation(30, today),
            "retention_d1": self._retention(1, today),
            "retention_d7": self._retention(7, today),
            "resurrected_7d": self._resurrected(7, today),
            # the 7 days before the current 7-day window, for ↑/↓ comparison
            "prev_7d": self._period_metrics(7, today - timedelta(days=7)),
            "broadcasts_7d": self._broadcast_response(7, today),
            "abandoned_checkouts_7d": self._abandoned_checkouts(7, today),
            "abandoned_checkouts_30d": self._abandoned_checkouts(30, today),
            "acquisition_sources_7d": self._property_breakdown(
                "bot_started", "source", days=7, today=today, only_new=True
            ),
            "acquisition_sources_30d": self._property_breakdown(
                "bot_started", "source", days=30, today=today, only_new=True
            ),
            "compat_paid_sources_30d": self._property_breakdown(
                "compat_paid_done", "source", days=30, today=today
            ),
            "callbacks_7d": self._property_breakdown(
                "callback_clicked", "callback", days=7, today=today
            ),
            "partner_funnel_30d": self._funnel_breakdown(
                "partner",
                {
                    "starts": "partner_link_started",
                    "signups": "partner_signup",
                    "activated": "partner_activated",
                    "paid": "payment_succeeded",
                },
                days=30,
                today=today,
            ),
            "campaign_funnel_30d": self._funnel_breakdown(
                "campaign",
                {
                    "starts": "campaign_link_started",
                    "signups": "campaign_signup",
                    "activated": "campaign_activated",
                    "paid": "payment_succeeded",
                },
                days=30,
                today=today,
            ),
        }

    def period(self, days: int) -> dict[str, Any]:
        return self._period_metrics(max(1, int(days)), datetime.now(MOSCOW).date())

    def daily(self, days: int) -> list[dict[str, Any]]:
        today = datetime.now(MOSCOW).date()
        days = max(1, int(days))
        start = today - timedelta(days=days - 1)
        output: list[dict[str, Any]] = []
        with closing(self._connect()) as conn:
            for offset in range(days):
                day = (start + timedelta(days=offset)).isoformat()
                row = conn.execute(
                    """
                    SELECT
                        COUNT(DISTINCT CASE
                            WHEN user_id IS NOT NULL AND event_name NOT LIKE 'admin_%'
                            THEN user_id END) AS active_users,
                        COUNT(DISTINCT CASE
                            WHEN event_name='user_registered' THEN user_id END) AS new_users,
                        COUNT(DISTINCT CASE
                            WHEN event_name='share_opened' THEN user_id END) AS share_users,
                        COALESCE(SUM(CASE
                            WHEN event_name='reading_completed' THEN value ELSE 0 END), 0)
                            AS readings,
                        COALESCE(SUM(value), 0) AS events
                    FROM events WHERE local_date=?
                    """,
                    (day,),
                ).fetchone()
                output.append(
                    {
                        "date": day,
                        "active_users": int(row["active_users"]),
                        "new_users": int(row["new_users"]),
                        "share_users": int(row["share_users"]),
                        "readings": int(row["readings"]),
                        "events": int(row["events"]),
                    }
                )
        return output
