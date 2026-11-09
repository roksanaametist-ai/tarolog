#!/usr/bin/env python3
"""Wire Robokassa pay button into rolled-back prod main.py (in place)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PLANS_BLOCK = '''PLAN_LABELS = {
    "sub_m_111": "Месяц безлимит — 111 ₽",
    "sub_m_555": "Месяц безлимит — 555 ₽",
    "sub_m_999": "Месяц безлимит — 999 ₽",
    # legacy YooKassa keys (не показываем в меню)
    "sub_10_169": "10 запросов — 169 ₽",
    "sub_7d_399": "Месяц безлимит — 359 ₽",
    "sub_14d_499": "3 месяца безлимит — 999 ₽",
    "sub_30d_699": "Год безлимит — 2999 ₽",
}

# Безлимитные тарифы с автопродлением (Robokassa Recurring)
RECURRING_PLAN_KEYS = frozenset({"sub_m_111", "sub_m_555", "sub_m_999", "sub_7d_399", "sub_14d_499", "sub_30d_699"})

PLAN_PRICE_KOPECKS = {
    "sub_m_111": 11100,
    "sub_m_555": 55500,
    "sub_m_999": 99900,
    "sub_10_169": 16900,
    "sub_7d_399": 35900,
    "sub_14d_499": 99900,
    "sub_30d_699": 299900,
}

PLAN_DAYS = {
    "sub_m_111": 31,
    "sub_m_555": 31,
    "sub_m_999": 31,
    "sub_7d_399": 31,
    "sub_14d_499": 93,
    "sub_30d_699": 365,
}

PRICE_TO_PLAN_KEY = {
    11100: "sub_m_111",
    55500: "sub_m_555",
    99900: "sub_m_999",
    16900: "sub_10_169",
    35900: "sub_7d_399",
    299900: "sub_30d_699",
}
'''

PAYMENT_PROVIDER_BLOCK = '''# 0 = оплата выкл (подписка через приглашения). 1 = включить оплату.
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PAYMENT_PROVIDER = (os.getenv("PAYMENT_PROVIDER") or "robokassa").strip().lower()
'''

USERDATA_HELPERS = '''
    def get_robokassa_prev_invoice_id(self, chat_id: int) -> Optional[int]:
        with self._lock:
            self._refresh_wallet_from_store()
            val = self.data.get(str(chat_id), {}).get("robokassa_prev_invoice_id")
            try:
                return int(val) if val is not None else None
            except (TypeError, ValueError):
                return None

    def get_payment_provider(self, chat_id: int) -> Optional[str]:
        with self._lock:
            self._refresh_wallet_from_store()
            val = self.data.get(str(chat_id), {}).get("payment_provider")
            return str(val) if val else None
'''

ROBOKASSA_FUNCS = r'''
async def _start_robokassa_checkout(
    chat_id: int,
    plan_key: str,
    selected_price: int,
    email: str,
) -> None:
    from bot_core import robokassa, robokassa_store

    if not robokassa.is_configured():
        raise ValueError("Robokassa не настроена (LOGIN/PASSWORD1/PASSWORD2)")

    order_manager.increment_order_number()
    inv_id = int(order_manager.get_order_number())
    amount_rub = int(selected_price) / 100.0
    shp = {"chat_id": str(chat_id), "plan": plan_key}
    use_recurring = robokassa.recurring_enabled()
    link = robokassa.build_payment_link(
        inv_id=inv_id,
        amount_rub=amount_rub,
        description=PLAN_LABELS.get(plan_key, "Подписка"),
        shp=shp,
        email=email,
        recurring=use_recurring,
    )
    robokassa_store.put_pending(
        inv_id,
        chat_id=chat_id,
        plan_key=plan_key,
        amount_kopecks=int(selected_price),
        kind="parent",
    )
    payment_nurture.set_checkout(
        chat_id,
        payment_id=str(inv_id),
        confirmation_url=link.url,
        plan_key=plan_key,
        selected_price=selected_price,
    )

    pay_kb = InlineKeyboardBuilder()
    pay_kb.row(types.InlineKeyboardButton(text="💳 Оплатить сейчас", url=link.url))
    pay_kb.row(types.InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="nurture_referral"))
    pay_kb.row(types.InlineKeyboardButton(text=BACK_BUTTON_TEXT, callback_data="back_to_main"))
    if use_recurring:
        renew_note = (
            "\n\nКарта сохранится для автопродления. "
            "Отменить — в меню «💳 Оформить подписку»."
        )
    else:
        renew_note = (
            "\n\nСейчас это разовая оплата на месяц "
            "(автопродление включим после одобрения Robokassa)."
        )
    await bot.send_message(
        chat_id,
        text=(
            f"Оплата: {PLAN_LABELS.get(plan_key, 'Подписка')}\n\n"
            "Нажмите кнопку ниже — откроется безопасная страница Robokassa.\n"
            "После оплаты безлимит на месяц включится автоматически."
            + renew_note
            + REFERRAL_HINT
        ),
        reply_markup=pay_kb.as_markup(),
    )
    asyncio.create_task(
        check_robokassa_payment_status(inv_id, chat_id, selected_price, plan_key=plan_key)
    )


async def check_robokassa_payment_status(
    inv_id: int,
    chat_id: int,
    selected_price: int,
    plan_key: Optional[str] = None,
) -> None:
    """Backup poll: ResultURL is primary; here we detect grant and avoid duplicate notify."""
    from bot_core import robokassa_store

    del selected_price, plan_key
    for _ in range(60):
        rec = robokassa_store.get_invoice(inv_id)
        if rec and rec.get("status") == "paid":
            # подтянуть грант из sqlite/json (ResultURL пишет в store)
            with user_data._lock:
                user_data._refresh_wallet_from_store()
            if not rec.get("notify_sent"):
                end = user_data.get_subscription_end(chat_id)
                end_s = end.strftime("%d.%m.%Y") if end else "—"
                renew_note = (
                    "\n\nАвтопродление включено. Отменить — «💳 Оформить подписку» → "
                    "«Отменить автопродление»."
                )
                try:
                    await bot.send_message(
                        chat_id,
                        f"Вам выдана подписка до {end_s}!" + renew_note + REFERRAL_HINT,
                        reply_markup=main_kb(chat_id),
                    )
                    robokassa_store.mark_notify_sent(inv_id)
                except Exception:
                    pass
            return
        await asyncio.sleep(10)

    await bot.send_message(
        chat_id,
        "Оплата пока не поступила. Если вы уже оплатили — подписка активируется автоматически "
        "после уведомления от Robokassa (обычно до минуты).\n"
        "Или нажмите «💳 Оформить подписку» и откройте ссылку снова."
        + REFERRAL_HINT,
    )


'''


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"marker not found: {label}")
    return text.replace(old, new, 1)


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "async def _start_robokassa_checkout" in text and 'callback_data="sub_m_111"' in text:
        print(f"already patched: {path}")
        return

    # Plans
    text = re.sub(
        r"PLAN_LABELS = \{.*?PRICE_TO_PLAN_KEY = \{.*?\n\}",
        PLANS_BLOCK.strip(),
        text,
        count=1,
        flags=re.S,
    )

    # PAYMENTS_ENABLED + PROVIDER
    text = re.sub(
        r"# 0 = ЮKassa выкл \(подписка через приглашения\)\. 1 = снова включить оплату\.\n"
        r"PAYMENTS_ENABLED = os\.getenv\(\"PAYMENTS_ENABLED\", \"0\"\)\.strip\(\)\.lower\(\) in \{\n"
        r"    \"1\",\n"
        r"    \"true\",\n"
        r"    \"yes\",\n"
        r"    \"on\",\n"
        r"\}",
        PAYMENT_PROVIDER_BLOCK.strip(),
        text,
        count=1,
    )

    # get_subscription_end refresh
    old_get_sub = '''    def get_subscription_end(self, chat_id: int) -> Optional[datetime]:
        end_time_str = self.data.get(str(chat_id), {}).get('subscription_end')
        if end_time_str:
            return datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
        return None'''
    new_get_sub = '''    def get_subscription_end(self, chat_id: int) -> Optional[datetime]:
        with self._lock:
            self._refresh_wallet_from_store()
            end_time_str = self.data.get(str(chat_id), {}).get('subscription_end')
            if end_time_str:
                return datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
            return None'''
    text = must_replace(text, old_get_sub, new_get_sub, "get_subscription_end")

    # helpers after get_payment_method_id
    old_pmid = '''    def get_payment_method_id(self, chat_id: int) -> Optional[str]:
        val = self.data.get(str(chat_id), {}).get("yookassa_payment_method_id")
        return str(val) if val else None

    def get_subscription_plan_key(self, chat_id: int) -> Optional[str]:'''
    new_pmid = '''    def get_payment_method_id(self, chat_id: int) -> Optional[str]:
        with self._lock:
            self._refresh_wallet_from_store()
            val = self.data.get(str(chat_id), {}).get("yookassa_payment_method_id")
            return str(val) if val else None
''' + USERDATA_HELPERS + '''
    def get_subscription_plan_key(self, chat_id: int) -> Optional[str]:'''
    text = must_replace(text, old_pmid, new_pmid, "payment helpers")

    # iter_users_due_renewal — include robokassa
    old_due = '''            if not u.get("auto_renew"):
                continue
            if not u.get("yookassa_payment_method_id"):
                continue'''
    new_due = '''            if not u.get("auto_renew"):
                continue
            provider = (u.get("payment_provider") or PAYMENT_PROVIDER or "").lower()
            has_method = bool(u.get("yookassa_payment_method_id"))
            has_robo = bool(u.get("robokassa_prev_invoice_id"))
            if provider == "robokassa":
                if not has_robo:
                    continue
            elif not has_method and not has_robo:
                continue'''
    text = must_replace(text, old_due, new_due, "iter_users_due_renewal")

    # apply_subscription_payment prices
    old_prices = '''    prices = {16900: "10", 35900: "31d", 99900: "93d", 299900: "365d"}'''
    new_prices = '''    prices = {
        11100: "31d",
        55500: "31d",
        99900: "31d",
        16900: "10",
        35900: "31d",
        299900: "365d",
    }'''
    text = must_replace(text, old_prices, new_prices, "apply_subscription_payment")

    # try_complete_pending_payment — robokassa branch first
    old_try = '''async def try_complete_pending_payment(chat_id: int, rec: dict) -> bool:
    payment_id = rec.get("payment_id")
    selected_price = rec.get("selected_price")
    plan_key = rec.get("plan_key")
    if not payment_id or not selected_price:
        return False
    try:
        configure_yookassa()
        zakaz = Payment.find_one(payment_id)'''
    new_try = '''async def try_complete_pending_payment(chat_id: int, rec: dict) -> bool:
    payment_id = rec.get("payment_id")
    selected_price = rec.get("selected_price")
    plan_key = rec.get("plan_key")
    if not payment_id or not selected_price:
        return False

    if PAYMENT_PROVIDER == "robokassa" or str(payment_id).isdigit():
        try:
            from bot_core import robokassa_store

            inv = robokassa_store.get_invoice(int(payment_id))
            if inv and inv.get("status") == "paid":
                with user_data._lock:
                    user_data._refresh_wallet_from_store()
                if user_has_active_subscription(chat_id):
                    payment_nurture.mark_completed(chat_id)
                    if not inv.get("notify_sent"):
                        end = user_data.get_subscription_end(chat_id)
                        end_s = end.strftime("%d.%m.%Y") if end else "—"
                        await bot.send_message(
                            chat_id,
                            f"Оплата прошла успешно! Безлимит до {end_s} 🎉"
                            "\\n\\nАвтопродление включено. Отменить — в меню «💳 Оформить подписку»."
                            + REFERRAL_HINT,
                            reply_markup=main_kb(chat_id),
                        )
                        robokassa_store.mark_notify_sent(int(payment_id))
                    return True
        except Exception:
            pass
        if PAYMENT_PROVIDER == "robokassa":
            return False

    try:
        configure_yookassa()
        zakaz = Payment.find_one(payment_id)'''
    text = must_replace(text, old_try, new_try, "try_complete_pending_payment")

    # charge_recurring — prepend robokassa
    old_charge = '''async def charge_recurring_subscription(chat_id: int) -> bool:
    """Безакцептное списание по сохранённому способу оплаты. True = успех."""
    pmid = user_data.get_payment_method_id(chat_id)
    plan_key = user_data.get_subscription_plan_key(chat_id)
    price = user_data.get_subscription_price(chat_id)
    email = user_data.get_user_email(chat_id)
    if not pmid or not plan_key or not price or plan_key not in RECURRING_PLAN_KEYS:
        return False
    if not email:
        logging.warning("Recurring charge skipped: no email for chat_id=%s", chat_id)
        return False

    configure_yookassa()'''
    new_charge = '''async def charge_recurring_subscription(chat_id: int) -> bool:
    """Безакцептное списание. True = успех (или Robokassa Recurring принят — грант через ResultURL)."""
    plan_key = user_data.get_subscription_plan_key(chat_id)
    price = user_data.get_subscription_price(chat_id)
    email = user_data.get_user_email(chat_id)
    provider = (user_data.get_payment_provider(chat_id) or PAYMENT_PROVIDER or "").lower()
    if not plan_key or not price or plan_key not in RECURRING_PLAN_KEYS:
        return False

    if provider == "robokassa" or (
        user_data.get_robokassa_prev_invoice_id(chat_id) and provider != "yookassa"
    ):
        from bot_core import robokassa, robokassa_store

        prev = user_data.get_robokassa_prev_invoice_id(chat_id)
        if not prev:
            logging.warning("Robokassa recurring skipped: no prev invoice chat_id=%s", chat_id)
            return False
        order_manager.increment_order_number()
        inv_id = int(order_manager.get_order_number())
        amount_rub = int(price) / 100.0
        shp = {"chat_id": str(chat_id), "plan": plan_key}
        robokassa_store.put_pending(
            inv_id,
            chat_id=chat_id,
            plan_key=plan_key,
            amount_kopecks=int(price),
            kind="child",
            parent_inv_id=prev,
        )
        try:
            body = await asyncio.to_thread(
                robokassa.request_recurring,
                inv_id=inv_id,
                previous_invoice_id=prev,
                amount_rub=amount_rub,
                description=f"Автопродление: {PLAN_LABELS.get(plan_key, 'подписка')}",
                shp=shp,
            )
        except Exception as e:
            logging.warning("Robokassa recurring request failed chat_id=%s: %s", chat_id, e)
            return False
        if "OK" in (body or "").upper():
            user_data.clear_renew_failure(chat_id)
            return True
        logging.warning("Robokassa recurring unexpected body chat_id=%s: %s", chat_id, body)
        return False

    pmid = user_data.get_payment_method_id(chat_id)
    if not pmid:
        return False
    if not email:
        logging.warning("Recurring charge skipped: no email for chat_id=%s", chat_id)
        return False

    configure_yookassa()'''
    text = must_replace(text, old_charge, new_charge, "charge_recurring")

    # open_subscription_menu intro
    old_intro = '''    intro = (
        "Выбери актуальную подписку для себя:\\n\\n"
        "Безлимитные тарифы (месяц / 3 месяца / год) подключают автопродление: "
        "карта сохранится в ЮKassa, перед окончанием периода сумма спишется снова. "
        "Отменить автопродление можно кнопкой ниже."
        + REFERRAL_HINT
    )'''
    new_intro = '''    intro = (
        "Выбери тариф на месяц безлимита:\\n\\n"
        "111 / 555 / 999 ₽ — один месяц безлимита. "
        "После оплаты карта сохранится для автопродления; "
        "отменить можно кнопкой ниже."
        + REFERRAL_HINT
    )'''
    text = must_replace(text, old_intro, new_intro, "open_subscription_menu intro")

    # sub() buttons
    old_sub = '''def sub(chat_id: Optional[int] = None):
    sub1 = types.InlineKeyboardButton(text='10 запросов - 169 руб.', callback_data="sub_10_169")
    sub3 = types.InlineKeyboardButton(text='Месяц (безлимит) - 359 руб.', callback_data="sub_7d_399")
    sub4 = types.InlineKeyboardButton(text='3 Месяца (безлимит) - 999 руб.', callback_data="sub_14d_499")
    sub5 = types.InlineKeyboardButton(text='Год (безлимит) - 2999 руб.', callback_data="sub_30d_699")

    markup = InlineKeyboardBuilder()
    markup.row(sub1)
    markup.row(sub3)
    markup.row(sub4)
    markup.row(sub5)'''
    new_sub = '''def sub(chat_id: Optional[int] = None):
    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Месяц безлимит — 111 ₽", callback_data="sub_m_111"))
    markup.row(types.InlineKeyboardButton(text="Месяц безлимит — 555 ₽", callback_data="sub_m_555"))
    markup.row(types.InlineKeyboardButton(text="Месяц безлимит — 999 ₽", callback_data="sub_m_999"))'''
    text = must_replace(text, old_sub, new_sub, "sub()")

    # Replace submonth body after email check
    old_submonth_tail = '''    try:
        configure_yookassa()
    except (ValueError, TypeError) as e:
        await bot.send_message(chat_id, f"Оплата временно недоступна: {e}", reply_markup=back_kb())
        await call.answer()
        return

    order_manager.increment_order_number()

    amount_value = f"{int(selected_price / 100)}.00"
    save_method = plan_key in RECURRING_PLAN_KEYS
    payment_payload = {
        "amount": {
            "value": amount_value,
            "currency": "RUB"
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": BOT_RETURN_URL
        },
        "description": PLAN_LABELS.get(plan_key, "Оплата подписки"),
        "metadata": {
            "order_id": f"{order_manager.get_order_number()}",
            "chat_id": str(chat_id),
            "plan_key": plan_key,
            "selected_price": str(selected_price),
        },
        "receipt": {
            "customer": {
                "email": f"{email}"
            },
            "items": [
                {
                    "description": PLAN_LABELS.get(plan_key, "Подписка")[:128],
                    "quantity": 1,
                    "amount": {
                        "value": amount_value,
                        "currency": "RUB"
                    },
                    "vat_code": 1
                }
            ]
        }
    }
    if save_method:
        payment_payload["save_payment_method"] = True

    idempotence_key = str(uuid.uuid4())
    payment = Payment.create(payment_payload, idempotence_key)

    confirmation_url = payment.confirmation.confirmation_url
    payment_id = payment.id

    payment_nurture.set_checkout(
        chat_id,
        payment_id=payment_id,
        confirmation_url=confirmation_url,
        plan_key=plan_key,
        selected_price=selected_price,
    )

    renew_hint = ""
    if save_method:
        renew_hint = (
            "\\n\\nПосле оплаты карта сохранится для автопродления этого тарифа. "
            "Отменить автопродление можно в меню «💳 Оформить подписку»."
        )

    pay_kb = InlineKeyboardBuilder()
    pay_kb.row(types.InlineKeyboardButton(text="💳 Оплатить сейчас", url=confirmation_url))
    pay_kb.row(types.InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="nurture_referral"))
    pay_kb.row(types.InlineKeyboardButton(text=BACK_BUTTON_TEXT, callback_data="back_to_main"))
    await bot.send_message(
        chat_id=message.chat.id,
        text=(
            f"Оплата: {PLAN_LABELS.get(plan_key, 'Подписка')}\\n\\n"
            + "Нажмите кнопку ниже — откроется безопасная страница YooKassa."
            + renew_hint
            + REFERRAL_HINT
        ),
        reply_markup=pay_kb.as_markup(),
    )

    asyncio.create_task(
        check_payment_status(payment_id, message.chat.id, selected_price, plan_key=plan_key)
    )'''

    new_submonth_tail = '''    try:
        if PAYMENT_PROVIDER == "robokassa":
            await _start_robokassa_checkout(chat_id, plan_key, selected_price, email)
        else:
            configure_yookassa()
            order_manager.increment_order_number()
            amount_value = f"{int(selected_price / 100)}.00"
            save_method = plan_key in RECURRING_PLAN_KEYS
            payment_payload = {
                "amount": {"value": amount_value, "currency": "RUB"},
                "capture": True,
                "confirmation": {"type": "redirect", "return_url": BOT_RETURN_URL},
                "description": PLAN_LABELS.get(plan_key, "Оплата подписки"),
                "metadata": {
                    "order_id": f"{order_manager.get_order_number()}",
                    "chat_id": str(chat_id),
                    "plan_key": plan_key,
                    "selected_price": str(selected_price),
                },
                "receipt": {
                    "customer": {"email": f"{email}"},
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
                payment_payload["save_payment_method"] = True
            idempotence_key = str(uuid.uuid4())
            payment = Payment.create(payment_payload, idempotence_key)
            confirmation_url = payment.confirmation.confirmation_url
            payment_id = payment.id
            payment_nurture.set_checkout(
                chat_id,
                payment_id=payment_id,
                confirmation_url=confirmation_url,
                plan_key=plan_key,
                selected_price=selected_price,
            )
            renew_hint = ""
            if save_method:
                renew_hint = (
                    "\\n\\nПосле оплаты карта сохранится для автопродления этого тарифа. "
                    "Отменить автопродление можно в меню «💳 Оформить подписку»."
                )
            pay_kb = InlineKeyboardBuilder()
            pay_kb.row(types.InlineKeyboardButton(text="💳 Оплатить сейчас", url=confirmation_url))
            pay_kb.row(types.InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="nurture_referral"))
            pay_kb.row(types.InlineKeyboardButton(text=BACK_BUTTON_TEXT, callback_data="back_to_main"))
            await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"Оплата: {PLAN_LABELS.get(plan_key, 'Подписка')}\\n\\n"
                    + "Нажмите кнопку ниже — откроется безопасная страница YooKassa."
                    + renew_hint
                    + REFERRAL_HINT
                ),
                reply_markup=pay_kb.as_markup(),
            )
            asyncio.create_task(
                check_payment_status(payment_id, message.chat.id, selected_price, plan_key=plan_key)
            )
    except (ValueError, TypeError) as e:
        await bot.send_message(chat_id, f"Оплата временно недоступна: {e}", reply_markup=back_kb())
        await call.answer()
        return
    await call.answer()'''
    text = must_replace(text, old_submonth_tail, new_submonth_tail, "submonth checkout")

    # Insert robokassa helpers before check_payment_status
    marker = "async def check_payment_status(payment_id, chat_id, selected_price, plan_key: Optional[str] = None):"
    if "async def _start_robokassa_checkout" not in text:
        text = must_replace(text, marker, ROBOKASSA_FUNCS + marker, "insert robokassa funcs")

    # startup log
    text = text.replace(
        'logging.info("YooKassa payments ENABLED")',
        'logging.info("Payments ENABLED provider=%s", PAYMENT_PROVIDER)',
        1,
    )
    text = text.replace(
        '"YooKassa payments DISABLED (referral unlimited). auto_renew cleared=%s"',
        '"Payments DISABLED (referral unlimited). auto_renew cleared=%s"',
        1,
    )

    # email success copy
    text = text.replace(
        '"Email установлен. Выберите подписку.\\n\\n"\n'
        '            "Безлимитные тарифы включают автопродление (карту можно отвязать в меню)."',
        '"Email установлен. Выберите подписку.\\n\\n"\n'
        '            "Тарифы 111/555/999 — месяц безлимита с автопродлением (отвязать карту можно в меню)."',
        1,
    )

    path.write_text(text, encoding="utf-8")
    # sanity
    compile(text, str(path), "exec")
    print(f"patched OK: {path}")


def patch_merge(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "robokassa_prev_invoice_id" in text and "payment_provider" in text:
        print(f"merge already extended: {path}")
        return
    old = '''        if key not in dirty_q and "questions" in disk_u:
            ram_u["questions"] = disk_u["questions"]
        if key not in dirty_s and "subscription_end" in disk_u:
            ram_u["subscription_end"] = disk_u["subscription_end"]
'''
    new = '''        if key not in dirty_q and "questions" in disk_u:
            ram_u["questions"] = disk_u["questions"]
        if key not in dirty_s and "subscription_end" in disk_u:
            ram_u["subscription_end"] = disk_u["subscription_end"]
        if key not in dirty_s:
            for field in (
                "subscription_plan_key",
                "subscription_price",
                "auto_renew",
                "payment_provider",
                "robokassa_prev_invoice_id",
                "last_robokassa_inv_id",
                "renew_fail_count",
                "next_renew_at",
            ):
                if field in disk_u:
                    ram_u[field] = disk_u[field]
'''
    if old not in text:
        raise SystemExit(f"merge marker missing: {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"merge patched: {path}")


FULFILL_STORE_HELPER = '''
def _patch_users_store(chat_id: int, changes: dict[str, Any]) -> None:
    """Write grant into SQLite operational store so the live bot sees it."""
    try:
        from bot_core.operational_store import OperationalStore
    except Exception as exc:
        logger.warning("operational_store import failed: %s", exc)
        _patch_user_data(chat_id, changes)
        return

    store = OperationalStore(_data_dir() / "bot_state.sqlite3")
    key = str(int(chat_id))

    def mutator(disk: Any) -> Any:
        data = disk if isinstance(disk, dict) else {}
        rec = data.get(key)
        if not isinstance(rec, dict):
            rec = {"questions": 5, "username": None}
            data[key] = rec
        for field, value in changes.items():
            rec[field] = value
        data[key] = rec
        return data

    try:
        store.update_document(
            "users",
            mutator,
            legacy_path=_user_data_path(),
            source="robokassa_fulfill",
            default={},
        )
    except Exception as exc:
        logger.warning("store update failed, fallback json: %s", exc)
        _patch_user_data(chat_id, changes)
'''


def patch_fulfill(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "_patch_users_store" in text:
        print(f"fulfill already patched: {path}")
        return
    text = text.replace(
        "def _patch_user_data(chat_id: int, changes: dict[str, Any]) -> None:",
        FULFILL_STORE_HELPER + "\n\ndef _patch_user_data(chat_id: int, changes: dict[str, Any]) -> None:",
        1,
    )
    text = text.replace(
        "_patch_user_data(chat_id, {k: wallet.get(k) for k in changes})",
        "_patch_users_store(chat_id, {k: wallet.get(k) for k in changes})",
        1,
    )
    compile(text, str(path), "exec")
    path.write_text(text, encoding="utf-8")
    print(f"fulfill patched: {path}")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    main_py = root / "main.py"
    merge_py = root / "bot_core" / "user_state_merge.py"
    fulfill_py = root / "bot_core" / "robokassa_fulfill.py"
    if not main_py.exists():
        raise SystemExit(f"no main.py in {root}")
    patch_main(main_py)
    if merge_py.exists():
        patch_merge(merge_py)
    if fulfill_py.exists():
        patch_fulfill(fulfill_py)


if __name__ == "__main__":
    main()
