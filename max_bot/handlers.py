"""MAX handlers aligned with the current Telegram bot in main.py."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from . import config
from . import state as fsm
from .client import api
from .deck import build_deck, cards_from_webapp_paths, parse_comma_separated_cards, tarot_cards
from .economy import (
    activity_logger,
    agreement_manager,
    one_card,
    promocode_store,
    reading_history,
    status_data,
    user_data,
)
from .keyboards import (
    agreement_kb,
    back_kb,
    cards_pick_kb,
    channel_kb,
    consult_link_kb,
    day_card_kb,
    main_kb,
    pd_kb,
)
from .payments import auto_renew_status_line, show_plans, start_payment
from .promos import VALID_PROMOCODES
import shared_wallet

from .readings import deliver_structured_spread, reply, run_day_card

logger = logging.getLogger(__name__)

PD_GATE_TEXT = (
    "Чтобы пользоваться ботом, нужно отдельное согласие на обработку персональных данных.\n\n"
    f"Политика: {config.PRIVACY_URL}\n\n"
    "Нажимая кнопку, вы соглашаетесь на обработку данных для оказания услуги "
    "(мессенджеры, баланс, переписка; часть данных может уходить за рубеж — см. политику)."
)
OFERTA_GATE_TEXT = (
    "Теперь примите публичную оферту. Это консультация / доступ к боту, "
    "не медицина и не гарантия событий в жизни. Подтверждаете, что вам есть 18 лет.\n\n"
    f"Оферта: {config.OFERTA_URL}"
)

MENU_PAYLOADS = {
    config.BTN_ASK: "menu_ask",
    config.BTN_DAY: "menu_day",
    config.BTN_YESNO: "menu_yesno",
    config.BTN_ROMANTIC: "menu_romantic",
    config.BTN_WARN: "menu_warn",
    config.BTN_BALANCE: "menu_balance",
    config.CONSULTATION_BUTTON_TEXT: "menu_consult",
    config.BTN_PAY: "menu_pay",
    config.BTN_SUPPORT: "menu_support",
    config.BTN_HOW: "menu_how",
    config.BTN_REFERRAL: "menu_referral",
    config.GROUP_BUTTON_TEXT: "menu_group",
    config.BTN_PROMO: "menu_promo",
    config.BTN_EXTRA: "menu_extra",
    config.BTN_BROADCAST: "menu_broadcast",
    config.BTN_STATS: "menu_admin",
    config.BACK_BUTTON_TEXT: "menu_home",
    "📊 Статистика": "menu_admin",
}


def is_admin(user_id: int) -> bool:
    return user_id in config.MAX_ADMIN_IDS


def referral_link(user_id: int) -> str:
    if config.MAX_BOT_USERNAME:
        return f"https://max.ru/{config.MAX_BOT_USERNAME}?start=ref_{user_id}"
    return f"ref_{user_id} (задайте MAX_BOT_USERNAME для полной ссылки)"


def _landing_extra(user_id: int) -> str:
    if user_data.data.get(str(user_id), {}).get("registration_source") == "landing":
        return "\n\n🌐 Вы пришли с сайта — у вас 5 бесплатных раскладов для старта."
    return ""


async def send_legal_gate(user_id: int) -> bool:
    if agreement_manager.user_has_agreed(user_id):
        return False
    if not agreement_manager.has_pd_consent(user_id):
        await reply(user_id, PD_GATE_TEXT, attachments=pd_kb(), fmt=None)
        return True
    await reply(user_id, OFERTA_GATE_TEXT, attachments=agreement_kb(), fmt=None)
    return True


async def send_main_welcome(user_id: int) -> None:
    await reply(
        user_id,
        "Привет!\nЯ твой персональный бот-таролог 🤖\n"
        "Воспользуйся кнопками ниже, чтобы взаимодействовать со мной:"
        + _landing_extra(user_id),
        attachments=main_kb(user_id),
        fmt=None,
    )
    await reply(
        user_id,
        f"У вас доступно {user_data.get_user_questions(user_id)} вопросов",
        fmt=None,
    )
    fsm.clear(user_id)


async def apply_referral_on_join(user_id: int, *, is_new: bool, payload: str | None) -> None:
    payload = (payload or "").strip()
    if config.LANDING_START_PARAM and payload == config.LANDING_START_PARAM:
        record = user_data._ensure(user_id)
        if not record.get("registration_source"):
            record["registration_source"] = "landing"
            user_data.save_data()
        return
    if not (is_new and payload.startswith("ref_")):
        return
    raw = payload[4:]
    if not raw.isdigit():
        return
    referrer_id = int(raw)
    if referrer_id == user_id:
        return
    if not user_data.set_referred_by_once(user_id, referrer_id):
        return
    user_data.add_user(referrer_id)
    user_data.increment_user_questions(referrer_id, config.REFERRAL_JOIN_BONUS)
    user_data.increment_referrals_count(referrer_id, 1)
    try:
        await reply(
            referrer_id,
            "По вашей реферальной ссылке пришёл новый пользователь! Вам начислено +5 раскладов.",
            fmt=None,
        )
    except Exception:
        pass


async def send_welcome(user_id: int, *, start_payload: str | None = None) -> None:
    is_new = not user_data.has_user(user_id)
    user_data.add_user(user_id)
    activity_logger.log_command(user_id, "/start")
    await apply_referral_on_join(user_id, is_new=is_new, payload=start_payload)
    if await send_legal_gate(user_id):
        return
    await send_main_welcome(user_id)


async def access_mode(user_id: int) -> Optional[str]:
    """'sub' if unlimited now, 'balance' if questions remain, otherwise None."""
    end = user_data.get_subscription_end(user_id)
    now = datetime.now()
    if end and now < end:
        return "sub"
    if end and now > end:
        await reply(user_id, "Ваша подписка закончилась.", attachments=back_kb(), fmt=None)
    if user_data.get_user_questions(user_id) > 0:
        return "balance"
    await reply(user_id, "У вас закончились вопросы!", attachments=back_kb(), fmt=None)
    return None


def _days_left(user_id: int) -> int:
    end = user_data.get_subscription_end(user_id)
    if not end:
        return 0
    return max(0, (end - datetime.now()).days)


async def start_ask(user_id: int) -> None:
    mode = await access_mode(user_id)
    if not mode:
        return
    fsm.set_state(user_id, fsm.ASK_QUESTION)
    if mode == "sub":
        text = (
            f"Подписка активна!\n\nОсталось дней: {_days_left(user_id)}.\n\n"
            "Напишите свой вопрос: 👇"
        )
    else:
        text = "Напишите свой вопрос для расклада: 👇"
    await reply(user_id, text, attachments=back_kb(), fmt=None)


async def start_yesno(user_id: int) -> None:
    mode = await access_mode(user_id)
    if not mode:
        return
    fsm.set_state(user_id, fsm.YESNO_QUESTION)
    if mode == "sub":
        text = (
            f"Подписка активна!\n\nОсталось дней: {_days_left(user_id)}.\n\n"
            "Напишите свой вопрос, на который хотите узнать ответ, да или нет: 👇"
        )
    else:
        text = "Напишите свой вопрос, на который хотите узнать ответ, да или нет: 👇"
    await reply(user_id, text, attachments=back_kb(), fmt=None)


async def start_fixed_spread(user_id: int, *, state: str, intro: str, pick_url: str) -> None:
    mode = await access_mode(user_id)
    if not mode:
        return
    fsm.set_state(user_id, state)
    if mode == "sub":
        await reply(
            user_id,
            f"Подписка активна!\n\nОсталось дней: {_days_left(user_id)}.",
            attachments=back_kb(),
            fmt=None,
        )
    await reply(user_id, intro, attachments=back_kb(), fmt=None)
    await reply(
        user_id,
        "Выбрать карты:",
        attachments=cards_pick_kb(pick_url),
        fmt=None,
    )


async def send_balance(user_id: int) -> None:
    questions = user_data.get_user_questions(user_id)
    end = user_data.get_subscription_end(user_id)
    if end and datetime.now() < end:
        status_line = f"Подписка активна. Осталось дней: {_days_left(user_id)}"
    else:
        status_line = "Подписка не активна."
    await reply(
        user_id,
        f"Ваш баланс: {questions} вопросов.\n{status_line}\n{auto_renew_status_line(user_id)}"
        + shared_wallet.hint("max", user_id, user_data.data.get(str(user_id))),
        attachments=back_kb(),
        fmt=None,
    )


async def send_referral_info(user_id: int) -> None:
    invited = user_data.get_referrals_count(user_id)
    await reply(
        user_id,
        (
            f"Ваша реферальная ссылка:\n{referral_link(user_id)}\n\n"
            "За каждого друга, который впервые запустит бота по этой ссылке, вам начисляется +5 раскладов.\n"
            f"Приглашено друзей: {invited}"
        ),
        attachments=back_kb(),
        fmt=None,
    )


async def send_consultation(user_id: int) -> None:
    attachments = consult_link_kb()
    video = config.CONSULTATION_VIDEO_PATH
    if os.path.isfile(video):
        try:
            token = await api.upload_media(video, "video")
        except Exception as exc:
            logger.warning("consultation video upload failed: %s", exc)
            token = None
        if token:
            attachments = [{"type": "video", "payload": {"token": token}}, *attachments]
    await reply(user_id, config.CONSULTATION_MESSAGE, attachments=attachments, fmt=None)
    await reply(
        user_id,
        "◀️ В главное меню — кнопка «Назад» ниже.",
        attachments=back_kb(),
        fmt=None,
    )


async def send_extra(user_id: int) -> None:
    await reply(
        user_id,
        f"Текущий баланс:{user_data.get_user_questions(user_id)}",
        attachments=back_kb(),
        fmt=None,
    )
    await reply(
        user_id,
        "Подпишитесь на канал и подтвердите кнопкой — бонус тот же, что в Telegram: "
        "+5 раскладов и следующее пополнение через 30 дней.\n\n"
        f"{config.CHANNEL_URL}",
        attachments=channel_kb(),
        fmt=None,
    )


async def claim_channel(user_id: int) -> None:
    if status_data.is_status_zero(user_id):
        status_data.toggle_status(user_id)
        user_data.increment_user_questions(user_id, 5)
        await reply(
            user_id,
            "Вы подписались на канал! Вам добавлено 5 вопросов.\n\n"
            "Следующее пополнение вашего аккаунта на 5 раскладов через 30 дней.",
            fmt=None,
        )
        return
    await reply(
        user_id,
        "Вопросы уже добавлены.\n\n"
        "Следующее пополнение вашего аккаунта на 5 раскладов через 30 дней.",
        fmt=None,
    )


def cards_from_message(text: str, message: dict | None) -> Optional[list[dict[str, Any]]]:
    blobs: list[str] = []
    stripped = (text or "").strip()
    if stripped.startswith("{") or stripped.startswith("["):
        blobs.append(stripped)
    body = (message or {}).get("body") or {}
    for att in body.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        payload = att.get("payload") or {}
        if isinstance(payload, dict) and isinstance(payload.get("cards"), list):
            return cards_from_webapp_paths(payload["cards"])
        for key in ("data", "text"):
            raw = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(raw, str):
                blobs.append(raw)
    for raw in blobs:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        paths = None
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            paths = data["cards"]
        elif isinstance(data, list):
            paths = data
        if paths:
            return cards_from_webapp_paths(paths)
    return None


async def finish_cards(
    user_id: int,
    cards: list[dict],
    *,
    question: str,
    expected: tuple[int, int],
    kind: str,
    yes_no: bool = False,
    roles: list[str] | None = None,
    wrong: str = "Неправильный ввод. Повторите попытку",
) -> None:
    low, high = expected
    if not (low <= len(cards) <= high):
        await reply(user_id, wrong, fmt=None)
        return
    fsm.clear(user_id)
    await deliver_structured_spread(
        user_id,
        question,
        cards,
        card_roles=(roles[: len(cards)] if roles else None),
        role_labels_for_fallback=roles,
        yes_no_mode=yes_no,
        show_card_list_header=not yes_no and len(cards) != 1,
        compact_single_card=yes_no or len(cards) == 1,
        kind=kind,
    )


def build_admin_dashboard() -> str:
    stats = user_data.get_aggregate_stats()
    history = reading_history.get_admin_stats(days=7)
    labels = {
        "ask": "Вопрос",
        "yesno": "Да/Нет",
        "day": "Карта дня",
        "romantic": "Чувства",
        "warning": "Предупреждение",
    }

    def kind_lines(counts: dict) -> str:
        if not counts:
            return "  • нет данных"
        return "\n".join(
            f"  • {labels.get(k, k)}: <b>{v}</b>"
            for k, v in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        )

    top = "\n".join(
        f"  • id <code>{uid}</code>: <b>{cnt}</b>" for uid, cnt in stats["top_referrers"]
    ) or "  • пока никого"
    return (
        f"<b>📊 Панель администратора (MAX)</b>\n"
        f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n\n"
        f"<b>👥 Пользователи</b>\n"
        f"  • В базе: <b>{stats['total']}</b>\n"
        f"  • В логах: <b>{activity_logger.get_total_users()}</b>\n"
        f"  • Новых сегодня: <b>{activity_logger.get_new_users_today()}</b>\n"
        f"  • Активные 7д: <b>{activity_logger.count_active_users(7)}</b>\n"
        f"  • Активная подписка: <b>{stats['active_subs']}</b>\n"
        f"  • Без вопросов: <b>{stats['zero_questions']}</b>\n\n"
        f"<b>🔮 Расклады</b>\n"
        f"  • Сегодня: <b>{history['today_total']}</b>\n"
        f"{kind_lines(history['by_kind_today'])}\n"
        f"  • 7 дней: <b>{history['period_total']}</b>\n"
        f"  • Всего: <b>{history['all_total']}</b>\n\n"
        f"<b>🔗 Рефералка</b>\n"
        f"  • Пришли по ссылке: <b>{stats['referred_users']}</b>\n"
        f"  • Всего приглашений: <b>{stats['total_invites']}</b>\n"
        f"<b>Топ:</b>\n{top}"
    )


async def handle_menu(user_id: int, payload: str) -> None:
    fsm.clear(user_id)
    if payload == "menu_home":
        await reply(user_id, "Меню Follow the Frensy:", attachments=main_kb(user_id), fmt=None)
        return
    if payload == "menu_ask":
        await start_ask(user_id)
        return
    if payload == "menu_yesno":
        await start_yesno(user_id)
        return
    if payload == "menu_day":
        one_card.add_chat(user_id)
        if one_card.update_date_if_needed(user_id):
            await reply(
                user_id,
                "Карта дня покажет как пройдёт твой сегодняшний день!",
                attachments=day_card_kb(),
                fmt=None,
            )
        else:
            await reply(user_id, "Вы уже получили карту дня!", attachments=back_kb(), fmt=None)
        return
    if payload == "menu_romantic":
        await start_fixed_spread(
            user_id,
            state=fsm.ROMANTIC,
            intro=config.ROMANTIC_INTRO,
            pick_url=config.MAX_CARDS_MINIAPP_URL,
        )
        return
    if payload == "menu_warn":
        await start_fixed_spread(
            user_id,
            state=fsm.WARNING,
            intro=config.WARN_INTRO,
            pick_url=config.MAX_CARDS_MINIAPP_URL,
        )
        return
    if payload == "menu_balance":
        await send_balance(user_id)
        return
    if payload == "menu_consult":
        await send_consultation(user_id)
        return
    if payload == "menu_pay":
        if user_data.get_user_email(user_id):
            await show_plans(user_id)
        else:
            fsm.set_state(user_id, fsm.EMAIL)
            await reply(
                user_id,
                "Для того чтобы оформить подписку необходимо ввести почту. \n\nВведите почту."
                + config.REFERRAL_HINT,
                attachments=back_kb(),
                fmt=None,
            )
        return
    if payload == "menu_support":
        await reply(user_id, config.SUPPORT_TEXT, attachments=back_kb(), fmt=None)
        return
    if payload == "menu_how":
        await reply(user_id, config.HOW_IT_WORKS_TEXT, attachments=back_kb(), fmt=None)
        return
    if payload == "menu_referral":
        await send_referral_info(user_id)
        return
    if payload == "menu_group":
        if config.GROUP_INVITE_URL:
            text = (
                "Вступайте в нашу группу — там анонсы, обсуждения и дополнительные материалы:\n"
                f"{config.GROUP_INVITE_URL}"
            )
        else:
            text = "Ссылка на группу пока не настроена. Администратор может добавить GROUP_INVITE_URL в .env на сервере."
        await reply(user_id, text, attachments=back_kb(), fmt=None)
        return
    if payload == "menu_promo":
        fsm.set_state(user_id, fsm.PROMO)
        await reply(user_id, "Если у вас есть промокод, то введите его", attachments=back_kb(), fmt=None)
        return
    if payload == "menu_extra":
        await send_extra(user_id)
        return
    if payload == "menu_broadcast":
        if not is_admin(user_id):
            return
        fsm.set_state(user_id, fsm.BROADCAST)
        await reply(
            user_id,
            "Отправьте сообщение для рассылки.\n\n"
            "Можно отправить текст. Бот разошлёт его всем пользователям MAX.",
            attachments=back_kb(),
            fmt=None,
        )
        return
    if payload == "menu_admin":
        if not is_admin(user_id):
            await reply(user_id, "Нет доступа.", fmt=None)
            return
        await reply(user_id, build_admin_dashboard(), attachments=main_kb(user_id))
        return


async def handle_state(user_id: int, text: str, message: dict | None) -> bool:
    state = fsm.get_state(user_id)
    if not state:
        return False
    picked = cards_from_message(text, message)

    if state == fsm.ASK_QUESTION:
        fsm.set_state(user_id, fsm.ASK_CARDS, question=text)
        await reply(
            user_id,
            "Если хотите ввести свои карты, напишите от 3 до 6 карт через запятую!",
            attachments=back_kb(),
            fmt=None,
        )
        await reply(
            user_id,
            "Выбери карты:",
            attachments=cards_pick_kb(config.MAX_CARDS_MINIAPP_URL),
            fmt=None,
        )
        return True

    if state == fsm.YESNO_QUESTION:
        fsm.set_state(user_id, fsm.YESNO_CARDS, question=text)
        await reply(
            user_id,
            "Если хотите ввести свою карту, напишите 1 карту!",
            attachments=back_kb(),
            fmt=None,
        )
        await reply(
            user_id,
            "Выбери карту:",
            attachments=cards_pick_kb(config.MAX_YESNO_MINIAPP_URL, label="🃏 Выбрать карту"),
            fmt=None,
        )
        return True

    if state == fsm.ASK_CARDS:
        data = fsm.get_data(user_id)
        question = str(data.get("question") or "")
        if picked:
            fsm.clear(user_id)
            await deliver_structured_spread(user_id, question, picked, kind="ask")
            return True
        await finish_cards(
            user_id,
            parse_comma_separated_cards(text),
            question=question,
            expected=(3, 6),
            kind="ask",
        )
        return True

    if state == fsm.YESNO_CARDS:
        data = fsm.get_data(user_id)
        question = str(data.get("question") or "")
        if picked:
            fsm.clear(user_id)
            await deliver_structured_spread(
                user_id,
                question,
                picked[:1],
                yes_no_mode=True,
                show_card_list_header=False,
                compact_single_card=True,
                kind="yesno",
            )
            return True
        await finish_cards(
            user_id,
            parse_comma_separated_cards(text),
            question=question,
            expected=(1, 1),
            kind="yesno",
            yes_no=True,
            wrong="Введите одну карту (или выберите через WebApp).",
        )
        return True

    if state in {fsm.ROMANTIC, fsm.WARNING}:
        romantic = state == fsm.ROMANTIC
        roles = config.ROMANTIC_CARD_ROLES if romantic else config.DANGEROUS_CARD_ROLES
        question = config.ROMANTIC_SPREAD_QUESTION if romantic else config.DANGEROUS_SPREAD_QUESTION
        kind = "romantic" if romantic else "warning"
        if picked:
            fsm.clear(user_id)
            await deliver_structured_spread(
                user_id,
                question,
                picked,
                card_roles=roles[: len(picked)],
                role_labels_for_fallback=roles,
                kind=kind,
            )
            return True
        await finish_cards(
            user_id,
            parse_comma_separated_cards(text),
            question=question,
            expected=(3, 3),
            kind=kind,
            roles=roles,
        )
        return True

    if state == fsm.PROMO:
        fsm.clear(user_id)
        code = (text or "").strip()
        if code in VALID_PROMOCODES:
            if promocode_store.is_used(user_id, code):
                await reply(
                    user_id,
                    "Вы уже использовали этот промокод. Пожалуйста, попробуйте другой. ⚠️",
                    attachments=main_kb(user_id),
                    fmt=None,
                )
            else:
                user_data.increment_user_questions(user_id, 100)
                promocode_store.mark_used(user_id, code)
                await reply(
                    user_id,
                    "Промокод активирован! Вам начислено 100 вопросов 🎉",
                    attachments=main_kb(user_id),
                    fmt=None,
                )
        else:
            await reply(
                user_id,
                "Некорректный промокод. Пожалуйста, попробуйте еще раз ⚠️",
                attachments=back_kb(),
                fmt=None,
            )
        return True

    if state == fsm.EMAIL:
        try:
            user_data.set_user_email(user_id, text.strip())
        except ValueError:
            await reply(user_id, "Email не установлен. Введите корректный email.", attachments=back_kb(), fmt=None)
            return True
        fsm.clear(user_id)
        await show_plans(
            user_id,
            intro=(
                "Email установлен. Выберите тариф «Месяц безлимит» (31 день).\n\n"
                "Это разовая оплата через Робокассу: автопродления нет, карта для списаний не сохраняется."
                + config.REFERRAL_HINT
            ),
        )
        return True

    if state == fsm.BROADCAST:
        if not is_admin(user_id):
            fsm.clear(user_id)
            return True
        fsm.clear(user_id)
        sent = 0
        failed = 0
        for target in user_data.get_filtered_user_ids([user_id]):
            try:
                await reply(target, text, fmt=None)
                sent += 1
            except Exception:
                failed += 1
        await reply(
            user_id,
            f"Рассылка завершена.\nОтправлено: {sent}\nНе доставлено: {failed}",
            attachments=main_kb(user_id),
            fmt=None,
        )
        return True

    return False


async def handle_text(user_id: int, text: str, message: dict | None = None) -> None:
    text = (text or "").strip()
    if not text and not cards_from_message("", message):
        return
    activity_logger.log_command(user_id, (text or "<attachment>")[:80])
    low = text.lower()
    first = low.split(maxsplit=1)[0] if low else ""

    if first == "/link":
        user_data.add_user(user_id)
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        if not code:
            issued = shared_wallet.issue_code("max", user_id, user_data.data.get(str(user_id)))
            await reply(
                user_id,
                "Чтобы баланс был один и в Telegram, отправьте боту в Telegram:\n"
                f"/link {issued}",
                attachments=main_kb(user_id),
                fmt=None,
            )
            return
        ok, reply_text = shared_wallet.redeem(
            "max", user_id, code, user_data.data.get(str(user_id))
        )
        if ok:
            shared_wallet.mirror(
                user_data.data.get(str(user_id)),
                shared_wallet.view("max", user_id, user_data.data.get(str(user_id))),
            )
            user_data.save_data()
        await reply(user_id, reply_text, attachments=main_kb(user_id), fmt=None)
        return

    if first in {"/start", "start", "начать"}:
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else None
        await send_welcome(user_id, start_payload=payload)
        return

    if text == "1111":
        if not is_admin(user_id):
            await reply(user_id, "Нет доступа.", fmt=None)
            return
        user_data.set_user_questions(user_id, 10**9)
        await reply(
            user_id,
            "Вам выдано практически бесконечное количество вопросов.",
            attachments=main_kb(user_id),
            fmt=None,
        )
        return

    if first in {"/admin", "/stats"} or text in MENU_PAYLOADS:
        if await send_legal_gate(user_id):
            return
        if first in {"/admin", "/stats"}:
            payload = "menu_admin"
        else:
            payload = MENU_PAYLOADS[text]
        await handle_menu(user_id, payload)
        return

    if first == "/agreement":
        await reply(
            user_id,
            f"Политика персональных данных:\n{config.PRIVACY_URL}\n\nПубличная оферта:\n{config.OFERTA_URL}",
            fmt=None,
        )
        return

    if await send_legal_gate(user_id):
        return

    if await handle_state(user_id, text, message):
        return

    await reply(
        user_id,
        "Выберите действие кнопками ниже.",
        attachments=main_kb(user_id),
        fmt=None,
    )


async def handle_callback(user_id: int, payload: str, callback_id: str = "") -> None:
    if callback_id:
        try:
            await api.answer_callback(callback_id)
        except Exception as exc:
            logger.warning("answer_callback failed: %s", exc)

    activity_logger.log_command(user_id, f"cb:{payload}")
    user_data.add_user(user_id)

    if payload == "agree_pd":
        agreement_manager.add_pd_consent(user_id)
        await reply(user_id, OFERTA_GATE_TEXT, attachments=agreement_kb(), fmt=None)
        return
    if payload == "agree":
        if not agreement_manager.has_pd_consent(user_id):
            await reply(user_id, PD_GATE_TEXT, attachments=pd_kb(), fmt=None)
            return
        agreement_manager.add_user_agreement(user_id)
        await reply(user_id, "Спасибо за согласие! Теперь вы можете продолжить использование бота.", fmt=None)
        await send_main_welcome(user_id)
        return
    if payload == "disagree":
        await reply(user_id, "Без согласия работать с ботом нельзя. Нажмите /start, когда будете готовы.", fmt=None)
        return

    if await send_legal_gate(user_id):
        return

    if payload == "card_day_one":
        build_deck()
        selected = one_card.select_random_card(user_id)
        path = f"static/card{selected}.jpg"
        await run_day_card(user_id, {"path": path, "label": tarot_cards.get(path, f"Карта {selected}")})
        return

    if payload == "channel_claim":
        await claim_channel(user_id)
        return

    if payload == "cancel_auto_renew":
        if not user_data.is_auto_renew_enabled(user_id):
            await reply(
                user_id,
                "Автопродление уже выключено.\n" + auto_renew_status_line(user_id),
                attachments=main_kb(user_id),
                fmt=None,
            )
            return
        user_data.disable_auto_renew(user_id)
        end = user_data.get_subscription_end(user_id)
        note = ""
        if end and end > datetime.now():
            note = f"\nТекущая подписка действует до {end.strftime('%d.%m.%Y %H:%M')}."
        await reply(
            user_id,
            "Автопродление отключено. Повторных списаний не будет."
            + note
            + "\nЧтобы снова включить — оплатите безлимитный тариф заново.",
            attachments=main_kb(user_id),
            fmt=None,
        )
        return

    if payload.startswith("sub_"):
        await start_payment(user_id, payload)
        return

    if payload in {
        "menu_home",
        "menu_ask",
        "menu_yesno",
        "menu_day",
        "menu_romantic",
        "menu_warn",
        "menu_balance",
        "menu_consult",
        "menu_pay",
        "menu_support",
        "menu_how",
        "menu_referral",
        "menu_group",
        "menu_promo",
        "menu_extra",
        "menu_broadcast",
        "menu_admin",
    }:
        await handle_menu(user_id, payload)
        return

    await reply(user_id, "Неизвестная кнопка.", attachments=main_kb(user_id), fmt=None)


def extract_user_id(update: dict) -> Optional[int]:
    ut = update.get("update_type")
    if ut == "bot_started":
        user = update.get("user") or {}
        uid = user.get("user_id")
        return int(uid) if uid is not None else None
    if ut == "message_created":
        sender = (update.get("message") or {}).get("sender") or {}
        uid = sender.get("user_id")
        return int(uid) if uid is not None else None
    if ut == "message_callback":
        cb = update.get("callback") or {}
        user = cb.get("user") or {}
        if user.get("user_id") is not None:
            return int(user["user_id"])
        sender = (cb.get("message") or {}).get("sender") or {}
        if sender.get("user_id") is not None:
            return int(sender["user_id"])
    return None


async def accept_miniapp_cards(user_id: int, cards: list[dict]) -> None:
    """Cards chosen inside the MAX miniapp, after the question was already saved."""
    if not cards:
        await reply(user_id, "Карты не выбраны. Откройте выбор ещё раз.", attachments=main_kb(user_id), fmt=None)
        return
    state = fsm.get_state(user_id)
    if state == fsm.ASK_CARDS:
        question = str(fsm.get_data(user_id).get("question") or "")
        fsm.clear(user_id)
        await deliver_structured_spread(user_id, question, cards, kind="ask")
        return
    if state == fsm.YESNO_CARDS:
        question = str(fsm.get_data(user_id).get("question") or "")
        fsm.clear(user_id)
        await deliver_structured_spread(
            user_id,
            question,
            cards[:1],
            yes_no_mode=True,
            show_card_list_header=False,
            compact_single_card=True,
            kind="yesno",
        )
        return
    if state in {fsm.ROMANTIC, fsm.WARNING}:
        romantic = state == fsm.ROMANTIC
        roles = config.ROMANTIC_CARD_ROLES if romantic else config.DANGEROUS_CARD_ROLES
        question = config.ROMANTIC_SPREAD_QUESTION if romantic else config.DANGEROUS_SPREAD_QUESTION
        fsm.clear(user_id)
        await deliver_structured_spread(
            user_id,
            question,
            cards,
            card_roles=roles[: len(cards)],
            role_labels_for_fallback=roles,
            kind="romantic" if romantic else "warning",
        )
        return
    await reply(
        user_id,
        "Сначала напишите вопрос, потом откройте выбор карт.",
        attachments=main_kb(user_id),
        fmt=None,
    )


async def dispatch_update(update: dict) -> None:
    ut = update.get("update_type") or ""
    user_id = extract_user_id(update)
    if user_id is None:
        logger.warning("No user_id in update %s", ut)
        return

    if ut == "bot_started":
        payload = update.get("payload") or update.get("start_payload")
        await send_welcome(user_id, start_payload=payload)
        return

    if ut == "message_created":
        msg = update.get("message") or {}
        sender = msg.get("sender") or {}
        if sender.get("is_bot"):
            return
        body = msg.get("body") or {}
        await handle_text(user_id, body.get("text") or "", msg)
        return

    if ut == "message_callback":
        cb = update.get("callback") or {}
        await handle_callback(user_id, cb.get("payload") or "", cb.get("callback_id") or "")
        return

    logger.debug("Unhandled update_type=%s", ut)
