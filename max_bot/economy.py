"""User balance, subscriptions, referrals — port of main.py UserData (MAX-only JSON)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import shared_wallet

from . import config

logger = logging.getLogger(__name__)


class UserData:
    def __init__(self, filename: Path | str | None = None) -> None:
        self.filename = Path(filename or config.USER_DATA_FILE)
        self.data: dict[str, dict[str, Any]] = self.load_data()

    def load_data(self) -> dict[str, dict[str, Any]]:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, dict) else {}
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            logger.warning("Broken user data file %s — starting empty", self.filename)
            return {}

    def save_data(self) -> None:
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def has_user(self, user_id: int) -> bool:
        return str(user_id) in self.data

    def add_user(self, user_id: int) -> None:
        key = str(user_id)
        if key in self.data:
            return
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data[key] = {
            "questions": 5,
            "subscription_end": None,
            "email": None,
            "last_refill_at": now_str,
            "referred_by": None,
            "referrals_count": 0,
            "active_referrals_count": 0,
            "first_reading_done": False,
            "referral_milestone_3": False,
            "referral_milestone_unlim3": False,
            "spread_card_count": 3,
            "reversed_cards": False,
        }
        self.save_data()

    def _ensure(self, user_id: int) -> dict[str, Any]:
        if not self.has_user(user_id):
            self.add_user(user_id)
        return self.data[str(user_id)]

    def _pull_wallet(self, user_id: int) -> dict:
        seed = self.data.get(str(user_id))
        wallet = shared_wallet.view("max", int(user_id), seed)
        shared_wallet.mirror(seed, wallet)
        return wallet

    def _commit_wallet(self, user_id: int, changes: dict) -> dict:
        seed = self.data.get(str(user_id))
        wallet = shared_wallet.update("max", int(user_id), seed, changes)
        shared_wallet.mirror(seed, wallet)
        self.save_data()
        return wallet

    def get_user_questions(self, user_id: int) -> int:
        if str(user_id) not in self.data:
            return 0
        return int(self._pull_wallet(user_id).get("questions") or 0)

    def decrement_user_questions(self, user_id: int) -> None:
        key = str(user_id)
        if key not in self.data:
            return
        updated = shared_wallet.add_questions("max", int(user_id), -1, self.data.get(key))
        if not updated:
            return
        shared_wallet.mirror(self.data.get(key), updated)
        self.save_data()

    def increment_user_questions(self, user_id: int, amount: int) -> None:
        key = str(user_id)
        self._ensure(user_id)
        updated = shared_wallet.add_questions("max", int(user_id), int(amount), self.data.get(key))
        if not updated:
            return
        shared_wallet.mirror(self.data.get(key), updated)
        self.save_data()

    def set_user_questions(self, user_id: int, amount: int) -> None:
        self._ensure(user_id)
        self._commit_wallet(user_id, {"questions": int(amount)})

    def set_subscription_end(self, user_id: int, end_time_str: str) -> None:
        self._ensure(user_id)
        self._commit_wallet(user_id, {"subscription_end": end_time_str})

    def get_subscription_end(self, user_id: int) -> Optional[datetime]:
        if str(user_id) not in self.data:
            return None
        raw = self._pull_wallet(user_id).get("subscription_end")
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def has_active_subscription(self, user_id: int) -> bool:
        end = self.get_subscription_end(user_id)
        return bool(end and end > datetime.now())

    def extend_subscription(self, user_id: int, days: int) -> None:
        new_end = datetime.now() + timedelta(days=days)
        self.set_subscription_end(user_id, new_end.strftime("%Y-%m-%d %H:%M:%S"))

    def set_user_email(self, user_id: int, email: str) -> None:
        if not self.is_valid_email(email):
            raise ValueError("Некорректный email адрес.")
        self._ensure(user_id)
        self._commit_wallet(user_id, {"email": email.strip()})

    def get_user_email(self, user_id: int) -> Optional[str]:
        if str(user_id) not in self.data:
            return None
        return self._pull_wallet(user_id).get("email")

    @staticmethod
    def is_valid_email(email: str) -> bool:
        import re

        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email or ""))

    def get_last_refill_at(self, user_id: int) -> Optional[datetime]:
        if str(user_id) not in self.data:
            return None
        val = self._pull_wallet(user_id).get("last_refill_at")
        if not val:
            return None
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def set_last_refill_at(self, user_id: int, dt: datetime) -> None:
        self._ensure(user_id)
        self._commit_wallet(user_id, {"last_refill_at": dt.strftime("%Y-%m-%d %H:%M:%S")})

    def get_filtered_user_ids(self, excluded_ids: list[int]) -> list[int]:
        excluded = {str(x) for x in excluded_ids}
        return [int(uid) for uid in self.data.keys() if uid not in excluded and str(uid).isdigit()]

    def enable_auto_renew(
        self,
        user_id: int,
        *,
        payment_method_id: str,
        plan_key: str,
        price_kopecks: int,
    ) -> None:
        self._ensure(user_id)
        self._commit_wallet(
            user_id,
            {
                "yookassa_payment_method_id": payment_method_id,
                "subscription_plan_key": plan_key,
                "subscription_price": int(price_kopecks),
                "auto_renew": True,
                "renew_fail_count": 0,
                "next_renew_at": None,
            },
        )

    def disable_auto_renew(self, user_id: int) -> bool:
        self._ensure(user_id)
        was = bool(self._pull_wallet(user_id).get("auto_renew"))
        self._commit_wallet(
            user_id,
            {"auto_renew": False, "next_renew_at": None, "renew_fail_count": 0},
        )
        return was

    def is_auto_renew_enabled(self, user_id: int) -> bool:
        if str(user_id) not in self.data:
            return False
        return bool(self._pull_wallet(user_id).get("auto_renew"))

    def get_payment_method_id(self, user_id: int) -> Optional[str]:
        if str(user_id) not in self.data:
            return None
        val = self._pull_wallet(user_id).get("yookassa_payment_method_id")
        return str(val) if val else None

    def get_subscription_plan_key(self, user_id: int) -> Optional[str]:
        if str(user_id) not in self.data:
            return None
        return self._pull_wallet(user_id).get("subscription_plan_key")

    def get_subscription_price(self, user_id: int) -> Optional[int]:
        if str(user_id) not in self.data:
            return None
        val = self._pull_wallet(user_id).get("subscription_price")
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def set_renew_failure(self, user_id: int, *, fail_count: int, next_renew_at: Optional[datetime]) -> None:
        self._ensure(user_id)
        changes = {
            "renew_fail_count": int(fail_count),
            "next_renew_at": (
                next_renew_at.strftime("%Y-%m-%d %H:%M:%S") if next_renew_at else None
            ),
        }
        if fail_count >= 3:
            changes["auto_renew"] = False
        self._commit_wallet(user_id, changes)

    def clear_renew_failure(self, user_id: int) -> None:
        self._ensure(user_id)
        self._commit_wallet(user_id, {"renew_fail_count": 0, "next_renew_at": None})

    def iter_users_due_renewal(self, now: Optional[datetime] = None) -> list[int]:
        now = now or datetime.now()
        shared_wallet.pull_into("max", self.data)
        due: list[int] = []
        for key, u in self.data.items():
            if not str(key).isdigit():
                continue
            if not u.get("auto_renew") or not u.get("yookassa_payment_method_id"):
                continue
            if not u.get("subscription_price") or not u.get("subscription_plan_key"):
                continue
            next_raw = u.get("next_renew_at")
            if next_raw:
                try:
                    if datetime.strptime(next_raw, "%Y-%m-%d %H:%M:%S") <= now:
                        due.append(int(key))
                    continue
                except ValueError:
                    pass
            end_raw = u.get("subscription_end")
            if not end_raw:
                continue
            try:
                end = datetime.strptime(end_raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if end <= now + timedelta(days=1):
                due.append(int(key))
        return due

    def should_decrement(self, user_id: int) -> bool:
        return not self.has_active_subscription(user_id)

    def can_read(self, user_id: int) -> bool:
        if self.has_active_subscription(user_id):
            return True
        return self.get_user_questions(user_id) > 0

    def get_spread_card_count(self, user_id: int) -> int:
        raw = self.data.get(str(user_id), {}).get("spread_card_count", 3)
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = 3
        return n if n in (1, 3, 5) else 3

    def set_spread_card_count(self, user_id: int, count: int) -> None:
        if count not in (1, 3, 5):
            count = 3
        self._ensure(user_id)["spread_card_count"] = count
        self.save_data()

    def get_reversed_cards_enabled(self, user_id: int) -> bool:
        return bool(self.data.get(str(user_id), {}).get("reversed_cards", False))

    def get_referred_by(self, user_id: int) -> Optional[int]:
        val = self.data.get(str(user_id), {}).get("referred_by")
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def set_referred_by_once(
        self, user_id: int, referrer_id: int, *, source: str = "ref"
    ) -> bool:
        u = self._ensure(user_id)
        if u.get("referred_by") is not None:
            return False
        u["referred_by"] = int(referrer_id)
        u["referral_source"] = (source or "ref")[:16]
        u["referred_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_data()
        return True

    def get_referral_source(self, user_id: int) -> str:
        return str(self.data.get(str(user_id), {}).get("referral_source") or "ref")

    def increment_referrals_count(self, user_id: int, amount: int = 1) -> None:
        u = self._ensure(user_id)
        u["referrals_count"] = int(u.get("referrals_count", 0)) + amount
        self.save_data()

    def get_referrals_count(self, user_id: int) -> int:
        return int(self.data.get(str(user_id), {}).get("referrals_count", 0))

    def get_active_referrals_count(self, user_id: int) -> int:
        return int(self.data.get(str(user_id), {}).get("active_referrals_count", 0))

    def increment_active_referrals(self, user_id: int, amount: int = 1) -> int:
        u = self._ensure(user_id)
        u["active_referrals_count"] = int(u.get("active_referrals_count", 0)) + amount
        self.save_data()
        return int(u["active_referrals_count"])

    def mark_first_reading_done(self, user_id: int) -> bool:
        u = self._ensure(user_id)
        if u.get("first_reading_done"):
            return False
        u["first_reading_done"] = True
        self.save_data()
        return True

    def claim_referral_milestone(self, user_id: int, milestone: Any) -> bool:
        key = f"referral_milestone_{milestone}"
        u = self._ensure(user_id)
        if u.get(key):
            return False
        u[key] = True
        self.save_data()
        return True

    def claim_share_active_bonus(self, user_id: int) -> bool:
        u = self._ensure(user_id)
        if u.get("share_active_bonus_done"):
            return False
        u["share_active_bonus_done"] = True
        self.save_data()
        return True

    def get_aggregate_stats(self) -> dict[str, Any]:
        shared_wallet.pull_into("max", self.data)
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        top_referrers: list[tuple[int, int]] = []
        stats: dict[str, Any] = {
            "total": 0,
            "active_subs": 0,
            "referred_users": 0,
            "total_invites": 0,
            "referrers": 0,
            "zero_questions": 0,
            "top_referrers": top_referrers,
            "referral_sources": {},
            "shared_total": 0,
            "shared_today": 0,
            "share_joined_total": 0,
            "share_joined_today": 0,
        }
        for uid, u in self.data.items():
            stats["total"] += 1
            if u.get("referred_by") is not None:
                stats["referred_users"] += 1
                src = str(u.get("referral_source") or "ref")
                stats["referral_sources"][src] = (
                    stats["referral_sources"].get(src, 0) + 1
                )
                if src == "share":
                    stats["share_joined_total"] += 1
                    if str(u.get("referred_at") or "").startswith(today):
                        stats["share_joined_today"] += 1
            pack = u.get("last_share_pack")
            if isinstance(pack, dict) and pack:
                stats["shared_total"] += 1
                if str(pack.get("at") or "").startswith(today):
                    stats["shared_today"] += 1
            rc = int(u.get("referrals_count", 0))
            stats["total_invites"] += rc
            if rc > 0:
                stats["referrers"] += 1
                try:
                    top_referrers.append((int(uid), rc))
                except ValueError:
                    pass
            end = u.get("subscription_end")
            if end:
                try:
                    if datetime.strptime(end, "%Y-%m-%d %H:%M:%S") > now:
                        stats["active_subs"] += 1
                except ValueError:
                    pass
            if int(u.get("questions", 0)) <= 0:
                stats["zero_questions"] += 1
        top_referrers.sort(key=lambda x: x[1], reverse=True)
        stats["top_referrers"] = top_referrers[:5]
        return stats


user_data = UserData()


class AgreementManager:
    def __init__(self, file_path: Path | str | None = None) -> None:
        self.file_path = Path(file_path or config.AGREEMENTS_FILE)

    def _load(self) -> dict:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}

    def _save(self, agreements: dict) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(agreements, f, ensure_ascii=False, indent=2)

    def _stage(self, user_id: int):
        v = self._load().get(str(user_id))
        if v is True:
            return True
        if isinstance(v, dict):
            if v.get("agreed") is True or v.get("stage") in {"done", True}:
                return True
            st = v.get("stage")
            if st in ("pd", "tb"):
                return st
            if v.get("at"):
                return True
        if v in ("pd", "tb"):
            return v
        return None

    def user_has_agreed(self, user_id: int) -> bool:
        v = self._load().get(str(user_id))
        if v is True:
            return True
        return isinstance(v, dict) and (
            v.get("agreed") is True or v.get("stage") in {"done", True}
        )

    def has_pd_consent(self, user_id: int) -> bool:
        if self.user_has_agreed(user_id):
            return True
        v = self._load().get(str(user_id))
        if v in ("pd", "tb"):
            return True
        return isinstance(v, dict) and v.get("stage") in ("pd", "tb", "done")

    def add_pd_consent(self, user_id: int) -> None:
        if self.has_pd_consent(user_id):
            return
        agreements = self._load()
        agreements[str(user_id)] = {
            "stage": "pd",
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save(agreements)

    def add_tb_consent(self, user_id: int) -> None:
        if self.user_has_agreed(user_id):
            return
        agreements = self._load()
        agreements[str(user_id)] = {
            "stage": "tb",
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save(agreements)

    def add_user_agreement(self, user_id: int) -> None:
        agreements = self._load()
        agreements[str(user_id)] = {
            "agreed": True,
            "stage": "done",
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save(agreements)


agreement_manager = AgreementManager()


class ReadingHistory:
    def __init__(self, file_path: Path | str | None = None) -> None:
        self.file_path = Path(file_path or config.READING_HISTORY_FILE)
        self.data: dict[str, list] = self._load()

    def _load(self) -> dict[str, list]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, dict) else {}
        except FileNotFoundError:
            return {}

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add(
        self,
        user_id: int,
        *,
        kind: str,
        question: str,
        cards: list[str],
        summary: str,
    ) -> None:
        key = str(user_id)
        self.data.setdefault(key, [])
        self.data[key].append(
            {
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "kind": kind[:32],
                "question": (question or "")[:800],
                "cards": cards[:5],
                "summary": (summary or "")[:500],
            }
        )
        if len(self.data[key]) > 200:
            self.data[key] = self.data[key][-200:]
        self._save()

    def get_admin_stats(self, days: int = 7) -> dict[str, Any]:
        cutoff = datetime.now() - timedelta(days=days)
        today = datetime.now().strftime("%Y-%m-%d")
        by_kind_today: dict[str, int] = {}
        by_kind_period: dict[str, int] = {}
        today_total = 0
        period_total = 0
        period_users: set[str] = set()
        all_total = 0
        for uid, items in self.data.items():
            if not isinstance(items, list):
                continue
            for e in items:
                if not isinstance(e, dict):
                    continue
                all_total += 1
                kind = str(e.get("kind") or "ask")
                at = str(e.get("at") or "")
                if at.startswith(today):
                    today_total += 1
                    by_kind_today[kind] = by_kind_today.get(kind, 0) + 1
                try:
                    dt = datetime.strptime(at, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if dt >= cutoff:
                    period_total += 1
                    period_users.add(uid)
                    by_kind_period[kind] = by_kind_period.get(kind, 0) + 1
        return {
            "today_total": today_total,
            "by_kind_today": by_kind_today,
            "period_total": period_total,
            "period_users": len(period_users),
            "by_kind_period": by_kind_period,
            "all_total": all_total,
        }


reading_history = ReadingHistory()


class Logger:
    def __init__(self, file_path: Path | str | None = None) -> None:
        self.file_path = Path(file_path or config.LOGS_FILE)
        self.logs: list[dict] = self._load()

    def _load(self) -> list[dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, list) else []
        except FileNotFoundError:
            return []

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.logs[-8000:], f, ensure_ascii=False)

    def log_command(self, user_id: int, command: str) -> None:
        self.logs.append(
            {
                "user_id": user_id,
                "command": command,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self._save()

    def get_total_users(self) -> int:
        return len({log["user_id"] for log in self.logs})

    def get_new_users_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        existing = {log["user_id"] for log in self.logs if not str(log["date"]).startswith(today)}
        today_users = {
            log["user_id"] for log in self.logs if str(log["date"]).startswith(today)
        }
        return len(today_users - existing)

    def count_active_users(self, days: int = 7) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return len(
            {
                log["user_id"]
                for log in self.logs
                if str(log.get("date", "")) >= cutoff
            }
        )


activity_logger = Logger()


class OneDayCard:
    def __init__(self, filename: Path | str | None = None) -> None:
        self.filename = Path(filename or config.DAY_CARD_FILE)
        self.data = self.load_data()

    def load_data(self) -> dict:
        try:
            with open(self.filename, "r", encoding="utf-8") as file:
                raw = json.load(file)
            return {str(k): v for k, v in raw.items()} if isinstance(raw, dict) else {}
        except FileNotFoundError:
            return {}

    def save_data(self) -> None:
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def add_chat(self, chat_id: int) -> None:
        key = str(chat_id)
        if key not in self.data:
            self.data[key] = {"map": None, "date": None}
            self.save_data()

    def update_date_if_needed(self, chat_id: int) -> bool:
        today = datetime.now().date()
        key = str(chat_id)
        self.add_chat(chat_id)
        current = self.data[key].get("date")
        if current is None or current != str(today):
            self.data[key]["date"] = str(today)
            self.save_data()
            return True
        return False

    def select_random_card(self, chat_id: int) -> int:
        import random

        self.add_chat(chat_id)
        selected = random.randrange(1, 79)
        self.data[str(chat_id)]["map"] = selected
        self.save_data()
        return selected


one_card = OneDayCard()


class StatusData:
    def __init__(self, filename: Path | str | None = None) -> None:
        self.filename = Path(filename or config.STATUS_FILE)
        self.data = self.load_data()

    def load_data(self) -> dict:
        try:
            with open(self.filename, "r", encoding="utf-8") as file:
                raw = json.load(file)
            return raw if isinstance(raw, dict) else {}
        except FileNotFoundError:
            return {}

    def save_data(self) -> None:
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(self.data, file)

    def set_status(self, chat_id: int, status: int) -> None:
        self.data[str(chat_id)] = status
        self.save_data()

    def toggle_status(self, chat_id: int) -> None:
        current = self.data.get(str(chat_id))
        if current is None:
            self.set_status(chat_id, 0)
        else:
            self.set_status(chat_id, 1 if current == 0 else 0)

    def is_status_zero(self, chat_id: int) -> bool:
        if str(chat_id) not in self.data:
            self.set_status(chat_id, 0)
            return True
        return self.data[str(chat_id)] == 0

    def is_subscribed_claim(self, chat_id: int) -> bool:
        return self.data.get(str(chat_id)) == 1


status_data = StatusData()


class PromocodeStore:
    def __init__(self, filename: Path | str | None = None) -> None:
        self.filename = Path(filename or config.PROMO_FILE)
        self.data: dict[str, list] = self._load()

    def _load(self) -> dict[str, list]:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {str(k): list(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        except FileNotFoundError:
            return {}

    def _save(self) -> None:
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_used(self, chat_id: int, code: str) -> bool:
        return code in self.data.get(str(chat_id), [])

    def mark_used(self, chat_id: int, code: str) -> None:
        key = str(chat_id)
        self.data.setdefault(key, [])
        if code not in self.data[key]:
            self.data[key].append(code)
            self._save()


promocode_store = PromocodeStore()


class OrderNumber:
    def __init__(self, filename: Path | str | None = None) -> None:
        self.filename = Path(filename or config.ORDER_FILE)
        self.order_number = 0
        self.load_order_number()

    def load_order_number(self) -> None:
        try:
            with open(self.filename, "r", encoding="utf-8") as file:
                data = json.load(file)
                self.order_number = int(data.get("order_number", 0))
        except FileNotFoundError:
            self.order_number = 0

    def save_order_number(self) -> None:
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump({"order_number": self.order_number}, file)

    def increment_order_number(self) -> None:
        self.order_number += 1
        self.save_order_number()

    def get_order_number(self) -> int:
        return self.order_number


order_manager = OrderNumber()
