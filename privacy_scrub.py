"""Strip contact identifiers from text before it goes to a foreign LLM.

Does not make Telegram anonymous: Bot API still needs chat_id.
First names in questions are kept so readings still make sense.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
_TG_USER = re.compile(r"(?<!\w)@([A-Za-z][A-Za-z0-9_]{3,31})\b")
_TG_LINK = re.compile(
    r"https?://(?:t\.me|telegram\.me)/[^\s]+",
    re.IGNORECASE,
)
_WA_LINK = re.compile(
    r"https?://(?:wa\.me|api\.whatsapp\.com)/[^\s]+",
    re.IGNORECASE,
)
_PHONE = re.compile(
    r"(?<!\d)(?:\+?7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"
)
_LONG_ID = re.compile(r"(?<!\d)\d{11,19}(?!\d)")
_NAMED_ID = re.compile(
    r"(?i)\b(?:telegram\s*id|user\s*id|chat\s*id|userid|chatid)\s*[:=#]?\s*\d+\b"
)
_CALLED = re.compile(
    r"(?i)\b(?:меня\s+зовут|мое\s+имя|моё\s+имя)\s+[А-ЯЁA-Z][а-яёa-z\-]+"
        r"(?:\s+[А-ЯЁA-Z][а-яёa-z\-]+){0,2}"
)
_FIO = re.compile(
    r"\b[А-ЯЁ][а-яё]{1,20}\s+[А-ЯЁ][а-яё]{1,20}\s+[А-ЯЁ][а-яё]{1,20}\b"
)


def scrub_prompt_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text or ""
    t = text
    t = _EMAIL.sub("[email]", t)
    t = _TG_LINK.sub("[ссылка]", t)
    t = _WA_LINK.sub("[ссылка]", t)
    t = _TG_USER.sub("[ник]", t)
    t = _NAMED_ID.sub("[id]", t)
    t = _PHONE.sub("[телефон]", t)
    t = _LONG_ID.sub("[id]", t)
    t = _CALLED.sub("[имя]", t)
    t = _FIO.sub("[ФИО]", t)
    return t
