"""Simple in-memory FSM for MAX bot (resets on restart)."""

from __future__ import annotations

from typing import Any, Optional

# user_id -> {"state": str, "data": dict}
_sessions: dict[int, dict[str, Any]] = {}


def get_state(user_id: int) -> Optional[str]:
    s = _sessions.get(user_id)
    return s.get("state") if s else None


def get_data(user_id: int) -> dict[str, Any]:
    s = _sessions.get(user_id)
    return dict(s.get("data") or {}) if s else {}


def set_state(user_id: int, state: str | None, **data: Any) -> None:
    if state is None:
        _sessions.pop(user_id, None)
        return
    cur = _sessions.get(user_id) or {"state": state, "data": {}}
    cur["state"] = state
    cur_data = dict(cur.get("data") or {})
    cur_data.update(data)
    cur["data"] = cur_data
    _sessions[user_id] = cur


def clear(user_id: int) -> None:
    _sessions.pop(user_id, None)


# States
ASK_QUESTION = "ask_question"
ASK_CARDS = "ask_cards"
YESNO_QUESTION = "yesno_question"
YESNO_CARDS = "yesno_cards"
ROMANTIC = "romantic"
WARNING = "warning"
PROMO = "promo"
EMAIL = "email"
BROADCAST = "broadcast"
