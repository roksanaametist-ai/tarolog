from analytics.store import AnalyticsStore
from bot_core import robokassa_fulfill as rf


def test_robokassa_payment_tracked_once(tmp_path, monkeypatch):
    monkeypatch.setattr(rf, "_data_dir", lambda: tmp_path)
    seed = {"acquisition_source": "landing"}
    assert rf._track_payment_succeeded(77, 123, "sub_m_555", 55500, "parent", seed) is True
    # repeated ResultURL / poll must not double count
    assert rf._track_payment_succeeded(77, 123, "sub_m_555", 55500, "parent", seed) is False
    snap = AnalyticsStore(tmp_path / "analytics.sqlite3").snapshot()
    week = snap["periods"]["7d"]
    assert week["counts"].get("payment_succeeded") == 1
    assert week["revenue_kopecks"] == 55500


def test_robokassa_tracking_never_raises(tmp_path, monkeypatch):
    def boom():
        raise RuntimeError("disk")
    monkeypatch.setattr(rf, "_data_dir", boom)
    assert rf._track_payment_succeeded(1, 1, "", 0, "parent", None) is False
