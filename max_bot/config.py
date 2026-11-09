"""Env and paths for the MAX bot. Separate data from Telegram."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

MAX_BOT_TOKEN = (os.getenv("MAX_BOT_TOKEN") or "").strip()
MAX_WEBHOOK_SECRET = (os.getenv("MAX_WEBHOOK_SECRET") or "").strip()
MAX_API_BASE = (os.getenv("MAX_API_BASE") or "https://platform-api2.max.ru").rstrip("/")
MAX_BOT_USERNAME = (os.getenv("MAX_BOT_USERNAME") or "").strip().lstrip("@")
MAX_WEBHOOK_URL = (os.getenv("MAX_WEBHOOK_URL") or "").strip()
MAX_HOST = os.getenv("MAX_HOST", "0.0.0.0")
MAX_PORT = int(os.getenv("MAX_PORT", "8088"))

# Owner Telegram id from brief; override with MAX_ADMIN_IDS for real MAX user ids.
_admin_raw = (os.getenv("MAX_ADMIN_IDS") or os.getenv("ADMIN_IDS") or "491482483").strip()
MAX_ADMIN_IDS = {
    int(x.strip())
    for x in _admin_raw.split(",")
    if x.strip().isdigit()
}

CONSULTATION_URL = (
    os.getenv("CONSULTATION_URL") or "https://t.me/roxanaametist"
).strip()
CONSULTATION_BUTTON_TEXT = "✨ Консультация эзотерика (платно)"
CONSULTATION_MESSAGE = (
    "Приглашаем на индивидуальную платную консультацию ✨\n\n"
    "Таро, астрология, дизайн человека — персональный разбор вашей ситуации.\n\n"
    "Для записи и уточнения стоимости напишите Роксане в Telegram:\n"
    "https://t.me/roxanaametist"
)
_video = os.getenv("CONSULTATION_VIDEO_PATH", "static/consultation.mp4").strip()
CONSULTATION_VIDEO_PATH = _video if os.path.isabs(_video) else str(_ROOT / _video)
GROUP_INVITE_URL = (os.getenv("GROUP_INVITE_URL") or "").strip()
GROUP_BUTTON_TEXT = "👥 Наша группа"
BACK_BUTTON_TEXT = "◀️ Назад"
SUPPORT_TEXT = (
    "Если у вас возникли проблемы с ботом, нажмите /start. \n"
    "Если бот так и не заработал в течение 10-15 минут, обратитесь в тех. поддержку @Roxana_Ametist_bot"
)
HOW_IT_WORKS_TEXT = (
    "Как пользоваться ботом ⬇️\n\n"
    "• Нажми на кнопку «Задать вопрос». \n"
    "• Напиши свой вопрос для расклада и отправь боту. \n"
    "• Сделай расклад и выпавшие карты введи в бота (карты вводи через запятую).\n"
    "• А теперь жди трактовку расклада. \n\n"
    "С ❤️, ваш персональный бот от гадалочки-Роксаночки"
    "\n\n"
    "Ссылка на видео инструкцию по использованию бота:"
    "\n\n"
    "https://www.youtube.com/shorts/FPpt3rNHXck?si=xGoInzxR6y_OQFky"
)

# Те же адреса, что у Telegram-бота в main.py
PRIVACY_URL = os.getenv("PRIVACY_URL", "https://followthefrensy.ru/privacy").strip()
OFERTA_URL = os.getenv("OFERTA_URL", "https://followthefrensy.ru/oferta").strip()
AGREEMENT_URL = (os.getenv("MAX_AGREEMENT_URL") or OFERTA_URL).strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/follow_the_frensy").strip()
CARDS_WEBAPP_URL = os.getenv("CARDS_WEBAPP_URL", "https://followthefrensy.ru/cards/").strip()
YESNO_WEBAPP_URL = os.getenv("YESNO_WEBAPP_URL", "https://followthefrensy.ru/yesno/").strip()
# .com не резолвится. Мини-приложения живут на followthefrensy.ru.
MAX_CARDS_MINIAPP_URL = (
    os.getenv("MAX_CARDS_MINIAPP_URL") or "https://followthefrensy.ru/cards/"
).strip()
MAX_YESNO_MINIAPP_URL = (
    os.getenv("MAX_YESNO_MINIAPP_URL") or "https://followthefrensy.ru/yesno/"
).strip()
MAX_PAYMENT_RETURN_URL = (
    os.getenv("MAX_PAYMENT_RETURN_URL")
    or (f"https://max.ru/{MAX_BOT_USERNAME}" if MAX_BOT_USERNAME else "https://max.ru")
).strip()

LLM_PUBLIC_STUB = os.getenv("LLM_PUBLIC_STUB", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
LLM_STUB_ALLOW_IDS = set(MAX_ADMIN_IDS)
LLM_PUBLIC_STUB_TEXT = (
    "Интерпретации раскладов с помощью нейросети будут доступны позднее"
)

BTN_ASK = "🔮✨  Задать вопрос  ✨🔮"
BTN_DAY = "🔮✨Карта дня ✨🔮"
BTN_YESNO = "🔮✨  Да/Нет  ✨🔮"
BTN_ROMANTIC = "🔮✨Чувства Мысли Действия ✨🔮"
BTN_WARN = "🔮✨Предупреждение от карт ✨🔮"
BTN_BALANCE = "💎 Мой баланс"
BTN_PAY = "💳 Оформить подписку"
BTN_SUPPORT = "🛠 Техподдержка"
BTN_HOW = "ℹ️ Как работает бот"
BTN_REFERRAL = "👥 Пригласить друга (+5)"
BTN_PROMO = "🎟 Промокод"
BTN_EXTRA = "🎁 Получить дополнительные расклады!"
BTN_BROADCAST = "📣 Сообщение пользователям"
BTN_STATS = "📊 Статистика"

ROMANTIC_INTRO = (
    "Чувства Мысли Действия\n\n"
    "В этом разделе ты сможешь узнать чувства, мысли и действия партнера.\n\n"
    "Все просто!\n\n"
    "МЫСЛЕННО задавай вопрос 🔮\n\n"
    "1-я карта отвечает на вопрос: Что чувствует партнер?\n"
    "2-я карта показывает: О чем думает партнер?\n"
    "3-я карта раскрывает: Какие действия предпримет партнер?\n\n"
    "Если у вас есть физическая колода на руках:\n"
    "Введите 3 карты, которые у вас выпали через запятую 🙌\n\n"
    "Если у вас нет физической колоды:\n"
    "Нажми кнопку в меню «Выбрать карты», и выберите 3 карты из 7 карт."
)
WARN_INTRO = (
    "Предупреждение от карт\n\n"
    "В этом разделе ты сможешь узнать предупреждение от карт.\n\n"
    "Все просто!\n\n"
    "МЫСЛЕННО задавай вопрос 🔮\n\n"
    "1-я карта отвечает на вопрос: Описание ситуации?\n"
    "2-я карта показывает: Возможные негативные последствия?\n"
    "3-я карта раскрывает: Совет для нейтрализации негативных последствий?\n\n"
    "Если у вас есть физическая колода на руках:\n"
    "Введите 3 карты, которые у вас выпали через запятую 🙌\n\n"
    "Если у вас нет физической колоды:\n"
    "Нажми кнопку в меню «Выбрать карты», и выберите 3 карты из 7 карт."
)
ROMANTIC_SPREAD_QUESTION = (
    "Расклад «Чувства / Мысли / Действия».\n"
    "1-я карта: что чувствует партнер.\n"
    "2-я карта: о чём думает партнер.\n"
    "3-я карта: какие действия предпримет партнер."
)
ROMANTIC_CARD_ROLES = ["Чувства", "Мысли", "Действия"]
DANGEROUS_SPREAD_QUESTION = (
    "Расклад «Предупреждение от карт».\n"
    "1-я карта: описание ситуации.\n"
    "2-я карта: возможные негативные последствия.\n"
    "3-я карта: совет для нейтрализации негативных последствий."
)
DANGEROUS_CARD_ROLES = ["Описание ситуации", "Негативные последствия", "Совет"]
REFERRAL_HINT = (
    "\n\n👥 Реферальная система: «Пригласить друга (+5)» в меню — "
    "за каждого нового пользователя по вашей ссылке вам +5 раскладов."
)

# LLM — same names as Telegram bot
TAROT_PROVIDER_RAW = (os.getenv("TAROT_PROVIDER") or "").strip().lower()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
GROQ_TAROT_MODEL = os.getenv("GROQ_TAROT_MODEL", "llama-3.3-70b-versatile").strip()
OPENAI_TAROT_MODEL = os.getenv("OPENAI_TAROT_MODEL", "gpt-4o-mini").strip()
TAROT_MAX_TOKENS = int(os.getenv("GROQ_TAROT_MAX_TOKENS", "1100"))
GROQ_FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("GROQ_TAROT_FALLBACK_MODELS", "llama-3.1-8b-instant").split(",")
    if m.strip() and m.strip() != GROQ_TAROT_MODEL
]

# Как в текущем Telegram-боте: +5 рефереру за нового пользователя по ссылке.
REFERRAL_JOIN_BONUS = 5
LANDING_START_PARAM = os.getenv("LANDING_BOT_START_PARAM", "site").strip()

DATA_DIR = Path(
    os.getenv("MAX_BOT_DATA_DIR")
    or os.getenv("BOT_DATA_DIR")
    or (_ROOT / "data_max")
)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def data_file(name: str) -> Path:
    return DATA_DIR / name


USER_DATA_FILE = data_file("user_data_max.json")
AGREEMENTS_FILE = data_file("user_agreements_max.json")
LOGS_FILE = data_file("logs_max.json")
READING_HISTORY_FILE = data_file("reading_history_max.json")
DAY_CARD_FILE = data_file("chat_data_max.json")
STATUS_FILE = data_file("status_data_max.json")
PROMO_FILE = data_file("used_promocodes_max.json")
ORDER_FILE = data_file("order_number_max.json")
PAYMENT_FILE = data_file("payment_data_max.json")
