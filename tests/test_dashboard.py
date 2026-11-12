from datetime import datetime, timedelta

from analytics.dashboard import SECTIONS, build_section, build_summary, trend
from analytics.store import MOSCOW, AnalyticsStore


def _store(tmp_path):
    s = AnalyticsStore(tmp_path / "a.sqlite3")
    now = datetime.now(MOSCOW)
    week_ago = now - timedelta(days=8)
    for uid in (1, 2, 3):
        s.track("user_registered", user_id=uid, occurred_at=now)
        s.track("reading_completed", user_id=uid, occurred_at=now, properties={"kind": "ask"})
    s.track("reading_completed", user_id=9, occurred_at=week_ago, properties={"kind": "ask"})
    s.track("payment_intent", user_id=1, occurred_at=now)
    s.track("payment_checkout", user_id=1, occurred_at=now)
    s.track("payment_checkout", user_id=2, occurred_at=now)
    s.track("payment_succeeded", user_id=2, occurred_at=now,
            properties={"amount_kopecks": 111100}, dedupe_key="p2")
    b_time = now - timedelta(hours=5)
    for uid in (1, 5):
        s.track("broadcast_sent", user_id=uid, occurred_at=b_time,
                properties={"campaign": "test-camp"})
    s.track("compat_start", user_id=3, occurred_at=now)
    s.track("compat_short_done", user_id=3, occurred_at=now)
    return s


def test_trend():
    assert "↑ было 2" in trend(5, 2)
    assert "↓ было 5" in trend(2, 5)
    assert trend(0, 0) == ""


def test_snapshot_new_metrics(tmp_path):
    snap = _store(tmp_path).snapshot()
    assert snap["prev_7d"]["counts"].get("reading_completed") == 1
    assert snap["abandoned_checkouts_7d"] == {"got_link": 2, "abandoned": 1}
    camp = snap["broadcasts_7d"]["test-camp"]
    assert camp["sent"] == 2 and camp["returned"] == 1  # user 1 acted after the broadcast


def test_summary_and_sections_render(tmp_path):
    snap = _store(tmp_path).snapshot()
    users = {"active_subs": 4, "total": 10}
    text = build_summary(snap, users=users, reviews={"pending": 2},
                         max_stats={"users": 0, "users_prev": 0})
    assert "Сводка за 7 дней" in text
    assert "<b>1 → </b>" not in text
    assert "1 111 ₽" in text
    assert "Получили ссылку и не оплатили: <b>1</b>" in text
    assert "Совместимость" in text
    assert "Рассылки" in text and "(50%)" in text
    assert "MAX" not in text  # nobody in MAX → line hidden
    assert "Отзывов ждут проверки: <b>2</b>" in text
    assert len(text) < 4000
    for name in SECTIONS:
        body = build_section(name, snap, users=users, reviews={}, leads={}, tomorrow={},
                             nurture={}, payment_data={}, kind_labels={"ask": "Вопрос"})
        assert body and "Неизвестный" not in body and len(body) < 4000
    deck = build_section("deck", snap, users=users, reviews={}, leads={}, tomorrow={},
                         nurture={}, payment_data={}, kind_labels={})
    assert "никто не пользовался" in deck  # all-zero rows are hidden
