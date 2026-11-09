"""Deliver spreads the same way Telegram does: cards, text, then menu."""

from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Any, Optional

from . import config
from .client import api
from .deck import draw_spread_cards
from .economy import reading_history, user_data
from .keyboards import after_reading_kb, main_kb
from .llm import (
    clean_tarot_text,
    fetch_structured_reading,
    get_tarot_reading_structured,
    structured_is_complete,
)

logger = logging.getLogger(__name__)


def _esc(text: str) -> str:
    return html.escape(str(text or ""), quote=False)


async def reply(
    user_id: int,
    text: str,
    *,
    attachments: list | None = None,
    chat_id: int | None = None,
    fmt: str | None = "html",
) -> Any:
    return await api.send_message(
        text=text,
        user_id=user_id,
        chat_id=chat_id,
        attachments=attachments,
        format=fmt,
    )


def split_caption_and_body(card_label: str, interpretation: str, idx: int) -> tuple[str, str]:
    title = f"Карта {idx}: {card_label}"
    body = clean_tarot_text(interpretation)
    if body and len(title) + len(body) + 4 <= 1000:
        return f"{title}\n\n{body}", ""
    return title, body


async def _send_card(user_id: int, card: dict, caption: str) -> None:
    path = card.get("path") or ""
    if path and not os.path.isabs(path):
        rooted = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)
        if os.path.isfile(rooted):
            path = rooted
    token = None
    if path and os.path.isfile(path):
        try:
            token = await api.upload_media(path, "image")
        except Exception as exc:
            logger.warning("card image upload failed: %s", exc)
    if token:
        await reply(
            user_id,
            _esc(caption),
            attachments=[{"type": "image", "payload": {"token": token}}],
        )
        return
    await reply(user_id, _esc(caption), fmt=None)


async def deliver_structured_spread(
    user_id: int,
    question_text: str,
    cards: list[dict[str, Any]],
    card_roles: Optional[list[str]] = None,
    *,
    decrement_balance: bool = True,
    yes_no_mode: bool = False,
    role_labels_for_fallback: Optional[list[str]] = None,
    show_card_list_header: bool = True,
    compact_single_card: bool = False,
    kind: str = "ask",
) -> None:
    expected_n = len(cards)
    if expected_n == 0:
        await reply(user_id, "Не удалось распознать карты. Повторите ввод.", fmt=None)
        return

    question_text = (question_text or "").strip()
    if not question_text:
        question_text = "Что важно понять в моей текущей ситуации и какой следующий шаг?"

    if config.LLM_PUBLIC_STUB and user_id not in config.LLM_STUB_ALLOW_IDS:
        await reply(user_id, config.LLM_PUBLIC_STUB_TEXT, fmt=None)
        return

    await reply(user_id, "Происходит магия… Готовлю трактовку.", fmt=None)

    prompt = question_text
    if yes_no_mode:
        prompt += (
            "\n\nВажно: в поле summary сначала напиши однозначный ответ «Да» или «Нет» "
            "именно на вопрос пользователя, затем краткое пояснение по карте. "
            "Не пиши, что вопрос непонятен."
        )

    card_labels = [c["label"] for c in cards]
    structured = await fetch_structured_reading(prompt, card_labels, card_roles)
    reading_ok = structured_is_complete(structured, expected_n)
    if not reading_ok:
        try:
            structured = await get_tarot_reading_structured(
                prompt + "\n\nПОВТОР: верни полный JSON со всеми трактовками и summary.",
                card_labels,
                card_roles_in_order=card_roles,
            )
            reading_ok = structured_is_complete(structured, expected_n)
        except Exception as exc:
            logger.warning("Extra structured retry failed: %s", exc)

    if decrement_balance and reading_ok and user_data.should_decrement(user_id):
        user_data.decrement_user_questions(user_id)

    per_card = list(structured.get("card_interpretations") or [])
    while len(per_card) < expected_n:
        per_card.append("")
    for idx in range(expected_n):
        raw = clean_tarot_text(per_card[idx] if isinstance(per_card[idx], str) else "")
        if not raw:
            role = ""
            if card_roles and idx < len(card_roles) and card_roles[idx]:
                role = f" ({card_roles[idx]})"
            raw = (
                f"Карта «{cards[idx]['label']}»{role} по вопросу «{question_text}» "
                f"указывает на ключевой нюанс вашей ситуации. "
                f"Смотрите на итоговый ответ ниже — там собран вывод по всем картам."
            )
        per_card[idx] = raw

    summary = clean_tarot_text(structured.get("summary") or "")
    fallback_roles = role_labels_for_fallback or card_roles or []
    if expected_n > 1 and not summary:
        lines = []
        for i in range(expected_n):
            if i < len(fallback_roles) and fallback_roles[i]:
                lines.append(f"{fallback_roles[i]}: {per_card[i]}")
            else:
                lines.append(f"{i + 1}. {cards[i]['label']}: {per_card[i]}")
        summary = f"Итог по вопросу «{question_text}»:\n\n" + "\n\n".join(lines)
    if yes_no_mode and not summary and per_card and per_card[0].strip():
        summary = per_card[0].strip()

    try:
        reading_history.add(
            user_id,
            kind=("yesno" if yes_no_mode and kind == "ask" else kind),
            question=question_text,
            cards=card_labels,
            summary=summary or "",
        )
    except Exception as exc:
        logger.warning("reading history save failed: %s", exc)

    if show_card_list_header and not compact_single_card:
        names = "\n".join(f"{idx + 1}. {card['label']}" for idx, card in enumerate(cards))
        await reply(user_id, f"Выпавшие карты:\n{names}", fmt=None)

    for idx, card in enumerate(cards):
        caption, body = split_caption_and_body(card["label"], per_card[idx], idx + 1)
        await _send_card(user_id, card, caption)
        if body:
            await reply(user_id, body, fmt=None)
        if not compact_single_card:
            await asyncio.sleep(0.35)

    if yes_no_mode and summary:
        await reply(user_id, f"Ответ по раскладу:\n\n{summary}", fmt=None)
    elif expected_n > 1 and summary:
        await reply(user_id, f"Итоговый ответ по раскладу:\n\n{summary}", fmt=None)
    elif compact_single_card and summary and not yes_no_mode:
        await reply(user_id, summary, fmt=None)

    if not reading_ok:
        await reply(
            user_id,
            "Трактовка собрана с запасом: если ответ кажется слишком общим — "
            "задайте вопрос чуть конкретнее (кто/что/когда) и повторите расклад.",
            fmt=None,
        )

    await reply(
        user_id,
        "Расклад завершён. Нужна личная консультация — кнопка ниже.",
        attachments=after_reading_kb(),
        fmt=None,
    )
    await reply(user_id, "Выберите дальнейшее действие:", attachments=main_kb(user_id), fmt=None)


async def run_day_card(user_id: int, card: dict[str, Any]) -> None:
    await deliver_structured_spread(
        user_id,
        "Расклад «Карта дня». Опиши, как пройдёт сегодняшний день по выпавшей карте.",
        [card],
        decrement_balance=False,
        show_card_list_header=False,
        compact_single_card=True,
        kind="day",
    )


async def run_auto_spread(
    user_id: int,
    question: str,
    *,
    count: int | None = None,
    kind: str = "ask",
    yes_no_mode: bool = False,
    card_roles: Optional[list[str]] = None,
) -> None:
    """Kept for callers that still want an automatic draw."""
    n = count if count is not None else 1
    if yes_no_mode:
        n = 1
    cards = draw_spread_cards(n, reversed_enabled=False)
    await deliver_structured_spread(
        user_id,
        question,
        cards,
        card_roles=card_roles,
        yes_no_mode=yes_no_mode,
        kind=kind,
        show_card_list_header=not yes_no_mode,
        compact_single_card=yes_no_mode or n == 1,
    )
