from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
SEGMENTS = {"inactive", "zero-balance", "lapsed", "checkout-abandoned"}


@dataclass(frozen=True)
class WinbackCandidate:
    user_id: int
    last_activity: datetime
    segment: str


def parse_bot_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MOSCOW)
    return parsed.astimezone(timezone.utc)


def _active_subscription(user: Mapping[str, Any], now: datetime) -> bool:
    end = parse_bot_datetime(user.get("subscription_end"))
    return bool(end and end > now)


def select_winback_candidates(
    *,
    users: Mapping[str, Any],
    agreements: Mapping[str, Any],
    nurture: Mapping[str, Any],
    last_activity: Mapping[int, datetime],
    already_sent: set[int],
    segment: str,
    inactive_days: int,
    now: datetime | None = None,
) -> list[WinbackCandidate]:
    if segment not in SEGMENTS:
        raise ValueError(f"unknown segment: {segment}")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    inactivity_cutoff = current - timedelta(days=max(1, int(inactive_days)))
    candidates: list[WinbackCandidate] = []

    for raw_user_id, raw_user in users.items():
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in already_sent:
            continue
        user = raw_user if isinstance(raw_user, Mapping) else {}
        if not bool(agreements.get(str(user_id))):
            continue
        if bool(user.get("tg_blocked")):
            continue

        fallback = parse_bot_datetime(
            user.get("last_activity_at")
            or (user.get("last_share_pack") or {}).get("at")
            or user.get("last_refill_at")
        )
        activity = last_activity.get(user_id) or fallback
        if activity is None:
            continue
        if activity.tzinfo is None:
            activity = activity.replace(tzinfo=timezone.utc)
        activity = activity.astimezone(timezone.utc)

        eligible = False
        if segment == "inactive":
            eligible = activity <= inactivity_cutoff
        elif segment == "zero-balance":
            eligible = (
                int(user.get("questions") or 0) <= 0
                and not _active_subscription(user, current)
                and activity <= inactivity_cutoff
            )
        elif segment == "lapsed":
            subscription_end = parse_bot_datetime(user.get("subscription_end"))
            eligible = bool(
                subscription_end
                and current - timedelta(days=90) <= subscription_end <= current
                and activity <= inactivity_cutoff
            )
        elif segment == "checkout-abandoned":
            record = nurture.get(str(user_id))
            record = record if isinstance(record, Mapping) else {}
            created_at = parse_bot_datetime(record.get("created_at"))
            eligible = bool(
                record
                and not record.get("completed")
                and record.get("stage") == "checkout"
                and created_at
                and current - timedelta(days=14) <= created_at <= current - timedelta(hours=1)
            )

        if eligible:
            candidates.append(
                WinbackCandidate(
                    user_id=user_id,
                    last_activity=activity,
                    segment=segment,
                )
            )

    return sorted(candidates, key=lambda item: (item.last_activity, item.user_id))


def winback_message(segment: str) -> str:
    messages = {
        "inactive": (
            "Карты снова готовы подсветить то, что сейчас важно ✨\n\n"
            "Если появился новый вопрос, можно продолжить с личного расклада."
        ),
        "zero-balance": (
            "Можно вернуться к картам без покупки ✨\n\n"
            "Карта дня даёт дополнительный расклад, а бонусы доступны в меню бота."
        ),
        "lapsed": (
            "Ваш период безлимитных раскладов завершился.\n\n"
            "Вернитесь, чтобы посмотреть доступные расклады и актуальные варианты доступа."
        ),
        "checkout-abandoned": (
            "Вы остановились перед оформлением подписки.\n\n"
            "Можно вернуться в бот, проверить доступные варианты или продолжить бесплатно."
        ),
    }
    if segment not in messages:
        raise ValueError(f"unknown segment: {segment}")
    return messages[segment]
