"""[049] MAX на Робокассе: счёт, выдача безлимита в кошелёк "max", без двойной выдачи."""

from __future__ import annotations

import importlib
import sys
import urllib.parse
from datetime import datetime, timedelta

import pytest

import shared_wallet
from bot_core import robokassa_fulfill as rf
from bot_core import robokassa_store


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_BOT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ROBOKASSA_LOGIN", "test-shop")
    monkeypatch.setenv("ROBOKASSA_PASSWORD1", "p1-test")
    monkeypatch.setenv("ROBOKASSA_PASSWORD2", "p2-test")
    monkeypatch.setattr(robokassa_store, "store_path", lambda: tmp_path / "robokassa_invoices.json")
    monkeypatch.setattr(rf, "_data_dir", lambda: tmp_path)
    sent: list[tuple[str, int, str]] = []
    monkeypatch.setattr(rf, "notify_max", lambda uid, text: sent.append(("max", uid, text)) or True)
    monkeypatch.setattr(rf, "notify_telegram", lambda cid, text: sent.append(("tg", cid, text)) or True)
    return tmp_path, sent


def _put_max(inv_id: int, user_id: int = 777, plan: str = "sub_m_555", kop: int = 55500):
    robokassa_store.put_pending(
        inv_id, chat_id=user_id, plan_key=plan, amount_kopecks=kop, kind="parent", extra={"platform": "max"}
    )


def test_max_invoice_grants_once(env):
    _tmp, sent = env
    _put_max(50000001)
    first = rf.fulfill_invoice(50000001, out_sum="555.00")
    assert first["ok"] and not first["already"] and first["platform"] == "max"
    wallet = shared_wallet.view("max", 777)
    end = datetime.strptime(wallet["subscription_end"], "%Y-%m-%d %H:%M:%S")
    assert timedelta(days=30, hours=23) < end - datetime.now() <= timedelta(days=31)
    assert wallet["subscription_plan_key"] == "sub_m_555"
    assert wallet["auto_renew"] is False
    assert sent == [("max", 777, sent[0][2])] and "Безлимит до" in sent[0][2]

    # повторный ResultURL и запасная проверка — второй раз не выдаём и не пишем
    assert rf.fulfill_invoice(50000001)["already"] is True
    assert shared_wallet.view("max", 777)["subscription_end"] == wallet["subscription_end"]
    assert robokassa_store.get_invoice(50000001)["fulfilled"] is True
    assert len(sent) == 1


def test_parallel_claim_only_once(env):
    _put_max(50000002)
    robokassa_store.mark_paid(50000002)
    assert robokassa_store.claim_grant(50000002) is True
    assert robokassa_store.claim_grant(50000002) is False
    # fulfill после уже занятой выдачи — ничего не добавляет
    res = rf.fulfill_invoice(50000002)
    assert res["already"] is True
    assert not shared_wallet.view("max", 777).get("subscription_end")


def test_max_stacks_on_active_subscription(env):
    future = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    shared_wallet.update("max", 777, None, {"subscription_end": future.strftime("%Y-%m-%d %H:%M:%S")})
    _put_max(50000003, plan="sub_m_111", kop=11100)
    res = rf.fulfill_invoice(50000003)
    new_end = datetime.strptime(res["subscription_end"], "%Y-%m-%d %H:%M:%S")
    assert new_end == future + timedelta(days=31)


def test_tg_invoice_not_routed_to_max(env, monkeypatch):
    _tmp, sent = env
    robokassa_store.put_pending(60, chat_id=555, plan_key="sub_m_111", amount_kopecks=11100)
    called = {}
    monkeypatch.setattr(rf, "_fulfill_max", lambda *a, **k: called.setdefault("max", True))
    monkeypatch.setattr(
        rf, "_grant_in_store", lambda *a, **k: (True, {"subscription_end": "2030-01-01 00:00:00", "auto_renew": False})
    )
    res = rf.fulfill_invoice(60)
    assert res["ok"] and "max" not in called
    assert sent and sent[0][0] == "tg"


def test_max_checkout_link_and_pending(env, monkeypatch):
    tmp, _sent = env
    for mod in [m for m in sys.modules if m == "max_bot" or m.startswith("max_bot.")]:
        sys.modules.pop(mod)
    payments = importlib.import_module("max_bot.payments")
    monkeypatch.setattr(payments.user_data, "get_user_email", lambda uid: "buyer@example.com")
    inv_id, url = payments.create_checkout(4242, "sub_m_999")
    assert inv_id > payments.MAX_INV_BASE
    rec = robokassa_store.get_invoice(inv_id)
    assert rec["platform"] == "max" and rec["chat_id"] == 4242 and rec["amount_kopecks"] == 99900
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["OutSum"] == ["999.00"] or q["OutSum"][0].startswith("999")
    assert q["Shp_platform"] == ["max"] and q["Shp_plan"] == ["sub_m_999"]
    assert "Recurring" not in q

    # номер уже занят Telegram-счётом — берётся следующий свободный
    robokassa_store.put_pending(inv_id + 1, chat_id=1, plan_key="sub_m_111", amount_kopecks=11100)
    inv2, _ = payments.create_checkout(4242, "sub_m_111")
    assert inv2 == inv_id + 2
