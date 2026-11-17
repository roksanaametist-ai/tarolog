"""[fix-039] Общая защита рассылок от FloodWait (TelegramRetryAfter).

Подключение — одна строка после создания бота:
    install_retry_after(bot)
Если Telegram просит подождать, ждём retry_after (+1 с) и повторяем запрос (до 3 раз).
"""
from __future__ import annotations

import asyncio
import logging

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramRetryAfter

MAX_RETRIES = 3


class RetryAfterMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        attempt = 0
        while True:
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as exc:
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise
                wait = int(getattr(exc, "retry_after", 1) or 1) + 1
                logging.warning("FloodWait: ждём %s с (попытка %s)", wait, attempt)
                await asyncio.sleep(wait)


def install_retry_after(bot) -> None:
    bot.session.middleware(RetryAfterMiddleware())
