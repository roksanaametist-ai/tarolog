"""Tarot deck + auto-draw (from main.py)."""

from __future__ import annotations

import random
import re
from typing import Any, Optional

tarot_cards: dict[str, str] = {}


def build_deck() -> dict[str, str]:
    """Populate tarot_cards once — same names/order as Telegram main()."""
    if tarot_cards:
        return tarot_cards

    arcana_names = [
        "Дурак",
        "Маг",
        "Верховная Жрица",
        "Императрица",
        "Император",
        "Иерофант",
        "Влюбленные",
        "Колесница",
        "Сила",
        "Отшельник",
        "Колесо Фортуны",
        "Правосудие",
        "Повешенный",
        "Смерть",
        "Умеренность",
        "Дьявол",
        "Башня",
        "Звезда",
        "Луна",
        "Солнце",
        "Суд",
        "Мир",
    ]
    for i, name in enumerate(arcana_names, start=1):
        tarot_cards[f"static/card{i}.jpg"] = name

    wands_names = [
        "Туз Жезлов",
        "Двойка Жезлов",
        "Тройка Жезлов",
        "Четверка Жезлов",
        "Пятерка Жезлов",
        "Шестерка Жезлов",
        "Семерка Жезлов",
        "Восьмерка Жезлов",
        "Девятка Жезлов",
        "Десятка Жезлов",
        "Король Жезлов",
        "Королева Жезлов",
        "Рыцарь Жезлов",
        "Паж Жезлов",
    ]
    for i, name in enumerate(wands_names, start=23):
        tarot_cards[f"static/card{i}.jpg"] = name

    cups_names = [
        "Туз Кубков",
        "Двойка Кубков",
        "Тройка Кубков",
        "Четверка Кубков",
        "Пятерка Кубков",
        "Шестерка Кубков",
        "Семерка Кубков",
        "Восьмерка Кубков",
        "Девятка Кубков",
        "Десятка Кубков",
        "Король Кубков",
        "Королева Кубков",
        "Рыцарь Кубков",
        "Паж Кубков",
    ]
    for i, name in enumerate(cups_names, start=37):
        tarot_cards[f"static/card{i}.jpg"] = name

    swords_names = [
        "Туз Мечей",
        "Двойка Мечей",
        "Тройка Мечей",
        "Четверка Мечей",
        "Пятерка Мечей",
        "Шестерка Мечей",
        "Семерка Мечей",
        "Восьмерка Мечей",
        "Девятка Мечей",
        "Десятка Мечей",
        "Король Мечей",
        "Королева Мечей",
        "Рыцарь Мечей",
        "Паж Мечей",
    ]
    for i, name in enumerate(swords_names, start=51):
        tarot_cards[f"static/card{i}.jpg"] = name

    pentacles_names = [
        "Туз Пентаклей",
        "Двойка Пентаклей",
        "Тройка Пентаклей",
        "Четверка Пентаклей",
        "Пятерка Пентаклей",
        "Шестерка Пентаклей",
        "Семерка Пентаклей",
        "Восьмерка Пентаклей",
        "Девятка Пентаклей",
        "Десятка Пентаклей",
        "Король Пентаклей",
        "Королева Пентаклей",
        "Рыцарь Пентаклей",
        "Паж Пентаклей",
    ]
    for i, name in enumerate(pentacles_names, start=65):
        tarot_cards[f"static/card{i}.jpg"] = name

    return tarot_cards


def draw_random_tarot_card(exclude_paths: Optional[set] = None) -> dict[str, Any]:
    build_deck()
    exclude_paths = exclude_paths or set()
    available = [p for p in tarot_cards if p not in exclude_paths]
    if not available:
        available = list(tarot_cards.keys())
    path = random.choice(available)
    return {"path": path, "label": tarot_cards[path]}


def apply_card_orientation(
    card: dict[str, Any],
    *,
    reversed_enabled: bool,
    force_reversed: Optional[bool] = None,
) -> dict[str, Any]:
    out = dict(card)
    label = str(out.get("label") or "")
    label_clean = re.sub(r"\s*\(перевёрнут\w*\)\s*$", "", label, flags=re.I).strip()
    if force_reversed is not None:
        is_rev = bool(force_reversed)
    elif reversed_enabled and random.random() < 0.5:
        is_rev = True
    else:
        is_rev = False
    out["label"] = f"{label_clean} (перевёрнутая)" if is_rev else label_clean
    out["reversed"] = is_rev
    return out


def normalize_deck_card_path(path: str) -> str:
    path = str(path or "").replace("\\", "/")
    match = re.search(r"(static/card\d+\.jpg)", path, flags=re.I)
    if match:
        return match.group(1)
    base = path.rsplit("/", 1)[-1]
    if re.fullmatch(r"card\d+\.jpg", base, flags=re.I):
        return f"static/{base}"
    return path


def parse_comma_separated_cards(text: str) -> list[dict[str, Any]]:
    """Same matching rules as Telegram main.parse_comma_separated_cards."""
    build_deck()
    parts = [p.strip() for p in (text or "").split(",") if p.strip()]
    name_to_path = {name.lower(): path for path, name in tarot_cards.items()}
    aliases = {
        "жрец": "иерофант",
        "папа": "иерофант",
        "верховный жрец": "иерофант",
        "hierophant": "иерофант",
        "жрица": "верховная жрица",
        "жрица таро": "верховная жрица",
        "high priestess": "верховная жрица",
        "priestess": "верховная жрица",
    }
    cards: list[dict[str, Any]] = []
    for part in parts:
        key = aliases.get(part.lower().strip(), part.lower().strip())
        path = name_to_path.get(key)
        if not path:
            for name_key, card_path in name_to_path.items():
                if key == name_key or name_key.startswith(key) or key.startswith(name_key):
                    path = card_path
                    break
        if not path:
            for name_key, card_path in name_to_path.items():
                if len(key) >= 4 and (key in name_key or name_key in key):
                    path = card_path
                    break
        label = tarot_cards.get(path, part) if path else part
        cards.append({"path": path, "label": label})
    return cards


def cards_from_webapp_paths(paths: list) -> list[dict[str, Any]]:
    build_deck()
    cards: list[dict[str, Any]] = []
    for raw in paths:
        path = normalize_deck_card_path(str(raw))
        label = tarot_cards.get(path)
        if not label and path:
            label = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        cards.append({"path": path, "label": label or path})
    return cards


def draw_spread_cards(count: int, *, reversed_enabled: bool = False) -> list[dict[str, Any]]:
    build_deck()
    count = max(1, min(int(count), 10))
    used: set = set()
    cards: list[dict[str, Any]] = []
    for _ in range(count):
        card = draw_random_tarot_card(used)
        used.add(card["path"])
        cards.append(apply_card_orientation(card, reversed_enabled=reversed_enabled))
    return cards
