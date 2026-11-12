#!/usr/bin/env python3
"""Broadcast: 3 invites → month unlimited (+ photo)."""
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
BOT_LINK = "https://t.me/Roxanaametist_Taro_bot?start=bonus"

MESSAGE = (
    "🎉 Хорошие новости!\n\n"
    "Теперь полный безлимит на месяц —\n"
    "просто пригласи 3 друзей в бота.\n\n"
    "Как получить:\n"
    "1) 🎁 Бонусы → ♾️ Безлимит за друзей\n"
    "2) Скопируй свою ссылку\n"
    "3) Когда 3 человека зайдут по ней — месяц безлимитных раскладов твой\n\n"
    "За каждого друга сразу +5 раскладов тебе\n"
    "(и +3 ему в подарок).\n\n"
    "Погнали ✨"
)


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
            [InlineKeyboardButton(text="♾️ Безлимит за друзей", url=BOT_LINK)],
            [
                InlineKeyboardButton(
                    text="✍️ Написать Роксане",
                    url="https://t.me/roxanaametist",
                )
            ],
        ]
    )

    sent = 0
    failed = 0
    for i, chat_id in enumerate(user_ids, start=1):
        try:
            photo = FSInputFile(str(PHOTO))
            await bot.send_photo(
                chat_id,
                photo,
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
    with open(USER_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids: list[int] = []
    for k in data.keys():
        try:
            ids.append(int(k))
        except ValueError:
            continue
    ids = sorted(set(ids))
    print(f"users={len(ids)} photo={PHOTO}", flush=True)
    sent, failed = asyncio.run(broadcast(ids))
    print(f"DONE sent={sent} failed={failed}", flush=True)
    if failed and sent == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
