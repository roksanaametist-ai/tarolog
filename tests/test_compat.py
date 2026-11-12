"""Тесты «💞 Совместимости»: весь поток через диспетчер aiogram, без сети.

Запуск из корня репозитория:  python -m pytest tests -q
"""

from __future__ import annotations

import asyncio
import itertools

import pytest

from tests import compat_harness as h

main, session = h.setup_main()
loop = asyncio.new_event_loop()
_ids = itertools.count(7_000_001)


def run(coro):
    return loop.run_until_complete(coro)


def feed(update):
    return run(main.dp.feed_update(main.bot, update))


def new_uid() -> int:
    return next(_ids)


def make_old_user(uid: int, questions: int = 0) -> None:
    main.user_data.add_user(uid)
    main.agreement_manager.add_user_agreement(uid)
    if questions:
        main.user_data.increment_user_questions(uid, questions)


def balance(uid: int) -> int:
    return main.user_data.get_user_questions(uid)


def invites_doc():
    return main.compat_store.get  # noqa: E731


def make_invite(uid: int, partner: str = "Анна", name: str = "Роксана") -> str:
    """Инициатор проходит короткий расклад; возвращает id приглашения."""
    feed(h.msg_update(uid, main.COMPAT_BUTTON, first_name=name))
    feed(h.cb_update(uid, "compat_topic:love", first_name=name))
    feed(h.cb_update(uid, "compat_self_yes", first_name=name))
    feed(h.msg_update(uid, partner, first_name=name))
    btn = session.find_button(uid, "compat_inv:")
    assert btn, f"нет кнопки приглашения; сообщения: {session.texts(uid)[-5:]}"
    return btn["data"].split(":", 1)[1]


def full_headers(uid: int):
    return [t for t in session.texts(uid) if "полный расклад" in t and "+" in t]


def open_link(uid: int, invite_id: str, name: str = "Анна"):
    feed(h.msg_update(uid, f"/start compat_{invite_id}", first_name=name))


def accept_full(uid: int, invite_id: str, name: str = "Анна"):
    feed(h.cb_update(uid, f"compat_view:{invite_id}", first_name=name))
    feed(h.cb_update(uid, f"compat_inv_yes:{invite_id}", first_name=name))


# ---------------------------------------------------------------- tests


def test_create_invite_short_spread():
    a = new_uid()
    make_old_user(a, questions=3)
    before = balance(a)
    inv_id = make_invite(a)
    inv = main.compat_store.get(inv_id)
    assert inv and inv["inviter_id"] == a and inv["partner_name"] == "Анна"
    assert len(inv["cards"]) == 3
    assert balance(a) == before - 1, "короткий расклад списывает ровно 1"
    texts = session.texts(a)
    assert any("Роксана + Анна" in t for t in texts)
    # кнопка «Позвать» → текст приглашения со ссылкой и share-кнопкой
    feed(h.cb_update(a, f"compat_inv:{inv_id}", first_name="Роксана"))
    share = session.find_button(a, "📩")
    assert share and share.get("url", "").startswith("https://t.me/share/url")
    assert f"compat_{inv_id}" in session.texts(a)[-1]


def test_open_by_existing_user_no_bonus_and_both_get_full():
    a, b = new_uid(), new_uid()
    make_old_user(a, questions=3)
    make_old_user(b, questions=2)
    inv_id = make_invite(a)
    a_after_short, b_before = balance(a), balance(b)

    open_link(b, inv_id)
    assert any("Роксана позвал(а) тебя" in t for t in session.texts(b))
    accept_full(b, inv_id)

    assert len(full_headers(b)) == 1, "приглашённый получил полный расклад"
    assert any("откликнулся(ась)" in t for t in session.texts(a)), "инициатор тоже получил"
    assert balance(a) == a_after_short, "у инициатора ничего не списано и бонусов нет"
    assert balance(b) == b_before, "у приглашённого ничего не списано"
    assert main.user_data.get_referred_by(b) is None, "старый пользователь не становится рефералом"
    inv = main.compat_store.get(inv_id)
    assert inv["status"] == "completed" and len(inv["full"]["cards"]) == 5
    assert [c["path"] for c in inv["full"]["cards"][:3]] == [c["path"] for c in inv["cards"]]
    # кнопки после полного расклада
    assert session.find_button(b, f"compat_story:{inv_id}")
    assert session.find_button(b, f"compat_live:{inv_id}")


def test_open_by_new_user_is_referral():
    a, b = new_uid(), new_uid()
    make_old_user(a, questions=3)
    inv_id = make_invite(a)
    a_before = balance(a)

    open_link(b, inv_id, name="Маша")
    assert main.user_data.get_referred_by(b) == a
    assert balance(a) == a_before + main.REFERRAL_JOIN_BONUS
    # согласие → сразу экран приглашения
    agree = session.find_button(b, "agree")
    assert agree, session.texts(b)
    feed(h.cb_update(b, agree["data"], first_name="Маша"))
    assert any("позвал(а) тебя" in t for t in session.texts(b))
    b_before = balance(b)
    accept_full(b, inv_id, name="Маша")
    assert len(full_headers(b)) == 1
    assert balance(b) == b_before, "полный расклад бесплатный"


def test_open_own_link():
    a = new_uid()
    make_old_user(a, questions=2)
    inv_id = make_invite(a)
    before = balance(a)
    open_link(a, inv_id, name="Роксана")
    assert "Это твоё приглашение — перешли его тому, кого зовёшь 💞" in session.texts(a)[-1]
    assert main.compat_store.get(inv_id)["status"] != "completed"
    assert balance(a) == before


def test_expired_invite():
    a, b = new_uid(), new_uid()
    make_old_user(a, questions=2)
    make_old_user(b)
    inv_id = make_invite(a)
    real_now = main.compat_store.now
    try:
        main.compat_store.now = lambda: real_now() + 31 * 24 * 3600
        open_link(b, inv_id)
        assert "Приглашение устарело" in session.texts(b)[-1]
        accept_full(b, inv_id)
        assert not full_headers(b)
    finally:
        main.compat_store.now = real_now


def test_reopen_shows_ready_spread_without_new_generation():
    a, b = new_uid(), new_uid()
    make_old_user(a, questions=2)
    make_old_user(b)
    inv_id = make_invite(a)
    open_link(b, inv_id)
    accept_full(b, inv_id)
    first = main.compat_store.get(inv_id)["full"]

    calls = {"n": 0}
    orig = main.get_tarot_reading_structured

    async def counting(*a, **kw):
        calls["n"] += 1
        return await orig(*a, **kw)

    main.get_tarot_reading_structured = counting
    try:
        open_link(b, inv_id)
        accept_full(b, inv_id)
    finally:
        main.get_tarot_reading_structured = orig
    assert calls["n"] == 0, "повторное открытие не зовёт нейросеть"
    assert any("уже открыт" in t for t in session.texts(b))
    assert main.compat_store.get(inv_id)["full"]["cards"] == first["cards"]
    # третий человек не может открыть чужое
    c = new_uid()
    make_old_user(c)
    open_link(c, inv_id)
    assert "уже открыл другой человек" in session.texts(c)[-1]


def test_double_click_gives_one_full_reading():
    a, b = new_uid(), new_uid()
    make_old_user(a, questions=2)
    make_old_user(b)
    inv_id = make_invite(a)
    feed(h.cb_update(b, f"compat_view:{inv_id}"))

    async def both():
        await asyncio.gather(
            main.dp.feed_update(main.bot, h.cb_update(b, f"compat_inv_yes:{inv_id}")),
            main.dp.feed_update(main.bot, h.cb_update(b, f"compat_inv_yes:{inv_id}")),
        )

    run(both())
    assert len(full_headers(b)) == 1
    assert len([t for t in session.texts(a) if "откликнулся(ась)" in t]) == 1


def test_double_click_short_spends_once():
    a = new_uid()
    make_old_user(a, questions=3)
    before = balance(a)

    async def both():
        await asyncio.gather(
            main.run_compat_short(a, _state(a), self_name="Роксана", partner_name="Анна", topic="work"),
            main.run_compat_short(a, _state(a), self_name="Роксана", partner_name="Анна", topic="work"),
        )

    run(both())
    assert balance(a) == before - 1


def _state(uid: int):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey

    key = StorageKey(bot_id=main.bot.id, chat_id=uid, user_id=uid)
    return FSMContext(storage=main.dp.storage, key=key)


def test_referral_daily_cap():
    a = new_uid()
    make_old_user(a, questions=10)
    invites = [make_invite(a, partner=f"Друг{'а' * i}") for i in range(6)]
    start = balance(a)
    for inv_id in invites:
        open_link(new_uid(), inv_id, name="Новичок")
    cap = main.REFERRAL_JOIN_DAILY_CAP
    assert balance(a) == start + cap * main.REFERRAL_JOIN_BONUS
    assert main.user_data.get_referrals_count(a) >= 6


def test_back_and_menu_clear_fsm():
    a = new_uid()
    make_old_user(a, questions=2)
    feed(h.msg_update(a, main.COMPAT_BUTTON))
    assert run(_state(a).get_state()) == main.CompatFlow.topic.state
    feed(h.cb_update(a, "compat_back"))
    assert run(_state(a).get_state()) is None


def test_name_validation():
    assert main.validate_compat_name("Анна-Мария") == "Анна-Мария"
    assert main.validate_compat_name("http://spam.ru") is None
    assert main.validate_compat_name("x" * 31) is None
    a = new_uid()
    make_old_user(a, questions=2)
    feed(h.msg_update(a, main.COMPAT_BUTTON))
    feed(h.cb_update(a, "compat_topic:friend"))
    feed(h.cb_update(a, "compat_self_yes"))
    before = balance(a)
    feed(h.msg_update(a, "@spam_link"))
    assert "Имя — до 30 символов" in session.texts(a)[-1]
    assert balance(a) == before


def test_funnel_counts_and_html():
    counts = main.compat_funnel_counts(7)
    assert counts.get("compat_short_done", {}).get("events", 0) >= 1 or counts
    html_out = main.build_compat_funnel_html(counts, days=7)
    assert "Совместимость" in html_out
