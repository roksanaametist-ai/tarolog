from __future__ import annotations

import html
from typing import Any, Mapping


def _n(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pct(value: Any) -> str:
    try:
        return f"{float(value or 0):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _period_line(label: str, metric: str, periods: Mapping[str, Any]) -> str:
    today = _n(periods["today"]["counts"].get(metric))
    week = _n(periods["7d"]["counts"].get(metric))
    month = _n(periods["30d"]["counts"].get(metric))
    return f"  • {label}: <b>{today}</b> / <b>{week}</b> / <b>{month}</b>\n"


def _unique_period_line(label: str, metric: str, periods: Mapping[str, Any]) -> str:
    today = _n(periods["today"]["unique"].get(metric))
    week = _n(periods["7d"]["unique"].get(metric))
    month = _n(periods["30d"]["unique"].get(metric))
    return f"  • {label}: <b>{today}</b> / <b>{week}</b> / <b>{month}</b>\n"


def _kind_lines(counts: Mapping[str, Any], labels: Mapping[str, str]) -> str:
    if not counts:
        return "  • по типам: нет данных\n"
    items = sorted(counts.items(), key=lambda item: (-_n(item[1]), item[0]))
    return "".join(
        f"    ◦ {html.escape(labels.get(str(kind), str(kind)))}: <b>{_n(count)}</b>\n"
        for kind, count in items
    )


def _growth_funnel_lines(values: Mapping[str, Any]) -> str:
    if not values:
        return "  • пока нет данных\n"
    lines = []
    for code, raw in values.items():
        row = raw if isinstance(raw, Mapping) else {}
        starts = _n(row.get("starts"))
        signups = _n(row.get("signups"))
        activated = _n(row.get("activated"))
        returning = _n(row.get("activated_returning"))
        paid = _n(row.get("paid"))
        activation_rate = 100 * min(activated, signups) / signups if signups else 0.0
        extra = f", вернувшихся активных {returning}" if returning else ""
        lines.append(
            f"  • <code>{html.escape(str(code))}</code>: "
            f"{starts} переходов → {signups} новых → {activated} активных "
            f"({_pct(activation_rate)}) → {paid} оплатили{extra}\n"
        )
    return "".join(lines)


def build_admin_dashboard(
    snapshot: Mapping[str, Any],
    *,
    users: Mapping[str, Any],
    reviews: Mapping[str, Any],
    leads: Mapping[str, Any],
    tomorrow: Mapping[str, Any],
    nurture: Mapping[str, Any],
    payment_data: Mapping[str, Any],
    kind_labels: Mapping[str, str],
    public_deck: Mapping[str, Any] | None = None,
    secret_stats_cmd: str | None = None,
) -> str:
    """Render the Telegram admin dashboard from canonical analytics."""
    periods = snapshot["periods"]
    today = periods["today"]
    week = periods["7d"]
    month = periods["30d"]
    lifetime = snapshot["lifetime"]
    lifetime_unique = snapshot["lifetime_unique"]

    activation_7d = snapshot["activation_7d"]
    activation_30d = snapshot["activation_30d"]
    d1 = snapshot["retention_d1"]
    d7 = snapshot["retention_d7"]

    total_revenue = _n(payment_data.get("total_amount"))
    tracked_revenue = (
        _n(snapshot.get("legacy_revenue_kopecks"))
        + _n(lifetime.get("payment_succeeded_revenue"))
    )
    # payment_succeeded revenue lives in properties; period values are already queried.
    if not tracked_revenue:
        tracked_revenue = total_revenue

    top_referrers = users.get("top_referrers") or []
    top_lines = "".join(
        f"  • <code>{int(uid)}</code>: <b>{_n(count)}</b> регистраций\n"
        for uid, count in top_referrers
    ) or "  • пока нет\n"

    sources = users.get("referral_sources") or {}
    source_lines = "".join(
        f"  • {html.escape(str(source))}: <b>{_n(count)}</b>\n"
        for source, count in sorted(sources.items())
    ) or "  • нет данных\n"

    plans = payment_data.get("subscriptions") or {}
    plan_lines = "".join(
        f"  • {html.escape(str(plan))}: <b>{_n(count)}</b>\n"
        for plan, count in plans.items()
    ) or "  • нет данных\n"
    acquisition_lines = "".join(
        f"  • {html.escape(str(source))}: <b>{_n(count)}</b>\n"
        for source, count in (snapshot.get("acquisition_sources_30d") or {}).items()
    ) or "  • нет данных\n"
    callback_lines = "".join(
        f"  • <code>{html.escape(str(callback))}</code>: <b>{_n(count)}</b>\n"
        for callback, count in (snapshot.get("callbacks_7d") or {}).items()
    ) or "  • нет данных\n"
    share_opens_30 = _n(month["unique"].get("share_opened"))
    share_starts_30 = _n(month["unique"].get("share_link_started"))
    share_signups_30 = _n(month["unique"].get("referral_share_signup"))
    share_activated_30 = _n(month["unique"].get("referral_share_activated"))
    payment_intents_30 = _n(month["unique"].get("payment_intent"))
    payment_checkouts_30 = _n(month["unique"].get("payment_checkout"))
    payment_success_30 = _n(month["unique"].get("payment_succeeded"))
    share_cards_30 = _n(month["unique"].get("share_card_generated"))
    share_bonus_30 = _n(month["unique"].get("share_first_bonus"))
    partner_starts_30 = _n(month["unique"].get("partner_link_started"))
    partner_signups_30 = _n(month["unique"].get("partner_signup"))
    partner_activated_30 = _n(month["unique"].get("partner_activated"))
    campaign_starts_30 = _n(month["unique"].get("campaign_link_started"))
    campaign_signups_30 = _n(month["unique"].get("campaign_signup"))
    campaign_activated_30 = _n(month["unique"].get("campaign_activated"))
    partner_lines = _growth_funnel_lines(snapshot.get("partner_funnel_30d") or {})
    campaign_lines = _growth_funnel_lines(snapshot.get("campaign_funnel_30d") or {})
    storage = snapshot.get("operational_storage") or {}

    def conversion(part: int, total: int) -> str:
        return _pct(100 * part / total if total else 0)

    return (
        "<b>📊 Telegram-аналитика</b>\n"
        f"<i>{html.escape(str(snapshot['generated_at']))}</i>\n"
        "<i>Формат периода: сегодня / 7 дней / 30 дней</i>\n\n"
        "<b>👥 Аудитория</b>\n"
        f"  • В базе (профили): <b>{_n(users.get('total'))}</b>\n"
        f"  • Регистраций в аналитике: <b>{_n(lifetime_unique.get('user_registered'))}</b>"
        f" <i>(с миграции SQLite)</i>\n"
        f"  • Активные: <b>{_n(today.get('active_users'))}</b> / "
        f"<b>{_n(week.get('active_users'))}</b> / <b>{_n(month.get('active_users'))}</b>\n"
        + _unique_period_line("Новые", "user_registered", periods)
        + f"  • Вернулись после 30 дней тишины (7д): "
        f"<b>{_n(snapshot.get('resurrected_7d'))}</b>\n"
        f"  • Активные подписки: <b>{_n(users.get('active_subs'))}</b>\n"
        f"  • Баланс 0 без подписки: <b>{_n(users.get('zero_questions'))}</b>\n"
        f"  • Указали email: <b>{_n(users.get('with_email'))}</b>\n"
        "<b>Источники новых пользователей за 30 дней:</b>\n"
        + acquisition_lines
        + "\n"
        "<b>⚡ Активация и удержание</b>\n"
        f"  • Первый расклад ≤24ч (7д): <b>{_n(activation_7d.get('activated_24h'))}</b>"
        f"/{_n(activation_7d.get('registered'))} — <b>{_pct(activation_7d.get('rate'))}</b>\n"
        f"  • Первый расклад ≤24ч (30д): <b>{_n(activation_30d.get('activated_24h'))}</b>"
        f"/{_n(activation_30d.get('registered'))} — <b>{_pct(activation_30d.get('rate'))}</b>\n"
        f"  • Возврат D1: <b>{_n(d1.get('returned'))}</b>/{_n(d1.get('cohort'))} — "
        f"<b>{_pct(d1.get('rate'))}</b>\n"
        f"  • Возврат D7: <b>{_n(d7.get('returned'))}</b>/{_n(d7.get('cohort'))} — "
        f"<b>{_pct(d7.get('rate'))}</b>\n\n"
        "<b>🔮 Расклады</b>\n"
        + _period_line("Успешно завершены (без уточнений)", "reading_completed", periods)
        + _unique_period_line("Уникальные пользователи", "reading_completed", periods)
        + _period_line("Уточнения (clarify)", "clarify_completed", periods)
        + _period_line("Попытки", "reading_started", periods)
        + _period_line("Ошибки генерации", "reading_failed", periods)
        + f"  • По типам за 7 дней:\n{_kind_lines(week.get('reading_kinds') or {}, kind_labels)}\n"

        "<b>📤 Воронка шеринга</b>\n"
        + _period_line("Открыли отправку", "share_opened", periods)
        + _unique_period_line("Создали шер-карточку", "share_card_generated", periods)
        + _unique_period_line("CTA «переслать» показан", "share_forward_prompted", periods)
        + _period_line("Бонус: друг зашёл по share-ссылке", "share_first_bonus", periods)
        + _period_line("Дожим друга до 1-го расклада", "invitee_activation_nudge", periods)
        + _period_line("Пуш шереру «друг без расклада»", "sharer_invitee_pending_nudge", periods)
        + _period_line("Авто-шер после расклада", "auto_share_sent", periods)
        + _period_line("Авто-шер пропущен (лимит)", "auto_share_skipped", periods)
        + _period_line("Тёплый nudge «переслать»", "warm_share_nudge", periods)
        + _unique_period_line("Получили бонус за share-приглашение", "share_first_bonus", periods)
        + _unique_period_line("Пользователи шеринга", "share_opened", periods)
        + _unique_period_line("Перешли по share-ссылке", "share_link_started", periods)
        + _unique_period_line("Новые по share", "referral_share_signup", periods)
        + _unique_period_line("Сделали первый расклад", "referral_share_activated", periods)
        + f"  • Конверсия за 30д: открыли→перешли <b>{conversion(share_starts_30, share_opens_30)}</b>, "
        f"перешли→новые <b>{conversion(share_signups_30, share_starts_30)}</b>, "
        f"новые→активные <b>{conversion(share_activated_30, share_signups_30)}</b>\n"
        + f"  • Пользователей шеринга за всё время: <b>{_n(users.get('shared_total'))}</b>\n"
        f"  • Открытий отправки за всё время: <b>{_n(users.get('share_clicks_total'))}</b>\n"
        f"  • Карточка→друг зашёл по share-ссылке за 30д: "
        f"<b>{conversion(share_bonus_30, share_cards_30)}</b>\n"
        "  • Периодические открытия считаются точно с момента SQLite-миграции\n\n"
        "<b>📣 Партнёры и кампании — 30 дней</b>\n"
        f"  • Партнёры: <b>{partner_starts_30}</b> переходов → "
        f"<b>{partner_signups_30}</b> новых → <b>{partner_activated_30}</b> активных\n"
        "<b>По партнёрам:</b>\n"
        + partner_lines
        + f"  • Кампании: <b>{campaign_starts_30}</b> переходов → "
        f"<b>{campaign_signups_30}</b> новых → <b>{campaign_activated_30}</b> активных\n"
        "<b>По кампаниям:</b>\n"
        + campaign_lines
        + _unique_period_line("Win-back сообщений отправлено", "winback_sent", periods)
        + "\n"
        "<b>🔗 Реферальная система</b>\n"
        f"  • Новые с реферером всего: <b>{_n(users.get('referred_users'))}</b>\n"
        f"  • Приглашений в счётчиках: <b>{_n(users.get('total_invites'))}</b>\n"
        f"  • Активных приглашений: <b>{_n(users.get('total_active_invites'))}</b>\n"
        f"  • Рефереров: <b>{_n(users.get('referrers'))}</b>\n"
        "<b>Источники:</b>\n"
        + source_lines
        + "<b>Топ:</b>\n"
        + top_lines
        + "\n<b>💳 Воронка оплаты</b>\n"
        + _unique_period_line("Открыли тарифы", "payment_intent", periods)
        + _unique_period_line("Получили ссылку", "payment_checkout", periods)
        + _unique_period_line("Успешно оплатили", "payment_succeeded", periods)
        + _period_line("Ошибки оплаты", "payment_failed", periods)
        + f"  • Конверсия за 30д: тарифы→ссылка "
        f"<b>{conversion(payment_checkouts_30, payment_intents_30)}</b>, "
        f"ссылка→оплата <b>{conversion(payment_success_30, payment_checkouts_30)}</b>\n"
        + f"  • Выручка сегодня / 7д / 30д: "
        f"<b>{today.get('revenue_kopecks', 0) / 100:.2f}</b> / "
        f"<b>{week.get('revenue_kopecks', 0) / 100:.2f}</b> / "
        f"<b>{month.get('revenue_kopecks', 0) / 100:.2f}</b> ₽\n"
        f"  • Выручка по старому счётчику: <b>{total_revenue / 100:.2f} ₽</b>\n"
        f"  • В ожидании: тарифы <b>{_n(nurture.get('intent_open'))}</b>, "
        f"оплата <b>{_n(nurture.get('checkout_open'))}</b>, "
        f"завершено <b>{_n(nurture.get('completed'))}</b>\n"
        "<b>Успешные оплаты по тарифам (старый счётчик):</b>\n"
        + plan_lines
        + "\n<b>✨ Консультации, отзывы, карта на завтра</b>\n"
        f"  • Лиды консультаций: <b>{_n(leads.get('today'))}</b> / "
        f"<b>{_n(leads.get('period'))}</b> / <b>{_n(leads.get('total'))}</b> (сегодня/7д/всего)\n"
        + _period_line("Созданы лиды (SQLite)", "consult_lead_created", periods)
        + _period_line("Отзывы отправлены", "review_submitted", periods)
        + _period_line("Промокод: открыли ввод", "promo_prompted", periods)
        + _period_line("Промокод: активирован", "promo_redeemed", periods)
        + _period_line("Промокод: отклонён", "promo_rejected", periods)
        + f"  • Отзывы сейчас: ожидают <b>{_n(reviews.get('pending'))}</b>, "
        f"одобрены <b>{_n(reviews.get('approved'))}</b>, "
        f"отклонены <b>{_n(reviews.get('rejected'))}</b>\n"
        f"  • Push карты на завтра включён: <b>{_n(tomorrow.get('push_enabled'))}</b>\n"
        + _period_line("Открыли карту на завтра", "tomorrow_opened", periods)
        + _period_line("Push отправлены", "tomorrow_push_sent", periods)
        + "\n<b>🃏 Своя колода</b> <i>(воронка SQLite · сегодня/7д/30д)</i>\n"
        + _period_line("Превью в боте", "public_deck_created", periods)
        + _period_line("Отправили в чат", "public_deck_sent", periods)
        + _period_line("Открыли в чате", "public_deck_opened_chat", periods)
        + _period_line("Открыли в личке", "public_deck_opened_dm", periods)
        + _period_line("Открыли всего", "public_deck_opened", periods)
        + _period_line("Открыли другую", "public_deck_reopened", periods)
        + _period_line("Перетасовали", "public_deck_shuffled", periods)
        + _period_line("Свой расклад (старт вопроса)", "public_deck_own_spread", periods)
        + _unique_period_line("Уники: превью", "public_deck_created", periods)
        + _unique_period_line("Уники: отправили", "public_deck_sent", periods)
        + _unique_period_line("Уники: открыли в чате", "public_deck_opened_chat", periods)
        + (
            f"  • Журнал колоды (сегодня / {int((public_deck or {}).get('days') or 7)}д / всего):\n"
            f"    ◦ превью в боте: <b>{_n(((public_deck or {}).get('preview') or (public_deck or {}).get('created_entry') or {}).get('today'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('preview') or (public_deck or {}).get('created_entry') or {}).get('period'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('preview') or (public_deck or {}).get('created_entry') or {}).get('total'))}</b>\n"
            f"    ◦ отправок в чат: <b>{_n(((public_deck or {}).get('sent') or {}).get('today'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('sent') or {}).get('period'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('sent') or {}).get('total'))}</b>\n"
            f"    ◦ открытий в чате: <b>{_n(((public_deck or {}).get('opened_chat') or {}).get('today'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('opened_chat') or {}).get('period'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('opened_chat') or {}).get('total'))}</b>\n"
            f"    ◦ открытий в личке: <b>{_n(((public_deck or {}).get('opened_dm') or {}).get('today'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('opened_dm') or {}).get('period'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('opened_dm') or {}).get('total'))}</b>\n"
            f"    ◦ свой расклад: <b>{_n(((public_deck or {}).get('own_spread') or {}).get('today'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('own_spread') or {}).get('period'))}</b> / "
            f"<b>{_n(((public_deck or {}).get('own_spread') or {}).get('total'))}</b>\n"
            f"    ◦ записей store: <b>{_n((public_deck or {}).get('posts_sent'))}</b> отправлено / "
            f"<b>{_n((public_deck or {}).get('posts_total'))}</b> всего\n"
            if public_deck
            else ""
        )
        + "\n<b>🖱 Популярные inline-кнопки за 7 дней</b>\n"
        + callback_lines
        +         f"\n<b>💾 Хранилище</b>\n"
        f"  • bot_state.sqlite3: <b>{html.escape(str(storage.get('integrity') or '—'))}</b>\n"
        f"  • Документов состояния: <b>{_n(storage.get('documents'))}</b>\n"
        "<i>SQLite · ежедневные проверяемые бэкапы · Europe/Moscow</i>\n\n"
        "<b>⌨️ Команды</b>\n"
        "  • <code>/admin123</code> — этот дашборд\n"
        "  • <code>/stats_date123 YYYY-MM-DD</code> — стата за день (SQLite analytics)\n"
        "  • <code>/who123</code> / <code>/who123 @user</code> — карточка пользователя\n"
        "  • <code>/grant123 @user</code> / <code>/grant123 @user 50</code> — выдать расклады\n"
        "  • <code>/denginam</code> — оплаты из JSON\n"
        "  • <code>/mod_reviews</code> — модерация отзывов\n"
        "  • <code>/popolnit_na123 N</code> — массовое пополнение\n"
        "  • <code>/tracklink partner|campaign …</code> — трекинг-ссылка"
        + (
            f"\n  • <code>/{html.escape(str(secret_stats_cmd))}</code> — пользователи (секрет)"
            if secret_stats_cmd
            else ""
        )
    )
