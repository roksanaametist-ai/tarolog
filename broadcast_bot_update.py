#!/usr/bin/env python3
"""Broadcast: bot update (photo + caption)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from aiogram import Bot
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from dotenv import load_dotenv

APP_DIR = Path("/root/tarolog")
USER_DATA = APP_DIR / "user_data.json"
PHOTO = APP_DIR / "static" / "broadcast_referral_unlim.jpg"
BOT_LINK = "https://t.me/Roxanaametist_Taro_bot?start=update"

MESSAGE = (
    "🎉 Хорошие новости — бот обновился!\n\n"
    "Что нового:\n"
    "• «Живой расклад» — разбор с человеком, не с ботом. "
    "Кнопка рядом с «Бонусы», внутри форматы и цены\n"
    "• в «Классических раскладах» — «Деньги»: посмотри, где твоя точка роста!\n"
    "• «Прогноз недели» — тон, ловушка и ход с понедельника на воскресенье!\n"
    "• «Своя колода» — удобно отправить другу или в чат и делать расклад вместе: "
    "открывается прямо в сообщении.\n\n"
    "Чтобы появилось новое меню, нажмите «Старт» ниже\n"
    "(или напишите /start в чат с ботом)."
)


def load_user_ids() -> list[int]:
    with open(USER_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids: list[int] = []
    for k, raw in data.items():
        user = raw if isinstance(raw, dict) else {}
        if user.get("tg_blocked"):
            continue
        try:
            ids.append(int(k))
        except ValueError:
            continue
    return sorted(set(ids))


async def broadcast(user_ids: list[int]) -> tuple[int, int]:
    load_dotenv(APP_DIR / ".env")
    token = (os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit("TELEGRAM_TOKEN not found in .env")
    if not PHOTO.is_file():
        raise SystemExit(f"Photo missing: {PHOTO}")

    bot = Bot(token=token)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Старт — обновить меню", url=BOT_LINK)],
        ]
    )

    sent = 0
    failed = 0
    for i, chat_id in enumerate(user_ids, start=1):
        try:
            await bot.send_photo(
                chat_id,
                FSInputFile(str(PHOTO)),
                caption=MESSAGE,
                reply_markup=kb,
            )
            sent += 1
        except Exception as e:
            failed += 1
            if failed <= 25:
                print(f"fail {chat_id}: {type(e).__name__}: {e}", flush=True)
        if i % 25 == 0:
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(0.05)
        if i % 100 == 0:
            print(
                f"progress {i}/{len(user_ids)} sent={sent} failed={failed}",
                flush=True,
            )

    await bot.session.close()
    return sent, failed


def main() -> None:
    ids = load_user_ids()
    print(f"users={len(ids)} photo={PHOTO}", flush=True)
    sent, failed = asyncio.run(broadcast(ids))
    print(f"DONE sent={sent} failed={failed}", flush=True)
    if failed and sent == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
