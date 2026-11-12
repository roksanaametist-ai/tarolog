"""Расклад «Совместимость»: приглашения второго человека.

Хранилище — документ ``compat_invites`` в OperationalStore (bot_state.sqlite3):

    {
      "invites": {
        "<id>": {
          "id", "inviter_id", "inviter_name", "partner_name", "topic",
          "cards": [{"path", "label", "reversed"}, ...],   # 3 карты короткого
          "created_at": <unix>, "status": "open|claimed|completed",
          "invitee_id", "invitee_name", "claimed_at", "completed_at",
          "full": {"cards": [...5], "roles": [...], "texts": [...], "summary": "..."}
        }
      },
      "pending": {"<chat_id>": {"id": "<invite_id>", "at": <unix>}}
    }

Все изменения — через ``update_document`` (одна транзакция на шаг), поэтому
двойной клик и второй экземпляр не создадут два полных расклада.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

DOC_NAME = "compat_invites"
PAYLOAD_PREFIX = "compat_"
INVITE_ID_BYTES = 9  # token_urlsafe(9) → 12 символов; payload = 19 символов (< 64)
INVITE_TTL_SECONDS = 30 * 24 * 3600
CLAIM_STALE_SECONDS = 10 * 60  # «зависший» claimed (упал бот) снова можно открыть
PENDING_TTL_SECONDS = 2 * 24 * 3600
NAME_MAX_LEN = 30
STORY_PHRASE_MAX = 220
STORY_PHRASE_MIN = 150

TOPICS: Dict[str, Dict[str, str]] = {
    "love": {
        "button": "❤️ Любовь",
        "label": "Любовь",
        "about": "романтические чувства и отношения пары",
    },
    "friend": {
        "button": "🤝 Дружба",
        "label": "Дружба",
        "about": "дружба, доверие и общение",
    },
    "work": {
        "button": "💼 Работа",
        "label": "Работа",
        "about": "рабочее партнёрство, совместные дела и роли в команде",
    },
}

SHORT_FIXED_ROLES = ["Ваша связь"]
FULL_EXTRA_ROLES = ["Что вас связывает", "Что мешает", "Куда идёт"]

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
_LINK_RE = re.compile(r"(https?|www|t\.me|telegram|\.ru|\.com)", re.IGNORECASE)


# ---------------------------------------------------------------- имена / тексты


def validate_name(text: Any) -> Optional[str]:
    """Имя 1–30 символов: только буквы, пробел и дефис. Иначе None."""
    raw = " ".join(str(text or "").split())
    if not raw or len(raw) > NAME_MAX_LEN:
        return None
    if "@" in raw or _LINK_RE.search(raw):
        return None
    for ch in raw:
        if ch.isalpha() or ch in " -":
            continue
        return None
    if not any(ch.isalpha() for ch in raw):
        return None
    if raw.startswith("-") or raw.endswith("-") or "--" in raw:
        return None
    return raw


def topic_label(topic: str) -> str:
    return TOPICS.get(topic, TOPICS["love"])["label"]


def short_roles(self_name: str, partner_name: str) -> List[str]:
    return [self_name, partner_name, *SHORT_FIXED_ROLES]


def full_roles(inviter_name: str, invitee_name: str) -> List[str]:
    return [inviter_name, invitee_name, *FULL_EXTRA_ROLES]


def build_compat_question(
    topic: str,
    first_name: str,
    second_name: str,
    *,
    full: bool,
) -> str:
    """Промпт по образцу romantic: роли карт + правила ответа, тема меняет трактовку."""
    t = TOPICS.get(topic, TOPICS["love"])
    a = first_name or "первый человек"
    b = second_name or "второй человек"
    lines = [
        f"Расклад «Совместимость» — тема: {t['label']}.",
        f"Два человека: {a} и {b}.",
        f"Смотрим именно в контексте темы: {t['about']}.",
        "",
        f"1-я карта ({a}): что {a} приносит в эту связь, каким(ой) {a} в ней бывает.",
        f"2-я карта ({b}): что {b} приносит в эту связь, каким(ой) {b} в ней бывает.",
        "3-я карта (Что вас связывает): общая основа, что притягивает и объединяет.",
    ]
    if full:
        lines += [
            "4-я карта (Что мешает): где трение, недопонимание или риск.",
            "5-я карта (Куда идёт): куда движется связь, если ничего резко не менять.",
        ]
    lines += [
        "",
        "Правила ответа:",
        f"- Пиши только по-русски, называй людей по именам «{a}» и «{b}».",
        f"- Держись темы «{t['label']}», не уходи в другие сферы жизни.",
        "- Без обещаний гарантированного результата, без запугивания и без советов "
        "расстаться или порвать отношения.",
        "- Тёплый, бережный тон: это взгляд карт, а не приговор.",
    ]
    if full:
        lines.append(
            "- В summary: главный вывод о совместимости и один мягкий совет "
            "(2–3 предложения, всего 150–250 символов)."
        )
    else:
        lines.append(
            "- В summary: короткий итог, что вас связывает (максимум 2 предложения)."
        )
    return "\n".join(lines)


def story_phrase(
    summary: str,
    limit: int = STORY_PHRASE_MAX,
    min_len: int = STORY_PHRASE_MIN,
) -> str:
    """Фраза для драпировки в сторис: целые предложения итога, пока не наберётся
    ~min_len символов, но не длиннее limit (иначе не влезет на ткань)."""
    text = " ".join(str(summary or "").split())
    if not text:
        return "Карты показали, что вас связывает 💞"
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    first = sentences[0]
    picked = first
    for sentence in sentences[1:]:
        if len(picked) >= min_len:
            break
        candidate = f"{picked} {sentence}"
        if len(candidate) > limit:
            break
        picked = candidate
    if len(picked) <= limit:
        return picked
    cut = first[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;:—- ") + "…"


def build_payload(invite_id: str) -> str:
    return f"{PAYLOAD_PREFIX}{invite_id}"


def parse_payload(payload: str) -> Optional[str]:
    raw = str(payload or "").strip()
    if not raw.startswith(PAYLOAD_PREFIX):
        return None
    invite_id = raw[len(PAYLOAD_PREFIX):]
    return invite_id if _ID_RE.fullmatch(invite_id) else None


def invite_message_text(inviter_name: str, link: str) -> str:
    return (
        f"{inviter_name} проверил(а) нашу совместимость 💞 "
        f"Посмотри, что говорят карты 👉 {link}"
    )


# ---------------------------------------------------------------- хранилище


@dataclass(frozen=True)
class OpenResult:
    """status: ok | self | expired | missing | busy | done | taken."""

    status: str
    invite: Optional[Dict[str, Any]] = None


class CompatInviteStore:
    def __init__(
        self,
        store: Any,
        *,
        doc_name: str = DOC_NAME,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.doc_name = doc_name
        self.now = now

    # -- низкий уровень
    @staticmethod
    def _norm(doc: Any) -> Dict[str, Any]:
        if not isinstance(doc, dict):
            doc = {}
        if not isinstance(doc.get("invites"), dict):
            doc["invites"] = {}
        if not isinstance(doc.get("pending"), dict):
            doc["pending"] = {}
        return doc

    def _update(self, mutator: Callable[[Dict[str, Any]], Any]) -> Any:
        box: Dict[str, Any] = {}

        def _m(current: Any) -> Dict[str, Any]:
            doc = self._norm(current)
            box["result"] = mutator(doc)
            return doc

        self.store.update_document(self.doc_name, _m, default={})
        return box.get("result")

    def _expired(self, inv: Dict[str, Any]) -> bool:
        return self.now() - float(inv.get("created_at") or 0) > INVITE_TTL_SECONDS

    # -- API
    def create_invite(
        self,
        *,
        inviter_id: int,
        inviter_name: str,
        partner_name: str,
        topic: str,
        cards: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        def _m(doc: Dict[str, Any]) -> Dict[str, Any]:
            invites = doc["invites"]
            invite_id = secrets.token_urlsafe(INVITE_ID_BYTES)
            while invite_id in invites:
                invite_id = secrets.token_urlsafe(INVITE_ID_BYTES)
            inv = {
                "id": invite_id,
                "inviter_id": int(inviter_id),
                "inviter_name": inviter_name,
                "partner_name": partner_name,
                "topic": topic if topic in TOPICS else "love",
                "cards": [
                    {
                        "path": c.get("path"),
                        "label": c.get("label"),
                        "reversed": bool(c.get("reversed")),
                    }
                    for c in cards[:3]
                ],
                "created_at": float(self.now()),
                "status": "open",
            }
            invites[invite_id] = inv
            return dict(inv)

        return self._update(_m)

    def get(self, invite_id: str) -> Optional[Dict[str, Any]]:
        return self._update(
            lambda doc: (
                dict(doc["invites"][invite_id])
                if invite_id in doc["invites"]
                else None
            )
        )

    def referrer_for(self, invite_id: str, user_id: int) -> Optional[int]:
        """Кто пригласил (для реферальной программы); None — своё/устарело/нет."""
        inv = self.get(invite_id)
        if not inv or self._expired(inv):
            return None
        inviter = int(inv.get("inviter_id") or 0)
        return inviter if inviter and inviter != int(user_id) else None

    def _status_for(self, inv: Optional[Dict[str, Any]], user_id: int) -> str:
        if not inv:
            return "missing"
        uid = int(user_id)
        if inv.get("status") == "completed":
            if uid in {int(inv.get("inviter_id") or 0), int(inv.get("invitee_id") or 0)}:
                return "done"
            return "taken"
        if int(inv.get("inviter_id") or 0) == uid:
            return "self"
        if self._expired(inv):
            return "expired"
        if inv.get("status") == "claimed":
            fresh = self.now() - float(inv.get("claimed_at") or 0) < CLAIM_STALE_SECONDS
            if fresh:
                return "busy" if int(inv.get("invitee_id") or 0) == uid else "taken"
        return "ok"

    def check(self, invite_id: str, user_id: int) -> OpenResult:
        inv = self.get(invite_id)
        return OpenResult(self._status_for(inv, user_id), inv)

    def claim(self, invite_id: str, user_id: int, invitee_name: str) -> OpenResult:
        """Атомарно занять приглашение под генерацию полного расклада."""

        def _m(doc: Dict[str, Any]) -> OpenResult:
            inv = doc["invites"].get(invite_id)
            status = self._status_for(inv, user_id)
            if status != "ok":
                return OpenResult(status, dict(inv) if inv else None)
            inv["status"] = "claimed"
            inv["invitee_id"] = int(user_id)
            inv["invitee_name"] = invitee_name
            inv["claimed_at"] = float(self.now())
            return OpenResult("ok", dict(inv))

        return self._update(_m)

    def release(self, invite_id: str, user_id: int) -> None:
        """Генерация не удалась — приглашение снова открыто."""

        def _m(doc: Dict[str, Any]) -> None:
            inv = doc["invites"].get(invite_id)
            if inv and inv.get("status") == "claimed" and int(inv.get("invitee_id") or 0) == int(user_id):
                inv["status"] = "open"
                inv.pop("claimed_at", None)

        self._update(_m)

    def complete(
        self,
        invite_id: str,
        user_id: int,
        *,
        cards: List[Dict[str, Any]],
        roles: List[str],
        texts: List[str],
        summary: str,
    ) -> Optional[Dict[str, Any]]:
        def _m(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            inv = doc["invites"].get(invite_id)
            if not inv or int(inv.get("invitee_id") or 0) != int(user_id):
                return None
            if inv.get("status") == "completed":
                return dict(inv)
            inv["status"] = "completed"
            inv["completed_at"] = float(self.now())
            inv["full"] = {
                "cards": [
                    {"path": c.get("path"), "label": c.get("label"), "reversed": bool(c.get("reversed"))}
                    for c in cards
                ],
                "roles": list(roles),
                "texts": list(texts),
                "summary": summary,
            }
            return dict(inv)

        return self._update(_m)

    # -- отложенное продолжение (пока человек принимает соглашение)
    def set_pending(self, chat_id: int, invite_id: str) -> None:
        def _m(doc: Dict[str, Any]) -> None:
            doc["pending"][str(chat_id)] = {"id": invite_id, "at": float(self.now())}

        self._update(_m)

    def pop_pending(self, chat_id: int) -> Optional[str]:
        def _m(doc: Dict[str, Any]) -> Optional[str]:
            item = doc["pending"].pop(str(chat_id), None)
            if not isinstance(item, dict):
                return None
            if self.now() - float(item.get("at") or 0) > PENDING_TTL_SECONDS:
                return None
            return str(item.get("id") or "") or None

        return self._update(_m)


# ---------------------------------------------------------------- аналитика

FUNNEL_EVENTS = (
    ("compat_start", "Начали"),
    ("compat_short_done", "Короткий расклад"),
    ("compat_invite_click", "Нажали «Позвать»"),
    ("compat_invite_open", "Друг открыл ссылку"),
    ("compat_full_done", "Полный расклад"),
    ("compat_story_share", "Сторис"),
    ("compat_live_click", "Живой разбор"),
)


def build_funnel_html(counts: Dict[str, Dict[str, int]], *, days: int) -> str:
    """counts: {event: {"events": n, "users": n}} → блок для админской статистики."""
    lines = [f"<b>💞 Совместимость — воронка за {days} дн.</b>"]
    for name, label in FUNNEL_EVENTS:
        c = counts.get(name) or {}
        lines.append(f"{label}: <b>{int(c.get('users', 0))}</b> чел. ({int(c.get('events', 0))})")
    return "\n".join(lines) + "\n"
