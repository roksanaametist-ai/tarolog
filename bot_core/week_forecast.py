"""Weekly forecast helpers: ISO week id and human range label."""

from __future__ import annotations

from datetime import datetime, timedelta

WEEK_ROLES = ("Тон", "Ловушка", "Ход")

_MONTHS_RU = (
    "янв",
    "фев",
    "мар",
    "апр",
    "мая",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)


def iso_week_id(now: datetime | None = None) -> str:
    now = now or datetime.now()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_monday(now: datetime | None = None):
    now = now or datetime.now()
    return now.date() - timedelta(days=now.weekday())


def week_range_label(now: datetime | None = None) -> str:
    monday = week_monday(now)
    sunday = monday + timedelta(days=6)
    m1 = _MONTHS_RU[monday.month - 1]
    m2 = _MONTHS_RU[sunday.month - 1]
    if monday.month == sunday.month:
        return f"{monday.day}–{sunday.day} {m1}"
    return f"{monday.day} {m1} – {sunday.day} {m2}"


def week_forecast_question(now: datetime | None = None) -> str:
    span = week_range_label(now)
    return (
        f"Расклад «Прогноз недели» на {span}. Личного вопроса нет.\n"
        "Три позиции:\n"
        "1) Тон — чем пахнет неделя, какой это фон.\n"
        "2) Ловушка — чего не делать, не подписывать, не обещать.\n"
        "3) Ход — куда жать, один конкретный шаг.\n\n"
        "В summary ровно три короткие строки:\n"
        "Тон: …\n"
        "Не: …\n"
        "Да: …\n"
        "Каждая карта — 1–2 жёстких предложения, без воды."
    )
