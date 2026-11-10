"""Monthly price-poll options and vote tally."""

from __future__ import annotations

from collections import Counter
from typing import Mapping

CAMPAIGN_ID = "price-poll-month"
CALLBACK_PREFIX = "ppoll:"

# (code, button label) — месяц безлимита. Сейчас в боте 359 ₽.
CHOICES: tuple[tuple[str, str], ...] = (
    ("99", "99 ₽"),
    ("149", "149 ₽"),
    ("199", "199 ₽"),
    ("249", "249 ₽"),
    ("299", "299 ₽"),
    ("359", "359 ₽ как сейчас"),
    ("499", "499 ₽"),
    ("0", "Не буду платить"),
)

CHOICE_LABELS = {code: label for code, label in CHOICES}

QUESTION = (
    "Сколько ок платить в месяц за безлимит раскладов?\n\n"
    "Сейчас месяц — 359 ₽.\n"
    "Это не оплата, один тап — просто сказать комфортную сумму."
)

THANKS = "Записала. Спасибо — на цену посмотрим по всем ответам."


def parse_choice(callback_data: str) -> str | None:
    raw = str(callback_data or "")
    if not raw.startswith(CALLBACK_PREFIX):
        return None
    code = raw[len(CALLBACK_PREFIX) :].strip()
    return code if code in CHOICE_LABELS else None


def tally_votes(votes: Mapping[str, Mapping] | None) -> list[tuple[str, str, int]]:
    counts: Counter[str] = Counter()
    if isinstance(votes, Mapping):
        for raw in votes.values():
            if not isinstance(raw, Mapping):
                continue
            code = str(raw.get("choice") or "")
            if code in CHOICE_LABELS:
                counts[code] += 1
    rows: list[tuple[str, str, int]] = []
    for code, label in CHOICES:
        rows.append((code, label, int(counts.get(code, 0))))
    return rows


def format_results(votes: Mapping[str, Mapping] | None) -> str:
    rows = tally_votes(votes)
    total = sum(n for _c, _l, n in rows)
    lines = [f"Опрос цены (месяц безлимит), голосов: {total}", ""]
    for _code, label, n in rows:
        pct = f" ({100 * n / total:.0f}%)" if total else ""
        lines.append(f"• {label}: {n}{pct}")
    return "\n".join(lines)
