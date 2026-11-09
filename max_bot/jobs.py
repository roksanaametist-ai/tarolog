"""Background jobs that mirror the Telegram bot, on MAX user ids."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import shared_wallet

from . import config
from .economy import status_data, user_data
from .readings import reply

logger = logging.getLogger(__name__)


async def periodic_30day_refill() -> None:
    """+5 every 30 days for users who confirmed the channel from MAX.

    Telegram checks chat membership. MAX cannot see a Telegram channel,
    so the bonus follows the same «Я подписан» claim stored in status_data.
    """
    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        for key in list(user_data.data.keys()):
            if not str(key).isdigit():
                continue
            user_id = int(key)
            try:
                last_refill = user_data.get_last_refill_at(user_id)
                if last_refill is None:
                    user_data.set_last_refill_at(user_id, now)
                    continue
                delta_days = (now.date() - last_refill.date()).days
                if delta_days < 30:
                    continue
                if not status_data.is_subscribed_claim(user_id):
                    if shared_wallet.peer("max", user_id):
                        continue
                    user_data.set_last_refill_at(user_id, now)
                    record = user_data._ensure(user_id)
                    if record.get("refill_notice_on") != today:
                        user_data._commit_wallet(user_id, {"refill_notice_on": today})
                        await reply(
                            user_id,
                            "Чтобы получать ежемесячное пополнение (+5 вопросов каждые 30 дней), "
                            f"подпишитесь на канал:\n{config.CHANNEL_URL}",
                            fmt=None,
                        )
                    continue
                add_amount = shared_wallet.grant_periods(
                    "max",
                    user_id,
                    user_data.data.get(str(user_id)),
                    period_days=30,
                    per_period=5,
                )
                if add_amount <= 0:
                    continue
                shared_wallet.mirror(
                    user_data.data.get(str(user_id)),
                    shared_wallet.view("max", user_id, user_data.data.get(str(user_id))),
                )
                user_data.save_data()
                await reply(
                    user_id,
                    f"Вам начислено {add_amount} вопросов (пополнение раз в 30 дней).",
                    fmt=None,
                )
            except Exception as exc:
                logger.warning("refill failed for %s: %s", user_id, exc)
        await asyncio.sleep(86400)
