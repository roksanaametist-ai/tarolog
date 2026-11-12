"""Тестовая обвязка для «Совместимости»: бот без сети и без боевого токена.

* BOT_DATA_DIR — временная папка (данные прода не трогаются);
* Telegram заменён FakeSession: все запросы бота пишутся в ``session.calls``;
* нейросеть заменена ``fake_structured`` (детерминированный ответ).

Импортировать этот модуль нужно ДО ``import main``.
"""

from __future__ import annotations

import itertools
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

_DATA_DIR = tempfile.mkdtemp(prefix="compat-tests-")
os.environ["BOT_DATA_DIR"] = _DATA_DIR
os.environ["TELEGRAM_TOKEN"] = "123456:TEST-not-a-real-token"
os.environ["BOT_JSON_MIRROR"] = "0"
os.environ["GROQ_API_KEY"] = "test-dummy"  # фиктивный: нейросеть подменена
os.environ.setdefault("OPENAI_API_KEY", "test-dummy")
os.environ.setdefault("BOT_ADMIN_IDS", "")
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import GetMe, TelegramMethod  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, Update, User  # noqa: E402

BOT_USER = User(id=999000, is_bot=True, first_name="Таро бот", username="Roxanaametist_Taro_bot")

_upd = itertools.count(1)
_mid = itertools.count(1000)


def _markup_dump(markup: Any) -> List[List[Dict[str, str]]]:
    if markup is None:
        return []
    rows = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None) or []
    out = []
    for row in rows:
        out.append(
            [
                {
                    k: v
                    for k, v in {
                        "text": getattr(b, "text", ""),
                        "data": getattr(b, "callback_data", None),
                        "url": getattr(b, "url", None),
                    }.items()
                    if v
                }
                for b in row
            ]
        )
    return out


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: List[Dict[str, Any]] = []

    async def close(self) -> None:  # pragma: no cover
        return None

    async def stream_content(self, *a, **kw):  # pragma: no cover
        if False:
            yield b""

    async def make_request(self, bot, method: TelegramMethod, timeout: Optional[int] = None):
        name = type(method).__name__
        chat_id = getattr(method, "chat_id", None)
        rec = {
            "method": name,
            "chat_id": chat_id,
            "text": getattr(method, "text", None) or getattr(method, "caption", None),
            "buttons": _markup_dump(getattr(method, "reply_markup", None)),
        }
        photo = getattr(method, "photo", None)
        if photo is not None:
            rec["photo"] = str(getattr(photo, "path", photo))
        self.calls.append(rec)
        if isinstance(method, GetMe):
            return BOT_USER
        returning = getattr(method, "__returning__", None)
        if returning is Message or name.startswith("Send"):
            return Message(
                message_id=next(_mid),
                date=datetime.now(),
                chat=Chat(id=int(chat_id or 0), type="private"),
                from_user=BOT_USER,
                text=rec["text"],
            )
        return True

    # helpers
    def for_chat(self, chat_id: int) -> List[Dict[str, Any]]:
        return [c for c in self.calls if c["chat_id"] == chat_id]

    def texts(self, chat_id: int) -> List[str]:
        return [c["text"] or "" for c in self.for_chat(chat_id)]

    def find_button(self, chat_id: int, prefix: str) -> Optional[Dict[str, str]]:
        for c in reversed(self.for_chat(chat_id)):
            for row in c["buttons"]:
                for b in row:
                    if str(b.get("data") or "").startswith(prefix) or str(b.get("text") or "").startswith(prefix):
                        return b
        return None


def user(uid: int, first_name: str = "Аня") -> User:
    return User(id=uid, is_bot=False, first_name=first_name)


def msg_update(uid: int, text: str, *, first_name: str = "Аня") -> Update:
    return Update(
        update_id=next(_upd),
        message=Message(
            message_id=next(_mid),
            date=datetime.now(),
            chat=Chat(id=uid, type="private"),
            from_user=user(uid, first_name),
            text=text,
        ),
    )


def cb_update(uid: int, data: str, *, first_name: str = "Аня") -> Update:
    return Update(
        update_id=next(_upd),
        callback_query=CallbackQuery(
            id=str(next(_upd)),
            from_user=user(uid, first_name),
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=next(_mid),
                date=datetime.now(),
                chat=Chat(id=uid, type="private"),
                from_user=BOT_USER,
                text="…",
            ),
        ),
    )


async def fake_structured(question: str, card_labels: List[str], card_roles_in_order=None, **kw) -> dict:
    roles = list(card_roles_in_order or [])
    return {
        "card_interpretations": [
            f"{(roles[i] if i < len(roles) else 'Карта')}: «{label}» — тёплый знак для этой связи."
            for i, label in enumerate(card_labels)
        ],
        "summary": "Вас связывает доверие и интерес друг к другу. Говорите открыто — так связь крепнет.",
    }


async def _no_sleep(*a, **kw) -> None:
    return None


def setup_main():
    """Импорт main + подмена сети/нейросети/пауз. Возвращает (main, session)."""
    import main  # noqa: WPS433

    session = FakeSession()
    main.bot.session = session
    main.get_tarot_reading_structured = fake_structured
    main.pause_reading = _no_sleep
    main.typing_delay_for_text = lambda text: 0
    main._bot_username_cache = BOT_USER.username
    if not main.tarot_cards:  # в проде колода заполняется в main() при запуске
        for i, name in enumerate(_ARCANA, start=1):
            main.tarot_cards[f"static/card{i}.jpg"] = name
        for i in range(len(_ARCANA) + 1, 79):
            main.tarot_cards[f"static/card{i}.jpg"] = f"Карта {i}"
    return main, session


_ARCANA = [
    "Дурак", "Маг", "Верховная Жрица", "Императрица", "Император", "Иерофант",
    "Влюбленные", "Колесница", "Сила", "Отшельник", "Колесо Фортуны",
    "Правосудие", "Повешенный", "Смерть", "Умеренность", "Дьявол",
    "Башня", "Звезда", "Луна", "Солнце", "Суд", "Мир",
]
