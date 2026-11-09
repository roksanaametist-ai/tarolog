"""Inline keyboards for MAX. Labels match the Telegram reply menu."""

from __future__ import annotations

from typing import Any

from . import config


def inline_keyboard(rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


def btn_callback(text: str, payload: str) -> dict[str, str]:
    return {"type": "callback", "text": text, "payload": payload}


def btn_link(text: str, url: str) -> dict[str, str]:
    return {"type": "link", "text": text, "url": url}


def btn_open_app(text: str, url: str) -> dict[str, str]:
    return {"type": "open_app", "text": text, "web_app": url}


def pd_kb() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [btn_link("📄 Политика ПД", config.PRIVACY_URL)],
            [btn_callback("✅ Согласен на обработку ПД", "agree_pd")],
            [btn_callback("❌ Отказаться", "disagree")],
        ]
    )


def agreement_kb() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [btn_link("📄 Оферта", config.OFERTA_URL)],
            [btn_callback("✅ Принимаю оферту, мне 18+", "agree")],
            [btn_callback("❌ Отказаться", "disagree")],
        ]
    )


def main_kb(user_id: int) -> list[dict[str, Any]]:
    # Одна кнопка в ряд: в MAX текст узкой кнопки обрезается, и меню из Telegram
    # превращалось в обрывки. Подписи короче, действия те же.
    rows: list[list[dict[str, Any]]] = [
        [btn_callback("🔮 Задать вопрос", "menu_ask")],
        [btn_callback("🔮 Карта дня", "menu_day")],
        [btn_callback("🔮 Да / Нет", "menu_yesno")],
        [btn_callback("Чувства, мысли, действия", "menu_romantic")],
        [btn_callback("🔮 Предупреждение", "menu_warn")],
        [btn_callback("💎 Мой баланс", "menu_balance")],
        [btn_callback("✨ Консультация", "menu_consult")],
        [btn_callback("💳 Оформить подписку", "menu_pay")],
        [btn_callback("🛠 Техподдержка", "menu_support")],
        [btn_callback("ℹ️ Как работает бот", "menu_how")],
        [btn_callback("👥 Пригласить (+5)", "menu_referral")],
    ]
    if config.GROUP_INVITE_URL:
        rows.append([btn_callback(config.GROUP_BUTTON_TEXT, "menu_group")])
    rows.append([btn_callback("🎟 Промокод", "menu_promo")])
    rows.append([btn_callback("🎁 Ещё расклады", "menu_extra")])
    if user_id in config.MAX_ADMIN_IDS:
        rows.append([btn_callback("📣 Рассылка", "menu_broadcast")])
        rows.append([btn_callback("📊 Статистика", "menu_admin")])
    return inline_keyboard(rows)


def back_kb() -> list[dict[str, Any]]:
    rows = [
        [btn_callback("✨ Консультация", "menu_consult")],
        [btn_callback(config.BACK_BUTTON_TEXT, "menu_home")],
    ]
    return inline_keyboard(rows)


def cards_pick_kb(url: str, *, label: str = "🃏 Выбрать карты") -> list[dict[str, Any]]:
    rows: list[list[dict[str, Any]]] = []
    if url:
        # open_app принимает только ссылку, заранее сохранённую в настройках бота MAX.
        # Пока её нет, обычная ссылка открывает ту же страницу.
        rows.append([btn_link(label, url)])
    rows.append([btn_callback(config.CONSULTATION_BUTTON_TEXT, "menu_consult")])
    rows.append([btn_callback(config.BACK_BUTTON_TEXT, "menu_home")])
    return inline_keyboard(rows)


def day_card_kb() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [btn_callback("Получить карту дня", "card_day_one")],
            [btn_link(config.CONSULTATION_BUTTON_TEXT, config.CONSULTATION_URL)],
            [btn_callback(config.BACK_BUTTON_TEXT, "menu_home")],
        ]
    )


def plans_kb(user_id: int) -> list[dict[str, Any]]:
    from .economy import user_data

    rows = [
        [btn_callback("10 запросов - 169 руб.", "sub_10_169")],
        [btn_callback("Месяц (безлимит) - 359 руб.", "sub_7d_399")],
        [btn_callback("3 Месяца (безлимит) - 999 руб.", "sub_14d_499")],
        [btn_callback("Год (безлимит) - 2999 руб.", "sub_30d_699")],
    ]
    if user_data.is_auto_renew_enabled(user_id):
        rows.append([btn_callback("⏸ Отменить автопродление", "cancel_auto_renew")])
    rows.append([btn_link(config.CONSULTATION_BUTTON_TEXT, config.CONSULTATION_URL)])
    rows.append([btn_callback(config.BACK_BUTTON_TEXT, "menu_home")])
    return inline_keyboard(rows)


def pay_link_kb(url: str) -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [btn_link("💳 Оплатить сейчас", url)],
            [btn_callback(config.BTN_REFERRAL, "menu_referral")],
            [btn_link(config.CONSULTATION_BUTTON_TEXT, config.CONSULTATION_URL)],
            [btn_callback(config.BACK_BUTTON_TEXT, "menu_home")],
        ]
    )


def consult_link_kb() -> list[dict[str, Any]]:
    return inline_keyboard(
        [[btn_link("💬 Записаться на консультацию", config.CONSULTATION_URL)]]
    )


def after_reading_kb() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [btn_link(config.CONSULTATION_BUTTON_TEXT, config.CONSULTATION_URL)],
            [btn_callback(config.BACK_BUTTON_TEXT, "menu_home")],
        ]
    )


def channel_kb() -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [btn_link("📢 Канал", config.CHANNEL_URL)],
            [btn_callback("Я подписан на канал", "channel_claim")],
            [btn_callback(config.BACK_BUTTON_TEXT, "menu_home")],
        ]
    )
