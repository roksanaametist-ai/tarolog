"""Своя колода: интерактивная карта в сообщении (inline) + свой расклад в боте."""

from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, SwitchInlineQueryChosenChat
from aiogram.utils.keyboard import InlineKeyboardBuilder

DEBOUNCE_SEC = 1.5
CARD_BACK_PATH = "static/card_back.jpg"
# Публичный URL для inline-отправки (CachedPhoto у части клиентов зависает на Send).
CARD_BACK_URL = "https://followthefrensy.ru/cards/static/card_back.jpg"
CARD_BACK_WIDTH = 1024
CARD_BACK_HEIGHT = 1748


class PublicCardStore:
    def __init__(self, posts_path: str, entries_path: str):
        self.posts_path = Path(posts_path)
        self.entries_path = Path(entries_path)
        self._lock = threading.Lock()
        self.posts: Dict[str, Dict[str, Any]] = {}
        self.entries: List[Dict[str, Any]] = []
        self.pending: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self.posts_path.exists():
            try:
                raw = json.loads(self.posts_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.posts = raw.get("posts") or {}
                    self.pending = raw.get("pending") or {}
                    old = raw.get("pending_own") or {}
                    for uid, pid in old.items():
                        self.pending.setdefault(
                            str(uid), {"action": "own", "id": str(pid)}
                        )
            except Exception:
                self.posts = {}
                self.pending = {}
        if self.entries_path.exists():
            try:
                raw = json.loads(self.entries_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    self.entries = raw
                elif isinstance(raw, dict):
                    self.entries = list(raw.get("entries") or [])
            except Exception:
                self.entries = []

    def _save_posts(self) -> None:
        self.posts_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"posts": self.posts, "pending": self.pending}
        self.posts_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_entries(self) -> None:
        self.entries_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries_path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def create_post(self, owner_user_id: int) -> Dict[str, Any]:
        with self._lock:
            public_card_id = secrets.token_hex(4)
            while public_card_id in self.posts:
                public_card_id = secrets.token_hex(4)
            post = {
                "public_card_id": public_card_id,
                "owner_user_id": int(owner_user_id),
                "is_opened": False,
                "card_path": None,
                "card_label": None,
                "last_card_path": None,
                "open_count": 0,
                "shuffle_count": 0,
                "chat_id": None,
                "message_id": None,
                "inline_message_id": None,
                "closed_file_id": None,
                "created_at": self._now(),
                "last_action_at": 0.0,
            }
            self.posts[public_card_id] = post
            self._save_posts()
            return dict(post)

    def get(self, public_card_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            post = self.posts.get(public_card_id)
            return dict(post) if post else None

    def bind_message(
        self,
        public_card_id: str,
        *,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
        closed_file_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            post = self.posts.get(public_card_id)
            if not post:
                return None
            if chat_id is not None:
                post["chat_id"] = int(chat_id)
            if message_id is not None:
                post["message_id"] = int(message_id)
            if inline_message_id:
                post["inline_message_id"] = str(inline_message_id)
            if closed_file_id:
                post["closed_file_id"] = str(closed_file_id)
            self._save_posts()
            return dict(post)

    def log_entry(
        self,
        *,
        user_id: int,
        public_card_id: str,
        entry_type: str,
        is_new_user: bool = False,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            post = self.posts.get(public_card_id) or {}
            ctx = (context or "").strip().lower() or None
            if ctx not in {"dm", "chat", None}:
                ctx = None
            if ctx is None and entry_type in {"open", "reopen", "shuffle"}:
                # Legacy/fallback: есть inline → открытие в чужом чате.
                ctx = "chat" if post.get("inline_message_id") else "dm"
            event = {
                "user_id": int(user_id),
                "public_card_id": public_card_id,
                "entry_type": entry_type,
                "context": ctx,
                "card_path": post.get("card_path"),
                "card_label": post.get("card_label"),
                "is_opened": bool(post.get("is_opened")),
                "owner_user_id": post.get("owner_user_id"),
                "is_new_user": bool(is_new_user),
                "created_at": self._now(),
            }
            self.entries.append(event)
            # Не раздуваем файл бесконечно.
            if len(self.entries) > 20000:
                self.entries = self.entries[-15000:]
            self._save_entries()
            return event

    def prune_orphan_posts(self, *, max_age_hours: float = 48.0) -> int:
        """Черновики без отправки/открытий старше max_age — удаляем."""
        cutoff_ts = time.time() - max(1.0, float(max_age_hours)) * 3600.0
        with self._lock:
            pending_ids = {
                str(v.get("id") or "")
                for v in self.pending.values()
                if isinstance(v, dict)
            }
            removed = 0
            for pid, post in list(self.posts.items()):
                if pid in pending_ids:
                    continue
                if post.get("inline_message_id"):
                    continue
                if int(post.get("open_count") or 0) > 0:
                    continue
                if int(post.get("shuffle_count") or 0) > 0:
                    continue
                created = str(post.get("created_at") or "")
                try:
                    created_ts = datetime.fromisoformat(created).timestamp()
                except Exception:
                    created_ts = 0.0
                if created_ts and created_ts > cutoff_ts:
                    continue
                del self.posts[pid]
                removed += 1
            if removed:
                self._save_posts()
            return removed

    def get_admin_stats(self, *, days: int = 7) -> Dict[str, Any]:
        """Воронка колоды из entries (не из сырых posts-клонов)."""
        today = datetime.now().strftime("%Y-%m-%d")
        cutoff = (datetime.now() - timedelta(days=max(1, int(days)))).strftime(
            "%Y-%m-%d"
        )

        def _day(ts: Any) -> str:
            return str(ts or "")[:10]

        with self._lock:
            posts_map = dict(self.posts)
            entries = list(self.entries)

        def _count_entries(
            entry_type: str, *, context: Optional[str] = None
        ) -> Dict[str, int]:
            today_n = 0
            period_n = 0
            total_n = 0
            users_period: set = set()
            for e in entries:
                if str(e.get("entry_type") or "") != entry_type:
                    continue
                ctx = str(e.get("context") or "").strip().lower()
                if not ctx:
                    post = posts_map.get(str(e.get("public_card_id") or "")) or {}
                    ctx = "chat" if post.get("inline_message_id") else "dm"
                if context is not None and ctx != context:
                    continue
                total_n += 1
                day = _day(e.get("created_at"))
                if day == today:
                    today_n += 1
                if day >= cutoff:
                    period_n += 1
                    uid = e.get("user_id")
                    if uid is not None:
                        users_period.add(uid)
            return {
                "today": today_n,
                "period": period_n,
                "total": total_n,
                "users_period": len(users_period),
            }

        preview = _count_entries("create")
        sent = _count_entries("sent")
        opened = _count_entries("open")
        opened_dm = _count_entries("open", context="dm")
        opened_chat = _count_entries("open", context="chat")
        return {
            "days": int(days),
            # Воронка (entries) — источник правды для админки
            "preview": preview,
            "created_entry": preview,
            "sent": sent,
            "opened": opened,
            "opened_dm": opened_dm,
            "opened_chat": opened_chat,
            "reopened": _count_entries("reopen"),
            "shuffled": _count_entries("shuffle"),
            "own_spread": _count_entries("own_spread"),
            # Служебно: сколько сырых post-записей ещё лежит в store
            "posts_total": len(posts_map),
            "posts_sent": sum(
                1 for p in posts_map.values() if p.get("inline_message_id")
            ),
        }

    def set_pending(self, user_id: int, *, action: str, public_card_id: str) -> None:
        with self._lock:
            self.pending[str(user_id)] = {"action": action, "id": public_card_id}
            self._save_posts()

    def pop_pending(self, user_id: int) -> Optional[Dict[str, str]]:
        with self._lock:
            item = self.pending.pop(str(user_id), None)
            if item is not None:
                self._save_posts()
            return item

    def _check_debounce(self, post: Dict[str, Any]) -> bool:
        last = float(post.get("last_action_at") or 0)
        return (time.time() - last) < DEBOUNCE_SEC

    def open_card(
        self,
        public_card_id: str,
        *,
        opened_by: int,
        draw_fn: Callable[[Optional[set]], Dict[str, Any]],
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        with self._lock:
            post = self.posts.get(public_card_id)
            if not post:
                return "missing", None
            if self._check_debounce(post):
                return "debounce", dict(post)
            if post.get("is_opened"):
                return "already_open", dict(post)
            exclude = set()
            if post.get("last_card_path"):
                exclude.add(post["last_card_path"])
            card = draw_fn(exclude or None)
            post["is_opened"] = True
            post["card_path"] = card["path"]
            post["card_label"] = card["label"]
            post["last_card_path"] = card["path"]
            post["open_count"] = int(post.get("open_count") or 0) + 1
            post["last_opened_by"] = int(opened_by)
            post["last_action_at"] = time.time()
            self._save_posts()
            return "opened", dict(post)

    def reopen_card(
        self,
        public_card_id: str,
        *,
        opened_by: int,
        draw_fn: Callable[[Optional[set]], Dict[str, Any]],
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        with self._lock:
            post = self.posts.get(public_card_id)
            if not post:
                return "missing", None
            if self._check_debounce(post):
                return "debounce", dict(post)
            if not post.get("is_opened"):
                return "closed", dict(post)
            exclude = set()
            if post.get("card_path"):
                exclude.add(post["card_path"])
            card = draw_fn(exclude or None)
            post["card_path"] = card["path"]
            post["card_label"] = card["label"]
            post["last_card_path"] = card["path"]
            post["open_count"] = int(post.get("open_count") or 0) + 1
            post["last_opened_by"] = int(opened_by)
            post["last_action_at"] = time.time()
            self._save_posts()
            return "reopened", dict(post)

    def shuffle_card(
        self,
        public_card_id: str,
        *,
        shuffled_by: int,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        with self._lock:
            post = self.posts.get(public_card_id)
            if not post:
                return "missing", None
            if self._check_debounce(post):
                return "debounce", dict(post)
            if not post.get("is_opened"):
                return "already_closed", dict(post)
            if post.get("card_path"):
                post["last_card_path"] = post["card_path"]
            post["is_opened"] = False
            post["card_path"] = None
            post["card_label"] = None
            post["shuffle_count"] = int(post.get("shuffle_count") or 0) + 1
            post["last_shuffled_by"] = int(shuffled_by)
            post["last_action_at"] = time.time()
            self._save_posts()
            return "shuffled", dict(post)

    def revert_failed_open(self, public_card_id: str) -> Optional[Dict[str, Any]]:
        """Откат после open/reopen, если editMessageMedia не прошёл — иначе UI залипает."""
        with self._lock:
            post = self.posts.get(public_card_id)
            if not post or not post.get("is_opened"):
                return dict(post) if post else None
            # reopen: вернуть предыдущую карту нельзя надёжно — закрываем колоду.
            if post.get("card_path"):
                post["last_card_path"] = post["card_path"]
            post["is_opened"] = False
            post["card_path"] = None
            post["card_label"] = None
            post["open_count"] = max(0, int(post.get("open_count") or 0) - 1)
            post["last_action_at"] = 0.0
            self._save_posts()
            return dict(post)


def own_spread_url(bot_username: str, public_card_id: str) -> str:
    uname = bot_username.lstrip("@")
    return f"https://t.me/{uname}?start=pubown_{public_card_id}"


def closed_keyboard(public_card_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="Открыть карту",
            callback_data=f"pubcard:open:{public_card_id}",
        )
    )
    return kb.as_markup()


def opened_keyboard(public_card_id: str, bot_username: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="Открыть свой расклад",
            url=own_spread_url(bot_username, public_card_id),
        )
    )
    kb.row(
        InlineKeyboardButton(
            text="Открыть другую",
            callback_data=f"pubcard:reopen:{public_card_id}",
        ),
        InlineKeyboardButton(
            text="Перетасовать колоду",
            callback_data=f"pubcard:shuffle:{public_card_id}",
        ),
    )
    return kb.as_markup()


def share_hint_keyboard(public_card_id: str) -> InlineKeyboardMarkup:
    """Выбор чата → сообщение уходит с живыми кнопками."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="📤 Отправить другу или в чат",
            switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                query=f"deck_{public_card_id}",
                allow_user_chats=True,
                allow_group_chats=True,
                allow_channel_chats=True,
                allow_bot_chats=False,
            ),
        )
    )
    return kb.as_markup()
