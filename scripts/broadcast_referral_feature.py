#!/usr/bin/env python3
"""Одноразовая маркетинговая рассылка о реферальной лестнице.

Запуск на сервере:
  cd /root/tarolog && ./venv/bin/python scripts/broadcast_referral_feature.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from aiogram import Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("BOT_DATA_DIR", str(ROOT)))
if not DATA_DIR.exists():
    DATA_DIR = ROOT

USER_DATA = DATA_DIR / "user_data.json"
TOKEN = os.getenv("TELEGRAM_TOKEN")
# [fix-039] по умолчанию только просмотр; отправка — только с --send
DRY_RUN = "--send" not in sys.argv


def load_user_ids() -> list[int]:
    if not USER_DATA.exists():
        raise SystemExit(f"Нет файла {USER_DATA}")
    raw = json.loads(USER_DATA.read_text(encoding="utf-8"))
    ids = []
    for k in raw.keys():
        try:
            ids.append(int(k))
        except ValueError:
            continue
    return ids


def build_text(username: str, chat_id: int) -> str:
    link = f"https://t.me/{username}?start=ref_{chat_id}"
    return (
        "✨ Новая возможность в Follow the Frensy\n\n"
        "Теперь за друзей — щедрые бонусы:\n\n"
        "• друг зашёл по вашей ссылке → вам +5 раскладов, "
        "ему +3 в подарок\n"
        "• 3 друга сделали расклад → вам 3 дня безлимита\n"
        "• 10 активных друзей → вам месяц безлимита\n\n"
        "Активный друг — тот, кто хотя бы раз получил трактовку в боте.\n\n"
        f"Ваша личная ссылка:\n{link}\n\n"
        "Поделитесь с подругами, в семье, в чатах — "
        "и открывайте безлимит бесплатно.\n\n"
        "Кнопка в меню: «👥 Пригласить друзей» — там же ваш прогресс."
    )


async def main() -> None:
    if not TOKEN:
        raise SystemExit("Нет TELEGRAM_TOKEN")

    bot = Bot(token=TOKEN)
    from _broadcast_retry import install_retry_after  # [fix-039] FloodWait
    install_retry_after(bot)
    me = await bot.get_me()
    username = me.username
    ids = load_user_ids()
    print(f"Bot @{username}, users: {len(ids)}, dry_run={DRY_RUN}")

    sent = 0
    failed = 0
    for chat_id in ids:
        text = build_text(username, chat_id)
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(
                text="Открыть мою ссылку",
                url=f"https://t.me/{username}?start=ref_{chat_id}",
            )
        )
        if DRY_RUN:
            if sent < 2:
                print("--- sample ---")
                print(text)
            sent += 1
            continue
        try:
            await bot.send_message(chat_id, text, reply_markup=kb.as_markup())
            sent += 1
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"fail {chat_id}: {e}")
        await asyncio.sleep(0.05)

    await bot.session.close()
    print(f"Done. sent={sent} failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
