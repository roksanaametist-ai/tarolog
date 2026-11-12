"""Платная полная «Совместимость» (99 ₽ / 69 ⭐): заказы, защита от двойного начисления."""

from __future__ import annotations

from bot_core import compat_paid, robokassa_store
from bot_core import robokassa_fulfill as rf
from bot_core.compat import CompatInviteStore
from bot_core.operational_store import OperationalStore


class Clock:
    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _orders(tmp_path, clock=None):
    return compat_paid.CompatOrderStore(
        OperationalStore(tmp_path / "bot_state.sqlite3"), now=clock or Clock()
    )


def _cards(n=3):
    return [{"path": f"c{i}.jpg", "label": f"Карта {i}", "reversed": False} for i in range(n)]


def test_register_same_payment_twice_creates_one_order(tmp_path):
    orders = _orders(tmp_path)
    key = compat_paid.stars_key("charge-1")
    created, rec = orders.register(key, chat_id=5, invite_id="inv123", method="stars", amount_stars=69)
    assert created and rec["status"] == "paid"
    created2, rec2 = orders.register(key, chat_id=5, invite_id="inv123", method="stars", amount_stars=69)
    assert not created2 and rec2["created_at"] == rec["created_at"]
    assert len(orders.for_invite("inv123")) == 1


def test_begin_delivery_is_exclusive_and_retry(tmp_path):
    clock = Clock()
    orders = _orders(tmp_path, clock)
    key = compat_paid.robokassa_key(42)
    orders.register(key, chat_id=5, invite_id="inv123", method="robokassa", amount_kopecks=9900)
    assert orders.begin_delivery(key, force=True)
    # второй обработчик (опрос / цикл) этот же заказ не берёт
    assert orders.begin_delivery(key, force=True) is None
    assert orders.due() == []
    # выдача упала — повтор только через паузу
    after = orders.fail(key)
    assert after["status"] == "paid"
    assert orders.begin_delivery(key) is None
    clock.t += compat_paid.RETRY_SECONDS + 1
    assert [r["key"] for r in orders.due()] == [key]
    assert orders.begin_delivery(key)
    orders.finish(key)
    assert orders.get(key)["status"] == "delivered"
    assert orders.begin_delivery(key, force=True) is None
    assert orders.due() == []


def test_stale_delivery_is_picked_up_again(tmp_path):
    clock = Clock()
    orders = _orders(tmp_path, clock)
    key = compat_paid.robokassa_key(43)
    orders.register(key, chat_id=5, invite_id="inv123", method="robokassa")
    assert orders.begin_delivery(key, force=True)
    clock.t += compat_paid.DELIVERING_STALE_SECONDS + 1  # бот перезапустился посреди выдачи
    assert [r["key"] for r in orders.due()] == [key]


def test_attempts_run_out_to_failed(tmp_path):
    clock = Clock()
    orders = _orders(tmp_path, clock)
    key = compat_paid.robokassa_key(44)
    orders.register(key, chat_id=5, invite_id="inv123", method="robokassa")
    for _ in range(compat_paid.MAX_ATTEMPTS):
        clock.t += compat_paid.RETRY_SECONDS + 1
        assert orders.begin_delivery(key)
        last = orders.fail(key)
    assert last["status"] == "failed"
    clock.t += 10_000
    assert orders.due() == []


def test_stars_payload_roundtrip():
    assert compat_paid.parse_stars_payload(compat_paid.stars_payload("abcDEF12")) == "abcDEF12"
    assert compat_paid.parse_stars_payload("sub:abc") is None
    assert compat_paid.parse_stars_payload("compat:x") is None


def test_pay_screen_text_has_note():
    text = compat_paid.pay_screen_text("Маша")
    assert "Маша ничего не узнает" in text
    assert "в безлимит не входит" in text


def _invite(tmp_path):
    store = CompatInviteStore(OperationalStore(tmp_path / "bot_state.sqlite3"))
    inv = store.create_invite(inviter_id=5, inviter_name="Аня", partner_name="Маша", topic="love", cards=_cards())
    return store, inv


def test_paid_full_saved_once_and_partner_gets_same(tmp_path):
    store, inv = _invite(tmp_path)
    payment = {"key": "rk:1", "method": "robokassa"}
    # чужой не может сохранить
    assert store.save_paid_full(inv["id"], 999, cards=_cards(5), roles=[], texts=[], summary="", payment=payment) is None
    saved = store.save_paid_full(
        inv["id"], 5, cards=_cards(5), roles=["r"] * 5, texts=["t"] * 5, summary="итог", payment=payment
    )
    assert saved["full"]["summary"] == "итог" and saved["paid"]["key"] == "rk:1"
    assert saved["status"] == "open"  # партнёр ещё может прийти по ссылке
    again = store.save_paid_full(
        inv["id"], 5, cards=_cards(5), roles=[], texts=[], summary="другой", payment={"key": "rk:2"}
    )
    assert again["full"]["summary"] == "итог"  # не перезаписан
    # партнёр открывает приглашение — расклад уже лежит, генерация не нужна
    res = store.claim(inv["id"], 777, "Маша")
    assert res.status == "ok"
    assert res.invite["full"]["summary"] == "итог"


def _robokassa_env(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(robokassa_store, "store_path", lambda: tmp_path / "robokassa_invoices.json")
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)


def test_robokassa_compat_invoice_registers_order_once_no_subscription(tmp_path, monkeypatch):
    _robokassa_env(tmp_path, monkeypatch)
    robokassa_store.put_pending(
        501,
        chat_id=5,
        plan_key=compat_paid.PLAN_KEY,
        amount_kopecks=9900,
        kind=compat_paid.INVOICE_KIND,
        extra={"invite_id": "inv123"},
    )
    first = rf.fulfill_invoice(501, out_sum="99.00")
    assert first["ok"] and first["kind"] == "compat" and not first["already"]
    second = rf.fulfill_invoice(501, out_sum="99.00")  # повторный ResultURL
    assert second["ok"] and second["already"]
    orders = _orders(tmp_path).for_invite("inv123")
    assert len(orders) == 1 and orders[0]["key"] == "rk:501" and orders[0]["amount_kopecks"] == 9900
    # подписка не выдана
    assert not (tmp_path / "user_data.json").exists() or "subscription_end" not in (
        tmp_path / "user_data.json"
    ).read_text(encoding="utf-8")


def test_compat_invoice_without_invite_is_not_acked(tmp_path, monkeypatch):
    _robokassa_env(tmp_path, monkeypatch)
    robokassa_store.put_pending(
        502, chat_id=5, plan_key=compat_paid.PLAN_KEY, amount_kopecks=9900, kind=compat_paid.INVOICE_KIND
    )
    assert rf.fulfill_invoice(502)["ok"] is False
