"""Admin dashboard v2: one-screen summary + detail sections behind buttons.

Pure functions: they only format already collected numbers, so they are easy to test.
Lines whose numbers are all zero are hidden in detail sections (dead features
disappear by themselves and come back once they get traffic again).
"""
from __future__ import annotations

import html
from typing import Any, Mapping, Optional

SECTIONS: dict[str, str] = {
    "readings": "🔮 Расклады",
    "money": "💳 Оплаты",
    "growth": "📣 Откуда люди",
    "share": "📤 Шеринг и рефералы",
    "deck": "🃏 Своя колода",
    "more": "⚙️ Прочее и команды",
}


SOURCE_LABELS: dict[str, str] = {
    "direct": "напрямую (без ссылки)",
    "landing": "с сайта",
    "referral": "приглашение друга",
    "share": "по ссылке «поделиться»",
    "compat": "приглашение в «Совместимость»",
    "partner": "партнёры",
    "campaign": "трекинг-ссылки / реклама",
    "other": "другие ссылки",
    "invalid": "битые ссылки",
    "unknown": "неизвестно",
}

PLAN_LABELS: dict[str, str] = {
    "10": "10 раскладов",
    "31d": "подписка на месяц",
    "93d": "подписка на 3 месяца",
    "365d": "подписка на год",
}


def _n(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pct(part: int, total: int) -> str:
    return f"{100 * part / total:.0f}%" if total else "—"


def _rub(kopecks: Any) -> str:
    rub = _n(kopecks) / 100
    text = f"{rub:,.0f}".replace(",", " ")
    return f"{text} ₽"


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def trend(cur: int, prev: int) -> str:
    """'↑ было 30' / '↓ было 30' / '= как неделей раньше'."""
    cur, prev = _n(cur), _n(prev)
    if cur == prev:
        return " <i>(= как неделей раньше)</i>" if cur else ""
    arrow = "↑" if cur > prev else "↓"
    return f" <i>({arrow} было {prev})</i>"


def _u(period: Mapping[str, Any], metric: str) -> int:
    return _n((period.get("unique") or {}).get(metric))


def _c(period: Mapping[str, Any], metric: str) -> int:
    return _n((period.get("counts") or {}).get(metric))


def _three(periods: Mapping[str, Any], metric: str, *, unique: bool) -> tuple[int, int, int]:
    get = _u if unique else _c
    return (get(periods["today"], metric), get(periods["7d"], metric), get(periods["30d"], metric))


def _row(label: str, values: tuple[int, int, int], *, hide_zero: bool = True) -> str:
    if hide_zero and not any(values):
        return ""
    a, b, c = values
    return f"  • {label}: <b>{a}</b> / <b>{b}</b> / <b>{c}</b>\n"


def _source_lines(sources: Mapping[str, Any], limit: int = 5) -> str:
    items = [(str(k), _n(v)) for k, v in (sources or {}).items() if _n(v)]
    items.sort(key=lambda kv: -kv[1])
    if not items:
        return "  • пока нет данных\n"
    shown = items[:limit]
    rest = sum(v for _, v in items[limit:])
    out = "".join(f"  • {_esc(SOURCE_LABELS.get(k, k))}: <b>{v}</b>\n" for k, v in shown)
    if rest:
        out += f"  • остальные: <b>{rest}</b>\n"
    return out


# ---------------------------------------------------------------- summary


def build_summary(
    snapshot: Mapping[str, Any],
    *,
    users: Mapping[str, Any],
    reviews: Mapping[str, Any],
    max_stats: Optional[Mapping[str, Any]] = None,
) -> str:
    periods = snapshot["periods"]
    week = periods["7d"]
    month = periods["30d"]
    prev = snapshot.get("prev_7d") or {"counts": {}, "unique": {}}

    active, active_prev = _n(week.get("active_users")), _n(prev.get("active_users"))
    new, new_prev = _u(week, "user_registered"), _u(prev, "user_registered")
    readings, readings_prev = _c(week, "reading_completed"), _c(prev, "reading_completed")
    readers = _u(week, "reading_completed")
    compat_users = _u(week, "compat_short_done")

    intent = _u(week, "payment_intent")
    checkout = _u(week, "payment_checkout")
    paid, paid_prev = _u(week, "payment_succeeded"), _u(prev, "payment_succeeded")
    revenue, revenue_prev = _n(week.get("revenue_kopecks")), _n(prev.get("revenue_kopecks"))
    abandoned = _n((snapshot.get("abandoned_checkouts_7d") or {}).get("abandoned"))

    act = snapshot.get("activation_7d") or {}
    d1 = snapshot.get("retention_d1") or {}

    shared = _u(week, "share_opened")
    via_share = _u(week, "share_link_started")

    out = [
        "<b>📊 Сводка за 7 дней</b>\n",
        f"<i>{_esc(snapshot.get('generated_at', ''))} · в скобках — прошлая неделя</i>\n\n",
        "<b>👥 Люди</b>\n",
        f"  • Пользовались ботом: <b>{active}</b>{trend(active, active_prev)}\n",
        f"  • Новые: <b>{new}</b>{trend(new, new_prev)}\n",
        f"  • Новые сделали расклад в первые сутки: <b>{_n(act.get('activated_24h'))}</b> "
        f"из {_n(act.get('registered'))}\n",
        f"  • Вернулись на следующий день: <b>{_pct(_n(d1.get('returned')), _n(d1.get('cohort')))}</b>\n\n",
        "<b>🔮 Расклады</b>\n",
        f"  • Сделано: <b>{readings}</b>{trend(readings, readings_prev)}, людей: <b>{readers}</b>\n",
    ]
    if compat_users or _u(week, "compat_start"):
        out.append(f"  • Из них «Совместимость»: <b>{compat_users}</b> чел.\n")
    out += [
        "\n<b>💳 Деньги</b>\n",
        f"  • Открыли тарифы → получили ссылку → оплатили: "
        f"<b>{intent}</b> → <b>{checkout}</b> → <b>{paid}</b>{trend(paid, paid_prev)}\n",
        f"  • Выручка: <b>{_rub(revenue)}</b>{trend(revenue // 100, revenue_prev // 100)}; "
        f"за 30 дней <b>{_rub(month.get('revenue_kopecks'))}</b>\n",
    ]
    if abandoned:
        out.append(f"  • Получили ссылку и не оплатили: <b>{abandoned}</b> чел.\n")
    out.append(f"  • Активных подписок: <b>{_n(users.get('active_subs'))}</b>\n\n")

    out.append("<b>🧭 Откуда пришли новые</b>\n")
    out.append(_source_lines(snapshot.get("acquisition_sources_7d") or {}, limit=4))

    broadcasts = snapshot.get("broadcasts_7d") or {}
    if broadcasts:
        sent = sum(_n(b.get("sent")) for b in broadcasts.values())
        back = sum(_n(b.get("returned")) for b in broadcasts.values())
        out.append(
            f"\n<b>📨 Рассылки</b>\n"
            f"  • Получили: <b>{sent}</b> чел., открыли бота в течение 3 дней: "
            f"<b>{back}</b> ({_pct(back, sent)})\n"
        )

    out.append(
        f"\n<b>📤 Поделились раскладом</b>: <b>{shared}</b> чел., "
        f"пришли по их ссылкам: <b>{via_share}</b>\n"
    )

    if max_stats and (_n(max_stats.get("users")) or _n(max_stats.get("users_prev"))):
        out.append(
            f"<b>📱 Бот в MAX</b>: пользовались <b>{_n(max_stats.get('users'))}</b> чел."
            f"{trend(_n(max_stats.get('users')), _n(max_stats.get('users_prev')))}\n"
        )

    pending = _n(reviews.get("pending"))
    if pending:
        out.append(f"\n⭐ Отзывов ждут проверки: <b>{pending}</b> — /mod_reviews\n")

    out.append("\n<i>Подробности — кнопками ниже.</i>")
    return "".join(out)


# ---------------------------------------------------------------- sections

_HEAD_3 = "<i>сегодня / 7 дней / 30 дней</i>\n"


def build_section(
    name: str,
    snapshot: Mapping[str, Any],
    *,
    users: Mapping[str, Any],
    reviews: Mapping[str, Any],
    leads: Mapping[str, Any],
    tomorrow: Mapping[str, Any],
    nurture: Mapping[str, Any],
    payment_data: Mapping[str, Any],
    kind_labels: Mapping[str, str],
    compat_html: str = "",
    secret_stats_cmd: Optional[str] = None,
) -> str:
    periods = snapshot["periods"]
    week, month = periods["7d"], periods["30d"]

    if name == "readings":
        kinds = week.get("reading_kinds") or {}
        kind_lines = "".join(
            f"  • {_esc(kind_labels.get(str(k), str(k)))}: <b>{_n(v)}</b>\n"
            for k, v in sorted(kinds.items(), key=lambda kv: -_n(kv[1]))
        ) or "  • нет данных\n"
        act7, act30 = snapshot.get("activation_7d") or {}, snapshot.get("activation_30d") or {}
        d1, d7 = snapshot.get("retention_d1") or {}, snapshot.get("retention_d7") or {}
        return (
            "<b>🔮 Расклады</b>\n" + _HEAD_3
            + _row("Сделано (без уточнений)", _three(periods, "reading_completed", unique=False), hide_zero=False)
            + _row("Людей", _three(periods, "reading_completed", unique=True), hide_zero=False)
            + _row("Уточнения", _three(periods, "clarify_completed", unique=False))
            + _row("Ошибки при раскладе", _three(periods, "reading_failed", unique=False))
            + "\n<b>По видам за 7 дней</b>\n" + kind_lines
            + "\n<b>Новички и возвраты</b>\n"
            f"  • Первый расклад в первые сутки: 7 дн. <b>{_n(act7.get('activated_24h'))}</b>/{_n(act7.get('registered'))}, "
            f"30 дн. <b>{_n(act30.get('activated_24h'))}</b>/{_n(act30.get('registered'))}\n"
            f"  • Вернулись на следующий день: <b>{_pct(_n(d1.get('returned')), _n(d1.get('cohort')))}</b>, "
            f"через неделю: <b>{_pct(_n(d7.get('returned')), _n(d7.get('cohort')))}</b>\n"
            f"  • Вернулись после месяца тишины (7 дн.): <b>{_n(snapshot.get('resurrected_7d'))}</b>\n"
            + "\n<b>Карта на завтра</b>\n"
            f"  • Включили напоминание: <b>{_n(tomorrow.get('push_enabled'))}</b>\n"
            + _row("Открыли карту", _three(periods, "tomorrow_opened", unique=False))
            + ("\n" + compat_html.strip() + "\n" if compat_html else "")
        )

    if name == "money":
        ab7 = snapshot.get("abandoned_checkouts_7d") or {}
        ab30 = snapshot.get("abandoned_checkouts_30d") or {}
        plans = payment_data.get("subscriptions") or {}
        plan_lines = (
            "".join(
                f"  • {_esc(PLAN_LABELS.get(str(p), str(p)))}: <b>{_n(c)}</b>\n"
                for p, c in plans.items() if _n(c)
            )
            if isinstance(plans, Mapping) else ""
        )
        i30, c30, p30 = _u(month, "payment_intent"), _u(month, "payment_checkout"), _u(month, "payment_succeeded")
        return (
            "<b>💳 Оплаты</b>\n" + _HEAD_3
            + _row("Открыли тарифы", _three(periods, "payment_intent", unique=True), hide_zero=False)
            + _row("Получили ссылку", _three(periods, "payment_checkout", unique=True), hide_zero=False)
            + _row("Оплатили", _three(periods, "payment_succeeded", unique=True), hide_zero=False)
            + _row("Ошибки оплаты", _three(periods, "payment_failed", unique=False))
            + f"  • За 30 дней: тарифы → ссылка <b>{_pct(c30, i30)}</b>, ссылка → оплата <b>{_pct(p30, c30)}</b>\n"
            f"  • Выручка: сегодня <b>{_rub(periods['today'].get('revenue_kopecks'))}</b>, "
            f"7 дн. <b>{_rub(week.get('revenue_kopecks'))}</b>, 30 дн. <b>{_rub(month.get('revenue_kopecks'))}</b>\n"
            f"  • Получили ссылку и не оплатили: 7 дн. <b>{_n(ab7.get('abandoned'))}</b> из {_n(ab7.get('got_link'))}, "
            f"30 дн. <b>{_n(ab30.get('abandoned'))}</b> из {_n(ab30.get('got_link'))}\n"
            f"  • Напоминания об оплате сейчас ждут: тарифы <b>{_n(nurture.get('intent_open'))}</b>, "
            f"ссылка <b>{_n(nurture.get('checkout_open'))}</b>\n"
            "\n<b>Подписки и баланс</b>\n"
            f"  • Активных подписок: <b>{_n(users.get('active_subs'))}</b>\n"
            f"  • Закончились расклады, подписки нет: <b>{_n(users.get('zero_questions'))}</b>\n"
            + _row("Промокод введён", _three(periods, "promo_redeemed", unique=False))
            + _row("Промокод не подошёл", _three(periods, "promo_rejected", unique=False))
            + f"\n<b>Старый учёт (за всё время)</b>\n"
            f"  • Сумма: <b>{_rub(payment_data.get('total_amount'))}</b>\n"
            + plan_lines
        )

    if name == "growth":
        out = [
            "<b>📣 Откуда люди</b>\n",
            f"  • В базе всего: <b>{_n(users.get('total'))}</b>, оставили email: <b>{_n(users.get('with_email'))}</b>\n",
            "\n<b>Источники новых за 30 дней</b>\n",
            _source_lines(snapshot.get("acquisition_sources_30d") or {}, limit=10),
        ]
        for title, key in (("Партнёры", "partner_funnel_30d"), ("Кампании / трекинг-ссылки", "campaign_funnel_30d")):
            rows = snapshot.get(key) or {}
            if not rows:
                continue
            out.append(f"\n<b>{title} — 30 дней</b>\n<i>переходы → новые → сделали расклад → оплатили</i>\n")
            for code, row in rows.items():
                row = row if isinstance(row, Mapping) else {}
                out.append(
                    f"  • <code>{_esc(code)}</code>: {_n(row.get('starts'))} → {_n(row.get('signups'))} → "
                    f"{_n(row.get('activated'))} → {_n(row.get('paid'))}\n"
                )
        broadcasts = snapshot.get("broadcasts_7d") or {}
        if broadcasts:
            out.append("\n<b>Рассылки за 7 дней</b> <i>(получили → открыли бота за 3 дня)</i>\n")
            for camp, b in broadcasts.items():
                out.append(
                    f"  • <code>{_esc(camp)}</code>: {_n(b.get('sent'))} → {_n(b.get('returned'))} "
                    f"({_pct(_n(b.get('returned')), _n(b.get('sent')))})\n"
                )
        return "".join(out)

    if name == "share":
        top = users.get("top_referrers") or []
        top_lines = "".join(f"  • <code>{int(uid)}</code>: <b>{_n(cnt)}</b>\n" for uid, cnt in top[:5])
        return (
            "<b>📤 Шеринг и рефералы</b>\n" + _HEAD_3
            + _row("Поделились раскладом (людей)", _three(periods, "share_opened", unique=True), hide_zero=False)
            + _row("Перешли по их ссылкам", _three(periods, "share_link_started", unique=True), hide_zero=False)
            + _row("Стали новыми пользователями", _three(periods, "referral_share_signup", unique=True))
            + _row("Пришли по реферальной ссылке", _three(periods, "referral_link_signup", unique=True))
            + _row("Из них сделали расклад", _three(periods, "referral_activated", unique=True))
            + "\n<b>Реферальная программа (всё время)</b>\n"
            f"  • Пришли по приглашению: <b>{_n(users.get('referred_users'))}</b>\n"
            f"  • Приглашали хоть раз: <b>{_n(users.get('referrers'))}</b> чел.\n"
            + ("<b>Топ приглашающих</b>\n" + top_lines if top_lines else "")
        )

    if name == "deck":
        body = (
            _row("Создали свою колоду", _three(periods, "public_deck_created", unique=True))
            + _row("Открыли колоду", _three(periods, "public_deck_opened", unique=True))
            + _row("Открыли в личке", _three(periods, "public_deck_opened_dm", unique=True))
            + _row("Открыли в чате", _three(periods, "public_deck_opened_chat", unique=True))
            + _row("Отправили в чат", _three(periods, "public_deck_sent", unique=True))
            + _row("Задали свой вопрос", _three(periods, "public_deck_own_spread", unique=True))
        )
        return "<b>🃏 Своя колода</b> <i>(людей)</i>\n" + _HEAD_3 + (body or "  • за 30 дней никто не пользовался\n")

    if name == "more":
        storage = snapshot.get("operational_storage") or {}
        integrity = str(storage.get("integrity") or "—")
        return (
            "<b>⚙️ Прочее</b>\n"
            f"  • Отзывы: ждут <b>{_n(reviews.get('pending'))}</b>, одобрены <b>{_n(reviews.get('approved'))}</b>, "
            f"отклонены <b>{_n(reviews.get('rejected'))}</b>\n"
            f"  • Заявки на консультацию: 7 дн. <b>{_n(leads.get('period'))}</b>, всего <b>{_n(leads.get('total'))}</b>\n"
            + ("" if integrity.lower() == "ok" else f"  • ⚠️ База состояния: <b>{_esc(integrity)}</b>\n")
            + "\n<b>⌨️ Команды</b>\n"
            "  • <code>/admin123</code> — эта сводка\n"
            "  • <code>/stats_date123 ГГГГ-ММ-ДД</code> — цифры за один день\n"
            "  • <code>/who123 @user</code> — карточка пользователя\n"
            "  • <code>/grant123 @user 50</code> — выдать расклады\n"
            "  • <code>/denginam</code> — оплаты\n"
            "  • <code>/mod_reviews</code> — проверка отзывов\n"
            "  • <code>/popolnit_na123 N</code> — пополнить всем\n"
            "  • <code>/tracklink partner|campaign …</code> — трекинг-ссылка\n"
            + (f"  • <code>/{_esc(secret_stats_cmd)}</code> — пользователи\n" if secret_stats_cmd else "")
        )

    return "Неизвестный раздел."
