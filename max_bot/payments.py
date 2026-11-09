"""YooKassa tariffs — same prices, grants and auto-renew as Telegram."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from . import config
from .economy import order_manager, user_data
from .keyboards import main_kb, pay_link_kb, plans_kb
from .readings import reply

logger = logging.getLogger(__name__)

PLAN_LABELS = {
    "sub_10_169": "10 запросов — 169 ₽",
    "sub_7d_399": "Месяц безлимит — 359 ₽",
    "sub_14d_499": "3 месяца безлимит — 999 ₽",
    "sub_30d_699": "Год безлимит — 2999 ₽",
}
RECURRING_PLAN_KEYS = frozenset({"sub_7d_399", "sub_14d_499", "sub_30d_699"})
PLAN_PRICE_KOPECKS = {
    "sub_10_169": 16900,
    "sub_7d_399": 35900,
    "sub_14d_499": 99900,
    "sub_30d_699": 299900,
}
PLAN_DAYS = {
    "sub_7d_399": 31,
    "sub_14d_499": 93,
    "sub_30d_699": 365,
}
PRICE_TO_PLAN_KEY = {v: k for k, v in PLAN_PRICE_KOPECKS.items()}


def configure_yookassa() -> None:
    from yookassa import Configuration

    account_id = __import__("os").getenv("YOOKASSA_ACCOUNT_ID")
    secret_key = __import__("os").getenv("YOOKASSA_SECRET_KEY")
    if not account_id or not secret_key:
        raise ValueError("YOOKASSA_ACCOUNT_ID и YOOKASSA_SECRET_KEY должны быть заданы в окружении")
    Configuration.account_id = int(account_id)
    Configuration.secret_key = secret_key


def initialize_payment_file() -> None:
    path = config.PAYMENT_FILE
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"total_amount": 0, "subscriptions": {"10": 0, "30": 0, "7d": 0, "14d": 0, "30d": 0}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def update_payment_data(amount: int, subscription_type: str) -> None:
    initialize_payment_file()
    with open(config.PAYMENT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
    data["total_amount"] = int(data.get("total_amount", 0)) + int(amount)
    subs = data.setdefault("subscriptions", {})
    subs[subscription_type] = int(subs.get(subscription_type, 0)) + 1
    with open(config.PAYMENT_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)


def auto_renew_status_line(user_id: int) -> str:
    if user_data.is_auto_renew_enabled(user_id):
        plan = user_data.get_subscription_plan_key(user_id)
        label = PLAN_LABELS.get(plan or "", "подписка")
        return f"Автопродление: включено ({label})"
    if user_data.get_payment_method_id(user_id):
        return "Автопродление: выключено"
    return "Автопродление: не подключено"


def apply_subscription_payment(user_id: int, selected_price: int) -> bool:
    prices = {16900: "10", 35900: "31d", 99900: "93d", 299900: "365d"}
    selected_type = prices.get(int(selected_price))
    if not selected_type:
        return False
    if selected_type == "10":
        user_data.increment_user_questions(user_id, 10)
    elif selected_type == "31d":
        user_data.extend_subscription(user_id, days=31)
    elif selected_type == "93d":
        user_data.extend_subscription(user_id, days=93)
    elif selected_type == "365d":
        user_data.extend_subscription(user_id, days=365)
    else:
        return False
    update_payment_data(int(selected_price), selected_type)
    return True


def _payment_method_saved_id(zakaz) -> Optional[str]:
    try:
        pm = getattr(zakaz, "payment_method", None)
        if pm is None:
            return None
        if getattr(pm, "saved", False) and getattr(pm, "id", None):
            return str(pm.id)
    except Exception:
        return None
    return None


def activate_payment_success(user_id: int, selected_price: int, zakaz, *, plan_key: Optional[str] = None) -> bool:
    payment_id = str(getattr(zakaz, "id", "") or "")
    record = user_data._ensure(user_id)
    user_data._pull_wallet(user_id)
    if payment_id and record.get("last_yookassa_payment_id") == payment_id:
        return True
    if not apply_subscription_payment(user_id, int(selected_price)):
        return False
    if payment_id:
        user_data._commit_wallet(user_id, {"last_yookassa_payment_id": payment_id})
    plan_key = plan_key or PRICE_TO_PLAN_KEY.get(int(selected_price))
    if plan_key in RECURRING_PLAN_KEYS:
        pmid = _payment_method_saved_id(zakaz)
        if pmid:
            user_data.enable_auto_renew(
                user_id,
                payment_method_id=pmid,
                plan_key=plan_key,
                price_kopecks=int(selected_price),
            )
    return True


async def show_plans(user_id: int, *, intro: str | None = None) -> None:
    text = intro or (
        "Выбери актуальную подписку для себя:\n\n"
        "Безлимитные тарифы (месяц / 3 месяца / год) подключают автопродление: "
        "карта сохранится в ЮKassa, перед окончанием периода сумма спишется снова. "
        "Отменить автопродление можно кнопкой ниже."
        + config.REFERRAL_HINT
    )
    await reply(user_id, text, attachments=plans_kb(user_id), fmt=None)


async def start_payment(user_id: int, plan_key: str) -> None:
    email = user_data.get_user_email(user_id)
    if not email:
        await reply(
            user_id,
            "Для оплаты сначала укажите email через «💳 Оформить подписку».",
            attachments=main_kb(user_id),
            fmt=None,
        )
        return
    selected_price = PLAN_PRICE_KOPECKS.get(plan_key)
    if not selected_price:
        await reply(user_id, "Неизвестный тариф.", attachments=main_kb(user_id), fmt=None)
        return
    try:
        configure_yookassa()
    except (ValueError, TypeError) as exc:
        await reply(user_id, f"Оплата временно недоступна: {exc}", attachments=main_kb(user_id), fmt=None)
        return

    from yookassa import Payment

    order_manager.increment_order_number()
    amount_value = f"{int(selected_price / 100)}.00"
    save_method = plan_key in RECURRING_PLAN_KEYS
    payload = {
        "amount": {"value": amount_value, "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": config.MAX_PAYMENT_RETURN_URL},
        "description": PLAN_LABELS.get(plan_key, "Оплата подписки"),
        "metadata": {
            "order_id": f"{order_manager.get_order_number()}",
            "chat_id": str(user_id),
            "plan_key": plan_key,
            "selected_price": str(selected_price),
            "channel": "max",
        },
        "receipt": {
            "customer": {"email": email},
            "items": [
                {
                    "description": PLAN_LABELS.get(plan_key, "Подписка")[:128],
                    "quantity": 1,
                    "amount": {"value": amount_value, "currency": "RUB"},
                    "vat_code": 1,
                }
            ],
        },
    }
    if save_method:
        payload["save_payment_method"] = True
    payment = await asyncio.to_thread(Payment.create, payload, str(uuid.uuid4()))
    confirmation_url = payment.confirmation.confirmation_url
    renew_hint = ""
    if save_method:
        renew_hint = (
            "\n\nПосле оплаты карта сохранится для автопродления этого тарифа. "
            "Отменить автопродление можно в меню «💳 Оформить подписку»."
        )
    await reply(
        user_id,
        (
            f"Оплата: {PLAN_LABELS.get(plan_key, 'Подписка')}\n\n"
            "Нажмите кнопку ниже — откроется безопасная страница YooKassa."
            + renew_hint
            + config.REFERRAL_HINT
        ),
        attachments=pay_link_kb(confirmation_url),
        fmt=None,
    )
    asyncio.create_task(check_payment_status(payment.id, user_id, selected_price, plan_key))


async def check_payment_status(payment_id: str, user_id: int, selected_price: int, plan_key: str) -> None:
    from yookassa import Payment

    configure_yookassa()
    for _ in range(60):
        zakaz = await asyncio.to_thread(Payment.find_one, payment_id)
        if zakaz.status == "succeeded":
            if activate_payment_success(user_id, selected_price, zakaz, plan_key=plan_key):
                renew_note = ""
                if plan_key in RECURRING_PLAN_KEYS and user_data.is_auto_renew_enabled(user_id):
                    renew_note = (
                        "\n\nАвтопродление включено: перед окончанием периода сумма "
                        "спишется снова. Отменить — «💳 Оформить подписку» → "
                        "«Отменить автопродление»."
                    )
                elif plan_key in RECURRING_PLAN_KEYS:
                    renew_note = (
                        "\n\nПодписка выдана. Автопродление не удалось включить "
                        "(возможно, в ЮKassa не включены автоплатежи или способ оплаты "
                        "не поддерживает сохранение)."
                    )
                await reply(
                    user_id,
                    "Вам выдана подписка!" + renew_note + config.REFERRAL_HINT,
                    attachments=main_kb(user_id),
                    fmt=None,
                )
            return
        if zakaz.status == "canceled":
            await reply(user_id, "Оплата отменена." + config.REFERRAL_HINT, fmt=None)
            return
        await asyncio.sleep(10)
    await reply(
        user_id,
        "Оплата пока не поступила. Если вы уже оплатили — подписка активируется автоматически "
        "в течение нескольких минут.\n"
        "Или нажмите «💳 Оформить подписку» и откройте ссылку снова."
        + config.REFERRAL_HINT,
        fmt=None,
    )


async def charge_recurring_subscription(user_id: int) -> bool:
    from yookassa import Payment

    pmid = user_data.get_payment_method_id(user_id)
    plan_key = user_data.get_subscription_plan_key(user_id)
    price = user_data.get_subscription_price(user_id)
    email = user_data.get_user_email(user_id)
    if not pmid or not plan_key or not price or plan_key not in RECURRING_PLAN_KEYS or not email:
        return False
    configure_yookassa()
    amount_value = f"{int(price / 100)}.00"
    order_manager.increment_order_number()
    payment = await asyncio.to_thread(
        Payment.create,
        {
            "amount": {"value": amount_value, "currency": "RUB"},
            "capture": True,
            "payment_method_id": pmid,
            "description": f"Автопродление: {PLAN_LABELS.get(plan_key, 'подписка')}",
            "metadata": {
                "order_id": f"{order_manager.get_order_number()}",
                "chat_id": str(user_id),
                "plan_key": plan_key,
                "selected_price": str(price),
                "recurring": "1",
                "channel": "max",
            },
            "receipt": {
                "customer": {"email": email},
                "items": [
                    {
                        "description": PLAN_LABELS.get(plan_key, "Подписка")[:128],
                        "quantity": 1,
                        "amount": {"value": amount_value, "currency": "RUB"},
                        "vat_code": 1,
                    }
                ],
            },
        },
        str(uuid.uuid4()),
    )
    for _ in range(12):
        zakaz = await asyncio.to_thread(Payment.find_one, payment.id)
        if zakaz.status == "succeeded":
            days = PLAN_DAYS.get(plan_key, 31)
            user_data.extend_subscription(user_id, days=days)
            update_payment_data(price, {31: "31d", 93: "93d", 365: "365d"}.get(days, "31d"))
            user_data.clear_renew_failure(user_id)
            end = user_data.get_subscription_end(user_id)
            end_s = end.strftime("%d.%m.%Y") if end else "—"
            await reply(
                user_id,
                f"Автопродление прошло успешно ✨\n"
                f"Тариф: {PLAN_LABELS.get(plan_key)}\n"
                f"Подписка продлена до {end_s}.",
                attachments=main_kb(user_id),
                fmt=None,
            )
            return True
        if zakaz.status in ("canceled", "failed"):
            return False
        await asyncio.sleep(5)
    return False


async def handle_recurring_failure(user_id: int) -> None:
    record = user_data.data.get(str(user_id), {})
    fail_count = int(record.get("renew_fail_count", 0)) + 1
    if fail_count == 1:
        next_at = datetime.now() + timedelta(hours=12)
    elif fail_count == 2:
        next_at = datetime.now() + timedelta(hours=24)
    else:
        next_at = None
    user_data.set_renew_failure(user_id, fail_count=fail_count, next_renew_at=next_at)
    if fail_count >= 3:
        text = (
            "Не удалось списать оплату за автопродление (3 попытки).\n"
            "Автопродление выключено. Оформите подписку снова через «💳 Оформить подписку»."
        )
    else:
        text = (
            f"Не удалось списать оплату за автопродление (попытка {fail_count}/3).\n"
            "Проверьте карту или баланс. Следующая попытка будет автоматически.\n"
            "Отменить автопродление: «💳 Оформить подписку» → «Отменить автопродление»."
        )
    try:
        await reply(user_id, text, attachments=main_kb(user_id), fmt=None)
    except Exception:
        pass


async def recurring_billing_loop() -> None:
    await asyncio.sleep(90)
    while True:
        try:
            for user_id in user_data.iter_users_due_renewal():
                if not user_data.is_auto_renew_enabled(user_id):
                    continue
                try:
                    ok = await charge_recurring_subscription(user_id)
                    if not ok:
                        await handle_recurring_failure(user_id)
                except Exception as exc:
                    logger.warning("Recurring charge error user_id=%s: %s", user_id, exc)
                    try:
                        await handle_recurring_failure(user_id)
                    except Exception:
                        pass
                await asyncio.sleep(1)
        except Exception as exc:
            logger.warning("recurring_billing_loop tick failed: %s", exc)
        await asyncio.sleep(3600)
