"""Idle-balance expiry campaign: ping, then cut to 1 if no reading before deadline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

CAMPAIGN_ID = "idle-expire-keep1"
CALLBACK_ASK = "idle_ask"
BUTTON_ASK = "Спросить сейчас"
BUTTON_DAY = "Карта дня"
BUTTON_GIVE = "Дать погадать другому"
DAY_CALLBACK = "classic_go_day"
GIVE_CALLBACK = "more_referral"
KEEP_QUESTIONS = 1
MIN_QUESTIONS = 2
IDLE_DAYS = 14
SKIP_ADMIN_IDS = {491482483}
TZ_MSK = ZoneInfo("Europe/Moscow")
TZ_LOG = ZoneInfo("Europe/Berlin")  # bot datetime.now() on this VPS
DEADLINE_MSK = datetime(2026, 10, 1, 23, 59, 59, tzinfo=TZ_MSK)

BROADCAST_TEXT = (
    "У тебя ещё расклады в боте.\n"
    "\n"
    "Если до 1 октября, 23:59 МСК не задашь ни одного вопроса — "
    "спишем накопленное и оставим 1.\n"
    "Это не оплата и не штраф за молчание: просто не держим мёртвый запас.\n"
    "\n"
    "Один вопрос или карта дня — и ничего не сгорает.\n"
    "Сам не гадаешь — дай погадать другому."
)

CUT_TEXT = (
    "Дедлайн прошёл — накопленное списала, оставила 1 расклад.\n"
    "Можешь спросить сейчас."
)


def parse_log_at(raw: object) -> datetime | None:
    s = str(raw or "").strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            naive = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=TZ_LOG).astimezone(timezone.utc)
    return None


def parse_iso_utc(raw: object) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return parse_log_at(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def last_reading_map(items: Iterable[Mapping]) -> dict[int, datetime]:
    latest: dict[int, datetime] = {}
    for row in items:
        if not isinstance(row, Mapping):
            continue
        try:
            uid = int(row.get("user_id") or 0)
        except (TypeError, ValueError):
            continue
        if uid <= 0:
            continue
        dt = parse_log_at(row.get("at"))
        if dt and (uid not in latest or dt > latest[uid]):
            latest[uid] = dt
    return latest


def last_reading_utc(items: Iterable[Mapping], user_id: int) -> datetime | None:
    return last_reading_map(items).get(user_id)


def has_reading_since(items: Iterable[Mapping], user_id: int, since_utc: datetime) -> bool:
    for row in items:
        if not isinstance(row, Mapping):
            continue
        try:
            uid = int(row.get("user_id") or 0)
        except (TypeError, ValueError):
            continue
        if uid != user_id:
            continue
        dt = parse_log_at(row.get("at"))
        if dt and dt >= since_utc:
            return True
    return False


def _questions(user: Mapping) -> int:
    try:
        return int(user.get("questions") or 0)
    except (TypeError, ValueError):
        return 0


def _has_unlim(user: Mapping, now: datetime) -> bool:
    end = parse_log_at(user.get("subscription_end"))
    return bool(end and end > now)


def select_idle_recipients(
    users: Mapping,
    items: Iterable[Mapping],
    *,
    now: datetime | None = None,
    already_done: set[int] | None = None,
) -> list[int]:
    now_utc = now or datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=IDLE_DAYS)
    done = already_done or set()
    last_by_user = last_reading_map(items)
    ids: list[int] = []
    for raw_id, raw_user in users.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in done or user_id in SKIP_ADMIN_IDS:
            continue
        user = raw_user if isinstance(raw_user, Mapping) else {}
        if bool(user.get("tg_blocked")):
            continue
        if _has_unlim(user, now_utc):
            continue
        if _questions(user) < MIN_QUESTIONS:
            continue
        last = last_by_user.get(user_id)
        if last is None or last >= cutoff:
            continue
        ids.append(user_id)
    return sorted(set(ids))
