"""LLM tarot readings — port of main.py prompts / structured JSON."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional

from openai import OpenAI

from privacy_scrub import scrub_prompt_text

from . import config

logger = logging.getLogger(__name__)

TAROT_SYSTEM_PROMPT = (
    "Ты опытный русскоязычный таролог-консультант Follow the Frensy. "
    "Отвечай ТОЛЬКО на русском: без английских слов и латиницы в обычном тексте "
    "(исключение — имена, если пользователь написал их латиницей). "
    "Стиль: коротко, ясно, по делу. Без воды, без поэзии, без общих фраз про «энергии вселенной». "
    "Главная цель — прямой полезный ответ на КОНКРЕТНЫЙ вопрос через выпавшие карты. "
    "Не уходи в сторону: не советуй покупки, гаджеты и чужие темы, если их нет в вопросе. "
    "Не пиши «я не понял вопрос», «переформулируйте» — отвечай по сути. "
    "Не путай «Верховная Жрица» (II) и «Иерофант» (V). "
    "Не давай энциклопедии по картам: каждая фраза связывает карту с ситуацией из вопроса. "
    "Строго следуй формату ответа из запроса пользователя. "
    "В тексте вопроса контакты могут быть заменены на [телефон], [email], [ник], [id], [имя], [ФИО] — "
    "отвечай по ситуации, не проси настоящие данные и не выдумывай их."
)

TAROT_CARD_MAX_CHARS = 280
TAROT_CARD_MAX_SENTENCES = 2
TAROT_SUMMARY_MAX_CHARS = 420
TAROT_SUMMARY_MAX_SENTENCES = 3

_groq_client: Optional[OpenAI] = None
_openai_client: Optional[OpenAI] = None


def _init_clients() -> None:
    global _groq_client, _openai_client
    if config.GROQ_API_KEY and _groq_client is None:
        _groq_client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    if config.OPENAI_API_KEY and _openai_client is None:
        _openai_client = OpenAI(api_key=config.OPENAI_API_KEY)


def tarot_provider() -> str:
    raw = config.TAROT_PROVIDER_RAW
    if raw in {"openai", "groq"}:
        return raw
    return "openai" if config.OPENAI_API_KEY else "groq"


def clean_tarot_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.strip()
    if not t:
        return ""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"```(?:json|JSON)?", "", t)
    t = t.replace("```", "")
    t = re.sub(r"[*_`#>]{1,}", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    banned = (
        r"\b(?:insufficient|undefined|null|NaN|error|TODO|as an AI|I cannot|"
        r"I'm sorry|High Priestess|Hierophant|The Fool|The Magician|summary|"
        r"card_interpretations|JSON|markdown)\b"
    )
    t = re.sub(banned, "", t, flags=re.IGNORECASE)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip(" \n\t-–—|")


def tighten_tarot_text(
    text: str,
    *,
    max_chars: int,
    max_sentences: int,
) -> str:
    t = clean_tarot_text(text)
    if not t:
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", t) if p.strip()]
    if len(parts) > max_sentences:
        t = " ".join(parts[:max_sentences])
    if len(t) > max_chars:
        cut = t[: max_chars - 1]
        sp = cut.rfind(" ")
        if sp > max_chars // 2:
            cut = cut[:sp]
        t = cut.rstrip(" ,;:—-") + "…"
    return t


def _is_rate_limit_error(err: BaseException) -> bool:
    text = str(err).lower()
    return (
        "429" in text
        or "rate_limit" in text
        or "tokens per day" in text
        or "tpd" in text
        or "insufficient_quota" in text
    )


async def _call_openai_chat(
    *,
    user_message: str,
    system_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    _init_clients()
    if _openai_client is None:
        raise RuntimeError("OPENAI_API_KEY не задан")
    response = await asyncio.to_thread(
        lambda: _openai_client.chat.completions.create(
            model=config.OPENAI_TAROT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=45.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
    )
    content = response.choices[0].message.content
    if isinstance(content, str) and content.strip():
        return content
    raise ValueError("Empty OpenAI response")


async def _call_groq_chat(
    *,
    user_message: str,
    system_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    _init_clients()
    if _groq_client is None:
        raise RuntimeError("GROQ_API_KEY не задан")
    last_err: Optional[BaseException] = None
    models = [config.GROQ_TAROT_MODEL] + config.GROQ_FALLBACK_MODELS
    for model in models:
        for attempt in range(2):
            try:
                response = await asyncio.to_thread(
                    lambda m=model: _groq_client.chat.completions.create(
                        model=m,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=45.0,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                    )
                )
                content = response.choices[0].message.content
                if isinstance(content, str) and content.strip():
                    return content
                last_err = ValueError("Empty Groq response")
            except Exception as e:
                last_err = e
                logger.warning("Groq model=%s attempt %s failed: %s", model, attempt + 1, e)
                if _is_rate_limit_error(e):
                    break
            await asyncio.sleep(0.35 + attempt * 0.35)
    raise RuntimeError(f"Groq failed: {last_err}")


async def get_tarot_reading(user_message: str) -> str:
    user_message = scrub_prompt_text(user_message)
    order = (
        ["openai", "groq"] if tarot_provider() == "openai" else ["groq", "openai"]
    )
    last_err: Optional[BaseException] = None
    for provider in order:
        try:
            if provider == "openai":
                text = await _call_openai_chat(
                    user_message=user_message,
                    system_prompt=TAROT_SYSTEM_PROMPT,
                    temperature=0.25,
                    max_tokens=min(config.TAROT_MAX_TOKENS, 1100),
                )
                logger.info("Tarot reply via OpenAI")
                return text
            text = await _call_groq_chat(
                user_message=user_message,
                system_prompt=TAROT_SYSTEM_PROMPT,
                temperature=0.25,
                max_tokens=config.TAROT_MAX_TOKENS,
            )
            logger.info("Tarot reply via Groq")
            return text
        except Exception as e:
            last_err = e
            logger.warning("Tarot provider %s failed: %s", provider, e)
    raise RuntimeError(f"Tarot LLM request failed: {last_err}")


async def get_tarot_reading_structured(
    question: str,
    card_meanings_in_order: list[str],
    card_roles_in_order: Optional[list[str]] = None,
) -> dict:
    expected_n = len(card_meanings_in_order)
    roles = card_roles_in_order or []
    question = (question or "").strip()
    if not question:
        question = "О чём говорят выпавшие карты в текущей жизненной ситуации пользователя?"

    lines = []
    for i, meaning in enumerate(card_meanings_in_order):
        role_prefix = f" ({roles[i]})" if i < len(roles) and roles[i] else ""
        lines.append(f"{i+1}.{role_prefix} {meaning}")

    def build_prompt(strict: bool) -> str:
        json_example = json.dumps(
            {
                "card_interpretations": [
                    f"Ответ по карте {i+1} именно на вопрос пользователя..."
                    for i in range(expected_n)
                ],
                "summary": "Прямой итоговый ответ на вопрос пользователя...",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        strict_line = "- Не допускаются пустые трактовки и общие отписки.\n" if strict else ""
        role_line = (
            "- Учитывай роль карты в раскладе, но отвечай в контексте вопроса.\n"
            if any(roles)
            else ""
        )
        return (
            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ (это главное — ответь именно на него):\n«{question}»\n\n"
            f"Выпавшие карты (по порядку, используй ТОЧНО эти названия):\n"
            + "\n".join(lines)
            + "\n\n"
            + "Ответь СТРОГО одним JSON-объектом без Markdown и без текста вокруг.\n"
            + "Формат:\n"
            + f"{json_example}\n\n"
            + "Правила (по приоритету):\n"
            + "1) Каждая трактовка ОБЯЗАНА отвечать на вопрос пользователя через смысл карты.\n"
            + "2) Запрещены абстрактные описания без связи с вопросом.\n"
            + f"3) Дай РОВНО {expected_n} трактовок, строго по порядку карт.\n"
            + "4) summary — очень краткий прямой ответ: вывод + один следующий шаг "
            + f"(максимум {TAROT_SUMMARY_MAX_SENTENCES} коротких предложения).\n"
            + f"5) Пиши только по-русски. На каждую трактовку — "
            + f"{TAROT_CARD_MAX_SENTENCES} коротких предложения.\n"
            + "6) Если в названии карты есть «(перевёрнутая)» — трактуй как перевёрнутую.\n"
            + role_line
            + strict_line
        )

    async def call_and_parse(strict: bool) -> dict:
        raw = await get_tarot_reading(build_prompt(strict))
        start = raw.find("{")
        end = raw.rfind("}")
        raw_json = raw[start : end + 1] if start != -1 and end != -1 and end > start else raw
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            raise ValueError("Not a JSON object")
        return data

    try:
        data = await call_and_parse(strict=False)
    except Exception as e:
        logger.warning("Structured tarot parse failed: %s", e)
        data = {"card_interpretations": [], "summary": ""}

    ci = data.get("card_interpretations") if isinstance(data, dict) else None
    summary = data.get("summary") if isinstance(data, dict) else None
    ok_ci = (
        isinstance(ci, list)
        and len(ci) == expected_n
        and all(isinstance(x, str) and x.strip() for x in ci)
    )
    ok_summary = True if expected_n <= 1 else isinstance(summary, str) and summary.strip()
    if not (ok_ci and ok_summary):
        try:
            data2 = await call_and_parse(strict=True)
            ci2 = data2.get("card_interpretations")
            summary2 = data2.get("summary")
            ok_ci2 = (
                isinstance(ci2, list)
                and len(ci2) == expected_n
                and all(isinstance(x, str) and x.strip() for x in ci2)
            )
            ok_summary2 = (
                True if expected_n <= 1 else isinstance(summary2, str) and summary2.strip()
            )
            if ok_ci2 and ok_summary2:
                return data2
        except Exception as e:
            logger.warning("Structured tarot strict retry failed: %s", e)

    if not isinstance(ci, list):
        ci = []
    ci = [clean_tarot_text(x) if isinstance(x, str) else "" for x in ci]
    while len(ci) < expected_n:
        ci.append("")
    ci = ci[:expected_n]
    if not isinstance(summary, str):
        summary = ""
    return {"card_interpretations": ci, "summary": clean_tarot_text(summary)}


def structured_is_complete(structured: dict, expected_n: int) -> bool:
    ci = structured.get("card_interpretations")
    if not isinstance(ci, list) or len(ci) != expected_n:
        return False
    return all(isinstance(x, str) and x.strip() for x in ci)


async def fetch_structured_reading(
    question_text: str,
    card_labels: list[str],
    card_roles: Optional[list[str]] = None,
) -> dict:
    structured = None
    expected_n = len(card_labels)
    for attempt in range(3):
        try:
            structured_try = await get_tarot_reading_structured(
                question_text, card_labels, card_roles_in_order=card_roles
            )
            if structured_is_complete(structured_try, expected_n):
                structured = structured_try
                break
        except Exception:
            pass
        await asyncio.sleep(0.35 + attempt * 0.35)
    if not structured:
        structured = {"card_interpretations": [], "summary": ""}
    return structured
