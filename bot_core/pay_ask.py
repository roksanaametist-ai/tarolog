"""Text survey: would you pay for monthly unlimited, and how much."""

from __future__ import annotations

import re
from typing import Mapping

CAMPAIGN_ID = "pay-ask-text-15"
CALLBACK_GO = "payask_go"
REWARD_QUESTIONS = 15
MIN_TEXT_LEN = 3
ADMIN_PAGE_SIZE = 8

BUTTON_TEXT = "Написать и забрать +15"

BROADCAST_TEXT = (
    "Привет. Хочу понять, стоит ли включать оплату за безлимит.\n"
    "\n"
    "Напиши одним сообщением:\n"
    "• заплатил(а) бы за месяц безлимита — да или нет\n"
    "• и сколько ок в рублях\n"
    "\n"
    "Сейчас ориентир 359 ₽. Это не счёт и не оплата.\n"
    "\n"
    "За честный ответ начислим +15 раскладов — после того, как напишешь."
)

PROMPT_TEXT = (
    "Ок. Одним сообщением: платил(а) бы за месяц безлимита "
    "и сколько комфортно (ориентир 359 ₽).\n"
    "\n"
    "Можно коротко: «нет» / «да, 199» / «только если 99». "
    f"+{REWARD_QUESTIONS} придут сразу после ответа."
)

THANKS_TEXT = (
    f"Спасибо. Записала. +{REWARD_QUESTIONS} раскладов уже на балансе."
)

ALREADY_TEXT = "Ответ уже принят, бонус уже был."

_AMOUNT_RE = re.compile(r"(\d{1,5})")


def extract_amount(text: str) -> int | None:
    raw = (text or "").strip().lower()
    if not raw:
        return None
    if any(
        w in raw
        for w in ("не буду", "не буду платить", "бесплатно", "даром", "0 руб")
    ):
        return 0
    if raw in {"0", "нет", "не", "no"}:
        return 0
    found = _AMOUNT_RE.findall(raw.replace(" ", ""))
    if not found:
        found = _AMOUNT_RE.findall(raw)
    if not found:
        return None
    try:
        return int(found[0])
    except ValueError:
        return None


def format_admin(answers: Mapping[str, Mapping] | None, *, page: int = 1) -> str:
    items: list[tuple[str, Mapping]] = []
    if isinstance(answers, Mapping):
        for uid, rec in answers.items():
            if isinstance(rec, Mapping):
                items.append((str(uid), rec))
    items.sort(key=lambda pair: str(pair[1].get("at") or ""), reverse=True)
    total = len(items)
    amounts: list[int] = []
    granted = 0
    for _uid, rec in items:
        if rec.get("granted"):
            granted += 1
        amt = rec.get("amount")
        if amt is None:
            amt = extract_amount(str(rec.get("text") or ""))
        if isinstance(amt, int):
            amounts.append(amt)
    page = max(1, int(page or 1))
    start = (page - 1) * ADMIN_PAGE_SIZE
    chunk = items[start : start + ADMIN_PAGE_SIZE]
    pages = max(1, (total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE)
    lines = [
        f"Опрос оплаты текстом: {total} ответов, бонус выдан: {granted}",
        f"Страница {page}/{pages}",
        "",
    ]
    if amounts:
        paid = [n for n in amounts if n > 0]
        zeros = sum(1 for n in amounts if n == 0)
        lines.append(
            f"Суммы в тексте: {len(amounts)} шт. · "
            f"не/0: {zeros} · с цифрой>0: {len(paid)}"
        )
        if paid:
            paid_sorted = sorted(paid)
            mid = paid_sorted[len(paid_sorted) // 2]
            lines.append(
                f"Среди >0: мин {paid_sorted[0]} · медиана {mid} · "
                f"макс {paid_sorted[-1]}"
            )
        lines.append("")
    if not chunk:
        lines.append("Пока пусто.")
        return "\n".join(lines)
    for uid, rec in chunk:
        at = str(rec.get("at") or "")[:19]
        text = str(rec.get("text") or "").replace("\n", " ").strip()
        if len(text) > 280:
            text = text[:277] + "…"
        amt = rec.get("amount")
        amt_s = f" · ~{amt}₽" if isinstance(amt, int) else ""
        lines.append(f"• {uid} {at}{amt_s}\n  {text}")
    if page < pages:
        lines.append("")
        lines.append(f"Дальше: /payask {page + 1}")
    return "\n".join(lines)
