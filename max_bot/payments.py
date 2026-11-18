"""[049] Оплата в MAX через Робокассу — те же тарифы, что в Telegram (111 / 555 / 999 ₽ в месяц).

Разовая оплата, без автопродления. Подписку выдаёт сайт по ResultURL
(bot_core.robokassa_fulfill, ветка platform="max"); здесь — ссылка на оплату и запасная проверка.
"""

from __future__ import annotations

import asyncio
import json
import logging

from . import config
from .economy import order_manager, user_data
from .keyboards import main_kb, pay_link_kb, plans_kb
from .readings import reply

logger = logging.getLogger(__name__)

PLAN_LABELS = {
    "sub_m_111": "Месяц безлимит — 111 ₽",
    "sub_m_555": "Месяц безлимит — 555 ₽",
    "sub_m_999": "Месяц безлимит — 999 ₽",
}
PLAN_PRICE_KOPECKS = {
    "sub_m_111": 11100,
    "sub_m_555": 55500,
    "sub_m_999": 99900,
}

# Номера счетов MAX — в своём диапазоне, чтобы не пересекаться с Telegram в общем хранилище.
MAX_INV_BASE = 50_000_000
# Запасная проверка: 60 × 10 с; на 18-й и последней — спросить Робокассу про этот счёт.
POLL_ATTEMPTS = 60
POLL_INTERVAL = 10
OPSTATE_AT = (18, 59)


def initialize_payment_file() -> None:
    path = config.PAYMENT_FILE
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"total_amount": 0, "subscriptions": {}}, ensure_ascii=False), encoding="utf-8")


def auto_renew_status_line(user_id: int) -> str:
    if user_data.is_auto_renew_enabled(user_id):
        plan = user_data.get_subscription_plan_key(user_id)
        label = PLAN_LABELS.get(plan or "", "подписка")
        return f"Автопродление: включено ({label})"
    return "Оплата разовая, автопродления нет"


async def show_plans(user_id: int, *, intro: str | None = None) -> None:
    text = intro or (
        "Выберите тариф «Месяц безлимит» (31 день).\n\n"
        "Это разовая оплата через Робокассу: автопродления нет, карта для списаний не сохраняется."
        + config.REFERRAL_HINT
    )
    await reply(user_id, text, attachments=plans_kb(user_id), fmt=None)


def next_inv_id() -> int:
    """Свободный номер счёта MAX (проверка по общему хранилищу Робокассы)."""
    from bot_core import robokassa_store

    for _ in range(1000):
        order_manager.increment_order_number()
        inv_id = MAX_INV_BASE + int(order_manager.get_order_number())
        if robokassa_store.is_free(inv_id):
            return inv_id
        logger.error("Robokassa inv_id=%s already taken, skipping", inv_id)
    raise RuntimeError("no free Robokassa inv_id after 1000 attempts")


def create_checkout(user_id: int, plan_key: str) -> tuple[int, str]:
    """Счёт в хранилище + ссылка на оплату. Возвращает (inv_id, URL); ValueError — оплата не настроена."""
    from bot_core import robokassa, robokassa_store

    price = PLAN_PRICE_KOPECKS[plan_key]
    email = user_data.get_user_email(user_id) or None
    for _ in range(5):
        inv_id = next_inv_id()
        link = robokassa.build_payment_link(
            inv_id=inv_id,
            amount_rub=price // 100,
            description=PLAN_LABELS[plan_key],
            shp={"chat_id": str(int(user_id)), "plan": plan_key, "platform": "max"},
            email=email,
            recurring=False,
        )
        try:
            robokassa_store.put_pending(
                inv_id,
                chat_id=int(user_id),
                plan_key=plan_key,
                amount_kopecks=price,
                kind="parent",
                extra={"platform": "max"},
            )
        except robokassa_store.InvoiceExistsError:
            continue  # номер успели занять — берём следующий
        return inv_id, link.url
    raise RuntimeError("could not reserve Robokassa invoice")


async def start_payment(user_id: int, plan_key: str) -> None:
    if plan_key not in PLAN_PRICE_KOPECKS:
        # старые кнопки (sub_10_169 и др.) — показать актуальные тарифы
        await show_plans(user_id, intro="Тарифы обновились. Выбери подписку:" + config.REFERRAL_HINT)
        return
    try:
        inv_id, url = await asyncio.to_thread(create_checkout, user_id, plan_key)
    except Exception as exc:
        logger.warning("MAX robokassa checkout failed user=%s: %s", user_id, exc)
        await reply(
            user_id,
            "Оплата временно недоступна. Попробуйте чуть позже.",
            attachments=main_kb(user_id),
            fmt=None,
        )
        return
    await reply(
        user_id,
        (
            f"Оплата: {PLAN_LABELS[plan_key]}\n\n"
            "Нажмите кнопку ниже — откроется страница Робокассы. "
            "После оплаты подписка включится сама, сюда придёт сообщение.\n"
            "Оплата разовая, автопродления нет."
            + config.REFERRAL_HINT
        ),
        attachments=pay_link_kb(url),
        fmt=None,
    )
    asyncio.create_task(check_payment_status(inv_id, user_id))


async def check_payment_status(inv_id: int, user_id: int) -> None:
    """Запасная проверка. Основная выдача — по ResultURL на сайте."""
    from bot_core import robokassa, robokassa_fulfill, robokassa_store

    for attempt in range(POLL_ATTEMPTS):
        rec = await asyncio.to_thread(robokassa_store.get_invoice, inv_id)
        if rec and rec.get("status") != "paid" and attempt in OPSTATE_AT:
            # ResultURL мог не дойти — спросить Робокассу про этот счёт
            try:
                state = await asyncio.to_thread(robokassa.op_state, inv_id)
                if state is not None and state.paid:
                    await asyncio.to_thread(robokassa_fulfill.fulfill_invoice, inv_id, out_sum=state.out_sum)
                    rec = await asyncio.to_thread(robokassa_store.get_invoice, inv_id)
            except Exception as exc:
                logger.warning("robokassa opstate check failed inv=%s: %s", inv_id, exc)
        if rec and rec.get("status") == "paid":
            if not rec.get("notify_sent"):
                end = user_data.get_subscription_end(user_id)
                end_s = end.strftime("%d.%m.%Y") if end else "—"
                try:
                    await reply(
                        user_id,
                        f"Вам выдана подписка до {end_s}! Это разовая оплата, автопродления нет."
                        + config.REFERRAL_HINT,
                        attachments=main_kb(user_id),
                        fmt=None,
                    )
                    robokassa_store.mark_notify_sent(inv_id)
                except Exception:
                    pass
            return
        await asyncio.sleep(POLL_INTERVAL)
