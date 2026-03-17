import logging
import os
from aiogram.fsm.storage.memory import MemoryStorage
from openai import OpenAI
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from aiogram.handlers import CallbackQueryHandler
import asyncio
import json
from typing import Dict, Optional, List
from aiogram.enums import ParseMode
import re
from aiogram.types import FSInputFile, ChatMemberMember, ChatMemberOwner
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, ContentType
from datetime import datetime, timedelta
from yookassa import Configuration, Payment
import uuid
import random

#MAKS API_TOKEN = '...'
#DEMID API_TOKEN = '...'
API_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Клиент Groq в режиме OpenAI-совместимого API
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# URLs мини‑приложений (WebApp)
CARDS_WEBAPP_URL = "https://followthefrensy.ru/cards"
YESNO_WEBAPP_URL = "https://followthefrensy.ru/yesno"

channel_id = -1001887928983

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=storage)

GOODS = {
    "demo": 1
}


class Form(StatesGroup):
    question = State()
    cards = State()

class Form2(StatesGroup):
    question = State()
    cards = State()

tarot_cards = {}


class Promo(StatesGroup):
    prikol=State()


class Email(StatesGroup):
    email_check=State()


class Mess_check(StatesGroup):
    message_id=State()


class romantic(StatesGroup):
    quest = State()


class dangerous(StatesGroup):
    dan = State()

#-----------------------------------------------------------------------------------------------------------------------


class Logger:
    def __init__(self, file_path: str = "logs.json"):
        self.file_path = file_path
        self.logs: List[Dict] = self._load_logs()

    def _load_logs(self) -> List[Dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return []

    def _save_logs(self):
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(self.logs, file, ensure_ascii=False, indent=4)

    def log_command(self, user_id: int, command: str):
        log_entry = {
            "user_id": user_id,
            "command": command,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.logs.append(log_entry)
        self._save_logs()

    def get_user_stats(self, user_id: int) -> List[Dict]:
        return [log for log in self.logs if log["user_id"] == user_id]

    def get_date_stats(self, date: str) -> List[Dict]:
        return [log for log in self.logs if log["date"].startswith(date)]

    def get_command_stats(self, command: str) -> List[Dict]:
        return [log for log in self.logs if log["command"] == command]

    def get_new_users_today(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        today_logs = self.get_date_stats(today)
        existing_users = set(log["user_id"] for log in self.logs if not log["date"].startswith(today))
        new_users = set(log["user_id"] for log in today_logs) - existing_users
        return len(new_users)

    def get_total_users(self) -> int:
        unique_users = set(log["user_id"] for log in self.logs)
        return len(unique_users)

    def get_stats_last_x_days(self, x: int) -> List[Dict]:
        x_days_ago = (datetime.now() - timedelta(days=x)).strftime("%Y-%m-%d")
        return [log for log in self.logs if log["date"] >= x_days_ago]

logger = Logger()

#-----------------------------------------------------------------------------------------------------------------------

class UserData:
    def __init__(self, filename: str = 'user_data.json'):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self) -> Dict[str, Dict[str, int]]:
        try:
            with open(self.filename, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_data(self) -> None:
        with open(self.filename, 'w') as file:
            json.dump(self.data, file)

    def add_user(self, chat_id: int) -> None:
        if str(chat_id) not in self.data:
            # Новый пользователь получает 5 вопросов один раз при первой регистрации
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.data[str(chat_id)] = {
                'questions': 5,
                'subscription_end': None,
                'email': None,
                # Для автопополнения раз в 30 дней
                'last_refill_at': now_str,
            }
            self.save_data()

    def get_user_questions(self, chat_id: int) -> int:
        return self.data.get(str(chat_id), {}).get('questions', 0)

    def decrement_user_questions(self, chat_id: int) -> None:
        if str(chat_id) in self.data:
            self.data[str(chat_id)]['questions'] -= 1
            self.save_data()

    def increment_user_questions(self, chat_id: int, amount: int) -> None:
        if str(chat_id) in self.data:
            self.data[str(chat_id)]['questions'] += amount
            self.save_data()

    def set_user_questions(self, chat_id: int, amount: int) -> None:
        """Устанавливает конкретное количество вопросов пользователю."""
        if str(chat_id) not in self.data:
            self.add_user(chat_id)
        self.data[str(chat_id)]['questions'] = amount
        self.save_data()

    def set_subscription_end(self, chat_id: int, end_time_str: str) -> None:
        if str(chat_id) in self.data:
            # Преобразуем строку в объект datetime
            end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
            self.data[str(chat_id)]['subscription_end'] = end_time_str
            self.save_data()

    def get_subscription_end(self, chat_id: int) -> Optional[datetime]:
        end_time_str = self.data.get(str(chat_id), {}).get('subscription_end')
        if end_time_str:
            return datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
        return None

    def extend_subscription(self, chat_id: int, days: int) -> None:
        new_end = datetime.now() + timedelta(days=days)
        self.set_subscription_end(chat_id, new_end.strftime('%Y-%m-%d %H:%M:%S'))

    def set_user_email(self, chat_id: int, email: str) -> None:
        if not self.is_valid_email(email):
            raise ValueError("Некорректный email адрес.")
        if str(chat_id) in self.data:
            self.data[str(chat_id)]['email'] = email
            self.save_data()

    def get_user_email(self, chat_id: int) -> Optional[str]:
        return self.data.get(str(chat_id), {}).get('email')

    def is_valid_email(self, email: str) -> bool:
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

    def get_filtered_user_ids(self, excluded_ids: List[int]) -> List[int]:
        all_ids = self.data.keys()

        excluded_ids_str = set(map(str, excluded_ids))

        return [int(chat_id) for chat_id in all_ids if chat_id not in excluded_ids_str]

    def get_last_refill_at(self, chat_id: int) -> Optional[datetime]:
        val = self.data.get(str(chat_id), {}).get('last_refill_at')
        if not val:
            return None
        try:
            return datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None

    def set_last_refill_at(self, chat_id: int, dt: datetime) -> None:
        if str(chat_id) not in self.data:
            self.add_user(chat_id)
        self.data[str(chat_id)]['last_refill_at'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        self.save_data()

user_data = UserData()

#-----------------------------------------------------------------------------------------------------------------------

class GrantState:
    """Небольшое состояние, чтобы не начислять месячные бонусы повторно при перезапуске."""
    def __init__(self, filename: str = "grant_state.json"):
        self.filename = filename
        self.data = self._load()

    def _load(self) -> Dict[str, str]:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _save(self) -> None:
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, key: str) -> Optional[str]:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value
        self._save()


grant_state = GrantState()

class StatusData:
    def __init__(self, filename: str = 'status_data.json'):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self) -> Dict[str, int]:
        try:
            with open(self.filename, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_data(self) -> None:
        with open(self.filename, 'w') as file:
            json.dump(self.data, file)

    def set_status(self, chat_id: int, status: int) -> None:
        if status not in (0, 1):
            raise ValueError("Статус должен быть 0 или 1.")
        self.data[str(chat_id)] = status
        self.save_data()

    def toggle_status(self, chat_id: int) -> None:
        current_status = self.data.get(str(chat_id), None)
        if current_status is None:
            self.set_status(chat_id, 0)
        else:
            new_status = 1 if current_status == 0 else 0
            self.set_status(chat_id, new_status)

    def is_status_zero(self, chat_id: int) -> bool:
        if str(chat_id) not in self.data:
            self.set_status(chat_id, 0)
            return True
        return self.data[str(chat_id)] == 0

status_data = StatusData()


#-----------------------------------------------------------------------------------------------------------------------

class PhotoSender:
    def __init__(self, bot):
        self.bot = bot

    async def send_photo(self, chat_id, photo_path, caption=None, parse_mode=None, reply_markup=None):
        try:
            photo = FSInputFile(photo_path)
            await self.bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")
            #Макс Лох 228

    async def send_photos(self, chat_id, photo_paths, caption=None, parse_mode=None):
        for photo_path in photo_paths:
            await self.send_photo(chat_id, photo_path, caption, parse_mode)

photo_sender = PhotoSender(bot)

#--------------------------------------------------------------------------------------------------------------------------

class OrderNumber:
    def __init__(self, filename='order_number.json'):
        self.filename = filename
        self.order_number = 0
        self.load_order_number()

    def load_order_number(self):
        try:
            with open(self.filename, 'r') as file:
                data = json.load(file)
                self.order_number = data.get('order_number', 0)
        except FileNotFoundError:
            self.order_number = 0

    def save_order_number(self):
        with open(self.filename, 'w') as file:
            json.dump({'order_number': self.order_number}, file)

    def increment_order_number(self):
        self.order_number += 1
        self.save_order_number()

    def get_order_number(self):
        return self.order_number

order_manager = OrderNumber()

#-----------------------------------------------------------------------------------------------------------------------------------------------------

class OneDayCard:
    def __init__(self, filename='chat_data.json'):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self):
        try:
            with open(self.filename, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_data(self):
        with open(self.filename, 'w') as file:
            json.dump(self.data, file)

    def add_chat(self, chat_id):
        if chat_id not in self.data:
            self.data[chat_id] = {'map': None, 'date': None}
            self.save_data()

    def update_date_if_needed(self, chat_id):
        today = datetime.now().date()
        if chat_id in self.data:
            chat_info = self.data[chat_id]
            current_date = chat_info.get('date')

            if current_date is None or current_date != str(today):
                chat_info['date'] = str(today)
                self.save_data()
                return True
        return False

    def select_random_card(self, chat_id):
        if chat_id in self.data:
            selected_card = random.randrange(1,78)
            self.data[chat_id]['map'] = selected_card
            self.save_data()
            return selected_card
        return None

one_card = OneDayCard()

#-----------------------------------------------------------------------------------------------------------------------

class AgreementManager:
    def __init__(self, file_path='user_agreements.json'):
        self.file_path = file_path
        self.agreement_text = (
            "Пожалуйста, ознакомьтесь с нашим дополнительным соглашением по ссылке:\n\n"
            "1. Вы соглашаетесь на обработку персональных данных.\n"
            "2. Вы принимаете условия использования бота.\n"
            "3. Вы подтверждаете, что вам больше 18 лет."
        )

    def load_agreements(self):
        try:
            with open(self.file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_agreements(self, agreements):
        with open(self.file_path, 'w') as file:
            json.dump(agreements, file, indent=4)

    def user_has_agreed(self, user_id):
        agreements = self.load_agreements()
        return str(user_id) in agreements

    def add_user_agreement(self, user_id):
        agreements = self.load_agreements()
        agreements[str(user_id)] = True
        self.save_agreements(agreements)

agreement_manager = AgreementManager()

def get_agreement_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="agree")
    builder.button(text="❌ Отказаться", callback_data="disagree")
    return builder.as_markup()

#----------------------------------------------------------------------------------------------------------------------------------
class AdminManager:
    def __init__(self, file_path='admins.json'):
        self.file_path = file_path

    def load_admins(self):
        try:
            with open(self.file_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_admins(self, admins):
        with open(self.file_path, 'w') as file:
            json.dump(admins, file, indent=4)

    def is_admin(self, user_id: int) -> bool:
        admins = self.load_admins()
        return str(user_id) in admins

    def add_admin(self, user_id: int):
        admins = self.load_admins()
        admins[str(user_id)] = True
        self.save_admins(admins)


admin_manager = AdminManager()

#----------------------------------------------------------------------------------------------------------------------------------


def split_text_into_paragraphs(text):
    paragraphs = text.split('\n\n')
    return paragraphs

async def get_card_names(card_list):
    return ", ".join([tarot_cards[card] for card in card_list])

async def get_tarot_reading(user_message):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a tarot reader who provides insightful and mystical interpretations of tarot card spreads."},
            {"role": "user", "content": user_message}
        ]
    )
    return response.choices[0].message.content


async def get_tarot_reading_structured(question: str, card_meanings_in_order: list[str]) -> dict:
    """
    Возвращает структурированный ответ:
    {
      "card_interpretations": ["...", "...", "..."],
      "summary": "..."
    }
    """
    user_prompt = (
        "Вопрос пользователя:\n"
        f"{question}\n\n"
        "Карты (строго по порядку, только значения, без названий):\n"
        + "\n".join([f"{i+1}. {m}" for i, m in enumerate(card_meanings_in_order)])
        + "\n\n"
          "Ответь СТРОГО в JSON без Markdown и без лишнего текста, в одну строку.\n"
          "Формат:\n"
          "{"
          "\"card_interpretations\":[\"...\",\"...\",\"...\"],"
          "\"summary\":\"...\""
          "}\n\n"
          "Правила:\n"
          "- Каждая интерпретация должна быть напрямую привязана к вопросу пользователя.\n"
          "- В summary дай итоговый ответ на вопрос с учетом всех карт (обязательно).\n"
          "- Не используй слова вроде SUMMARY/ИТОГ/РЕЗЮМЕ как маркеры, просто текст.\n"
          "- Не перечисляй названия карт.\n"
          "- Пиши по-русски."
    )

    raw = await get_tarot_reading(user_prompt)
    # Пытаемся вытащить JSON даже если модель добавила мусор
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        raw_json = raw[start : end + 1] if start != -1 and end != -1 and end > start else raw
        data = json.loads(raw_json)
        if not isinstance(data, dict):
            raise ValueError("Not a JSON object")
        return data
    except Exception:
        # Фоллбек: вернем как один общий текст, чтобы бот не молчал
        return {"card_interpretations": [], "summary": raw}

PAYMENT_FILE = "payment_data.json"

def initialize_payment_file():
    """Инициализация файла с данными, если он отсутствует."""
    try:
        with open(PAYMENT_FILE, "r") as file:
            pass
    except FileNotFoundError:
        with open(PAYMENT_FILE, "w") as file:
            json.dump({"total_amount": 0, "subscriptions": {"10": 0, "30": 0, "7d": 0, "14d": 0, "30d": 0}}, file)


def update_payment_data(amount, subscription_type):
    """Обновляет данные о платежах в файле."""
    with open(PAYMENT_FILE, "r") as file:
        data = json.load(file)

    # Обновление общей суммы
    data["total_amount"] += amount

    # Обновление количества подписок
    if subscription_type in data["subscriptions"]:
        data["subscriptions"][subscription_type] += 1

    # Сохранение обновлений
    with open(PAYMENT_FILE, "w") as file:
        json.dump(data, file, indent=4)

async def pidor_doma():
    while True:
        today = datetime.today().date()
        if today.day == 1:
            # Защита от повторного начисления в тот же день при перезапуске бота
            last_run = grant_state.get("monthly_15_last_date")
            if last_run == str(today):
                await asyncio.sleep(3600)
                continue

            filtered_ids = user_data.get_filtered_user_ids([343465637])
            for pid_chat_id in filtered_ids:
                if isinstance(await bot.get_chat_member(channel_id, pid_chat_id), ChatMemberMember) or isinstance(
                        await bot.get_chat_member(channel_id, pid_chat_id), ChatMemberOwner):
                    await bot.send_message(pid_chat_id, "Вам добавились 15 ежемесячных вопросов!")
                    user_data.increment_user_questions(pid_chat_id, 15)
            grant_state.set("monthly_15_last_date", str(today))
        await asyncio.sleep(86400)


async def periodic_30day_refill():
    """
    Каждые 30 календарных дней начисляет +5 вопросов и присылает уведомление.
    Проверка выполняется 1 раз в сутки.
    """
    while True:
        now = datetime.now()
        # Снимок пользователей, чтобы не ломаться если data меняется
        user_ids = list(user_data.data.keys())
        for chat_id_str in user_ids:
            try:
                chat_id = int(chat_id_str)
            except ValueError:
                continue

            last_refill = user_data.get_last_refill_at(chat_id)
            if last_refill is None:
                user_data.set_last_refill_at(chat_id, now)
                continue

            delta_days = (now.date() - last_refill.date()).days
            if delta_days < 30:
                continue

            periods = delta_days // 30
            if periods <= 0:
                continue

            add_amount = 5 * periods
            user_data.increment_user_questions(chat_id, add_amount)
            # Сдвигаем дату на целые периоды, чтобы не начислять повторно
            new_last = last_refill + timedelta(days=30 * periods)
            user_data.set_last_refill_at(chat_id, new_last)

            try:
                await bot.send_message(
                    chat_id,
                    f"Вам начислено {add_amount} вопросов (пополнение раз в 30 дней).",
                )
            except Exception:
                # Пользователь мог заблокировать бота
                pass

        await asyncio.sleep(86400)

#---------------------------------------------------------------------------------------------------------------------------

# @dp.message(CommandStart())
# async def send_welcome(message: types.Message, state: FSMContext):
#     logger.log_command(message.chat.id, message.text)
#     user_data.add_user(message.chat.id)
#     await message.answer("Привет!"
#                          "\n"
#                          "Я твой персональный бот-таролог 🤖"
#                          "\n"
#                          "Воспользуйся кнопками ниже, чтобы взаимодействовать со мной:", reply_markup=main_kb(message.chat.id))
#     await state.clear()
#     await bot.send_message(message.chat.id, f"У вас доступно {user_data.get_user_questions(message.chat.id)} вопросов")


@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.log_command(message.chat.id, message.text)
    user_data.add_user(message.chat.id)
    if not agreement_manager.user_has_agreed(user_id):
        await message.answer("Для предоставления доступа к работе с ботом вам необходимо ознакомиться с доп. соглашением.\n\nОно расположено по ссылке:\n"
                             "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11",reply_markup=get_agreement_keyboard())

    else:
        await message.answer(
            "Привет!\nЯ твой персональный бот-таролог 🤖\n"
            "Воспользуйся кнопками ниже, чтобы взаимодействовать со мной:", reply_markup=main_kb(message.chat.id))
        await state.clear()
        await bot.send_message(message.chat.id,
                               f"У вас доступно {user_data.get_user_questions(message.chat.id)} вопросов")


@dp.callback_query(F.data.in_(["agree", "disagree"]))
async def process_agreement(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if callback.data == "agree":
        agreement_manager.add_user_agreement(user_id)
        await callback.message.answer("Спасибо за согласие! Теперь вы можете продолжить использование бота.")
        await callback.message.answer(
            "Привет!\nЯ твой персональный бот-таролог 🤖\n"
            "Воспользуйся кнопками ниже, чтобы взаимодействовать со мной:",
            reply_markup=main_kb(callback.message.chat.id))
        await state.clear()
        await callback.message.answer(
                               f"У вас доступно {user_data.get_user_questions(callback.message.chat.id)} вопросов")
    else:
        await callback.message.answer("Вы отказались от соглашения. Пожалуйста, начните снова, нажав /start.")

    await callback.answer()
#lox2.0

@dp.callback_query(lambda c: c.data in ['agree', 'disagree'])
async def process_agreement(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if callback_query.data == 'agree':
        agreement_manager.add_user_agreement(user_id)
        await callback_query.message.answer("Спасибо за согласие! Теперь вы можете продолжить использование бота.")
        await callback_query.message.answer(
            "Привет!\nЯ твой персональный бот-таролог 🤖\n"
            "Воспользуйся кнопками ниже, чтобы взаимодействовать со мной:", reply_markup=main_kb(callback_query.message.chat.id))
        await state.clear()
        await bot.send_message(callback_query.chat.id,
                               f"У вас доступно {user_data.get_user_questions(callback_query.message.chat.id)} вопросов")
    else:
        await callback_query.message.answer("Вы отказались от соглашения. Пожалуйста, начните снова, нажав /start.")


@dp.message(lambda message: message.text == '🔮✨  Задать вопрос  ✨🔮')
async def ask_question(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    subscription_end = user_data.get_subscription_end(chat_id)

    if subscription_end and datetime.now() < subscription_end:
        remaining_days = (subscription_end - datetime.now()).days
        await state.clear()
        await state.set_state(Form.question)
        await message.answer(f"Подписка активна! "
                             f"\n"
                             f"\nОсталось дней: {remaining_days}. "
                             f"\n"
                             f"\nНапишите свой вопрос: 👇")
    else:
        if subscription_end and datetime.now() > subscription_end:
            await message.answer("Ваша подписка закончилась.")

        if user_data.get_user_questions(chat_id) >= 0:
            await state.clear()
            await state.set_state(Form.question)
            await message.answer("Напишите свой вопрос для расклада: 👇")
        else:
            await bot.send_message(message.chat.id, "У вас закончились вопросы!")


@dp.message(Form.question)
async def parse_data(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    user_question = message.text
    await state.update_data({'question': user_question})

    webAppInfo = types.WebAppInfo(url=CARDS_WEBAPP_URL)
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text='Магические карты', web_app=webAppInfo))

    await state.set_state(Form.cards)
    await bot.send_message(message.chat.id, "Если хотите ввести свои карты, напишите от 3 до 6 карт через запятую!")
    await message.answer(text='Выбери карты:', reply_markup=builder.as_markup())

@dp.message(Form.cards)
async def process_question(message: types.Message, state: FSMContext):
    if message.text:
        logger.log_command(message.chat.id, message.text)
    if message.text and re.match(r'^\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*$', message.text):
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()

        user_question = data_state[
                            "question"] + 'Ответь на этот вопрос полагаясь на эти карты: ' + cardas + '. Напиши расклад по картам и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 4:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown")
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif message.text and re.match(r'^\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*$', message.text):
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()
        user_question = data_state[
                            "question"] + 'Ответь на этот вопрос полагаясь на эти карты: ' + cardas + '. Напиши расклад по картам и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 5:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown")
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif message.text and re.match(r'^\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*$', message.text):
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()
        user_question = data_state[
                            "question"] + 'Ответь на этот вопрос полагаясь на эти карты: ' + cardas + '. Напиши расклад по картам и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 6:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown")
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif message.text and re.match(r'^\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*$', message.text):
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()
        user_question = data_state[
                            "question"] + 'Ответь на этот вопрос полагаясь на эти карты: ' + cardas + '. Напиши расклад по картам и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 7:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown")
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif F.content_type == ContentType.WEB_APP_DATA:
        chat_id = message.chat.id
        data = json.loads(message.web_app_data.data)
        cards12 = data["cards"]
        cardas = await get_card_names(cards12)

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()
        question_text = data_state["question"]

        # Структурированный запрос к модели: интерпретации по порядку + summary
        card_meanings_in_order = [tarot_cards[card_path] for card_path in cards12]
        structured = await get_tarot_reading_structured(question_text, card_meanings_in_order)

        subscription_end = user_data.get_subscription_end(chat_id)

        if not (subscription_end and datetime.now() < subscription_end):
            user_data.decrement_user_questions(message.chat.id)

        await bot.delete_message(chat_id, msg.message_id)
        per_card_paragraphs = structured.get("card_interpretations") or []
        summary_paragraph = (structured.get("summary") or "").strip()

        # 1. Перечисление выпавших карт
        names_list = [tarot_cards[card_path] for card_path in cards12]
        names_text_lines = [f"{idx + 1}. {name}" for idx, name in enumerate(names_list)]
        header = "Перечисление выпавших карт:\n" + "\n".join(names_text_lines)
        await bot.send_message(chat_id, header, parse_mode="Markdown")

        # 2. Для каждой карты отправляем фото и её интерпретацию
        for idx, card_path in enumerate(cards12):
            card_name = tarot_cards[card_path]
            interp = per_card_paragraphs[idx] if idx < len(per_card_paragraphs) else ""
            caption = f"Карта {idx + 1}: {card_name}\n\n{interp}".strip()
            await photo_sender.send_photo(
                message.chat.id,
                card_path,
                caption=caption,
                parse_mode="Markdown",
            )
            await asyncio.sleep(3)

        # 3. Общий итоговый ответ (обязателен, но если модель сломалась — всё равно покажем что есть)
        if summary_paragraph:
            await bot.send_message(
                chat_id,
                f"Итоговый ответ по раскладу:\n\n{summary_paragraph}",
                parse_mode="Markdown",
            )

        # 4. Возврат в главное меню
        await bot.send_message(chat_id, "Расклад завершён. Выберите дальнейшее действие:", reply_markup=main_kb(message.chat.id))
        await state.clear()
    else: 
        await bot.send_message(message.chat.id, "Неправильный ввод. Повторите попытку")

#------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == '🔮✨  Да/Нет  ✨🔮')
async def ask_question(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    subscription_end = user_data.get_subscription_end(chat_id)

    if subscription_end and datetime.now() < subscription_end:
        remaining_days = (subscription_end - datetime.now()).days
        await state.clear()
        await state.set_state(Form2.question)
        await message.answer(f"Подписка активна! "
                             f"\n"
                             f"\nОсталось дней: {remaining_days}. "
                             f"\n"
                             f"\nНапишите свой вопрос, на который хотите узнать ответ, да или нет: 👇")
    else:
        if subscription_end and datetime.now() > subscription_end:
            await message.answer("Ваша подписка закончилась.")

        if user_data.get_user_questions(chat_id) >= 0:
            await state.clear()
            await state.set_state(Form2.question)
            await message.answer("Напишите свой вопрос, на который хотите узнать ответ, да или нет: 👇")
        else:
            await bot.send_message(message.chat.id, "У вас закончились вопросы!")


@dp.message(Form2.question)
async def parse_data(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    user_question = message.text
    await state.update_data({'question': user_question})

    webAppInfo = types.WebAppInfo(url=YESNO_WEBAPP_URL)
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text='Магические карты', web_app=webAppInfo))

    await state.set_state(Form2.cards)
    await bot.send_message(message.chat.id, "Если хотите ввести свои карту, напишите 1 карту!")
    await message.answer(text='Выбери карты:', reply_markup=builder.as_markup())

@dp.message(Form2.cards)
async def process_question(message: types.Message, state: FSMContext):
    if message.text:
        logger.log_command(message.chat.id, message.text)
    if message.text:
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()

        user_question = data_state[
                            "question"] + 'Ответь на этот вопрос да или нет, полагаясь на эту карту: ' + cardas + '. Напиши ответ да или нет по карте. Напиши текст без оформления текста и без введения.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 4:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif F.content_type == ContentType.WEB_APP_DATA:
        chat_id = message.chat.id
        data = json.loads(message.web_app_data.data)
        cards12 = data["cards"]
        cardas = await get_card_names(cards12)

        msg = await bot.send_message(chat_id, "Происходит магия...")

        data_state = await state.get_data()
        user_question = data_state[
                            "question"] + 'Ответь на этот вопрос да или нет, полагаясь на эту карту: ' + cardas + '. Напиши ответ да или нет по карте. Напиши текст без оформления текста и без введения.'
        tarot_response = await get_tarot_reading(user_question)

        subscription_end = user_data.get_subscription_end(chat_id)

        if not (subscription_end and datetime.now() < subscription_end):
            user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i == 4:
                await bot.send_message(chat_id, paragraph, reply_markup=main_kb(message.chat.id))
            else:
                await photo_sender.send_photo(message.chat.id, cards12[i-1], caption=paragraph,
                                              parse_mode="Markdown", reply_markup=main_kb(message.chat.id))
                await asyncio.sleep(3)

        await state.clear()
    else:
        await bot.send_message(message.chat.id, "Неправильный ввод. Повторите попытку")


#----------------------------------------------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == '1111')
async def make_admin(message: types.Message):
    """Команда 1111: делает пользователя админом и выдает очень много вопросов."""
    chat_id = message.chat.id
    admin_manager.add_admin(chat_id)
    user_data.set_user_questions(chat_id, 10**9)
    await message.answer(
        "Вы назначены администратором. Вам выдано практически бесконечное количество вопросов.",
        reply_markup=main_kb(chat_id),
    )

#----------------------------------------------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == '🔮✨Карта дня ✨🔮')
async def one_day_start(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    one_card.add_chat(chat_id)
    if one_card.update_date_if_needed(chat_id):
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(text='Получить карту дня', callback_data="card_day_one"))
        await message.answer("Карта дня покажет как пройдёт твой сегодняшний день!", reply_markup=builder.as_markup())
    else:
        await message.answer("Вы уже получили карту дня!")

@dp.callback_query(lambda call: call.data.startswith("card_day_"))
async def one_day_finish(call: CallbackQuery):
    logger.log_command(call.message.chat.id, call.message.text)
    chat_id = call.message.chat.id
    await call.message.delete()
    msg = await bot.send_message(chat_id, "Происходит магия...")
    selected_card = one_card.select_random_card(chat_id)
    sel_card = f"static/card{selected_card}.jpg"
    carda = tarot_cards[sel_card]
    user_question = 'Расскажи мне как пройдёт сегодняшний день по этой карте: ' + carda + '. Напиши текст без оформления текста и без введения. Только 1 абзац.'
    tarot_response = await get_tarot_reading(user_question)
    await bot.delete_message(chat_id, msg.message_id)
    await photo_sender.send_photo(chat_id, sel_card, caption=tarot_response, parse_mode="Markdown")

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == '🔮✨Чувства Мысли Действия ✨🔮')
async def ask_roman_quest(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    subscription_end = user_data.get_subscription_end(chat_id)

    if subscription_end and datetime.now() < subscription_end:
        remaining_days = (subscription_end - datetime.now()).days
        await state.clear()
        await state.set_state(romantic.quest)
        await message.answer(f"Подписка активна! "
                             f"\n"
                             f"\nОсталось дней: {remaining_days}.")
        webAppInfo = types.WebAppInfo(url=CARDS_WEBAPP_URL)
        builder = ReplyKeyboardBuilder()
        builder.add(types.KeyboardButton(text='Магические карты', web_app=webAppInfo))
        await bot.send_message(chat_id, "Чувства Мысли Действия\n\n"
                                             "В этом разделе ты сможешь узнать чувства, мысли и действия партнера.\n\n"
                                             "Все просто!\n\n" 
                                             "МЫСЛЕННО задавай вопрос 🔮\n\n"
                                             "1-я карта отвечает на вопрос: Что чувствует партнер?\n"
                                             "2-я карта показывает: О чем думает партнер?\n"
                                             "3-я карта раскрывает: Какие действия предпримет партнер?\n\n"
                                             "Если у вас есть физическая колода на руках:\n"
                                             "Введите 3 карты, которые у вас выпали через запятую 🙌\n\n"
                                             "Если у вас нет физической колоды:\n"
                                             "Нажми кнопку в меню «Выбрать карты», и  выберите 3 карты из 7 карт.")
        await message.answer(text='Выбрать карты', reply_markup=builder.as_markup())
    else:
        if subscription_end and datetime.now() > subscription_end:
            await message.answer("Ваша подписка закончилась.")

        if user_data.get_user_questions(chat_id) >= 0:
            await state.clear()
            await state.set_state(romantic.quest)
            webAppInfo = types.WebAppInfo(url=CARDS_WEBAPP_URL)
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text='Магические карты', web_app=webAppInfo))
            await bot.send_message(chat_id, "Чувства Мысли Действия\n\n"
                                            "В этом разделе ты сможешь узнать чувства, мысли и действия партнера.\n\n"
                                            "Все просто!\n\n"
                                            "МЫСЛЕННО задавай вопрос 🔮\n\n"
                                            "1-я карта отвечает на вопрос: Что чувствует партнер?\n"
                                            "2-я карта показывает: О чем думает партнер?\n"
                                            "3-я карта раскрывает: Какие действия предпримет партнер?\n\n"
                                            "Если у вас есть физическая колода на руках:\n"
                                            "Введите 3 карты, которые у вас выпали через запятую 🙌\n\n"
                                            "Если у вас нет физической колоды:\n"
                                            "Нажми кнопку в меню «Выбрать карты», и  выберите 3 карты из 7 карт.")
            await message.answer(text='Выбрать карты', reply_markup=builder.as_markup())
        else:
            await bot.send_message(message.chat.id, "У вас закончились вопросы!")

@dp.message(romantic.quest)
async def process_question(message: types.Message, state: FSMContext):
    if message.text:
        logger.log_command(message.chat.id, message.text)
    if message.text and re.match(r'^\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*$', message.text):
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        user_question = 'Ответь на эти вопросы 1-я карта отвечает на вопрос: Что чувствует партнер? 2-я карта показывает: О чем думает партнер? 3-я карта раскрывает: Какие действия предпримет партнер? полагаясь на: ' + cardas + '. Напиши расклад и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 4:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown")
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif F.content_type == ContentType.WEB_APP_DATA:
        chat_id = message.chat.id
        data = json.loads(message.web_app_data.data)
        cards12 = data["cards"]
        cardas = await get_card_names(cards12)

        msg = await bot.send_message(chat_id, "Происходит магия...")

        user_question = 'Ответь на эти вопросы. 1-я карта отвечает на вопрос: Что чувствует партнер? 2-я карта показывает: О чем думает партнер? 3-я карта раскрывает: Какие действия предпримет партнер? Полагайся на: ' + cardas + '. Напиши расклад и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'

        tarot_response = await get_tarot_reading(user_question)

        subscription_end = user_data.get_subscription_end(chat_id)

        if not (subscription_end and datetime.now() < subscription_end):
            user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i == 4:
                await bot.send_message(chat_id, paragraph, reply_markup=main_kb(message.chat.id))
            else:
                await photo_sender.send_photo(message.chat.id, cards12[i-1], caption=paragraph,
                                              parse_mode="Markdown")
                await asyncio.sleep(3)

        await state.clear()
    else:
        await bot.send_message(message.chat.id, "Неправильный ввод. Повторите попытку")

#----------------------------------------------------------------------------РЕПЛИКА-------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == '🔮✨Предупреждение от карт ✨🔮')
async def ask_roman_quest1(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    subscription_end = user_data.get_subscription_end(chat_id)

    if subscription_end and datetime.now() < subscription_end:
        remaining_days = (subscription_end - datetime.now()).days
        await state.clear()
        await state.set_state(dangerous.dan)
        await message.answer(f"Подписка активна! "
                             f"\n"
                             f"\nОсталось дней: {remaining_days}.")
        webAppInfo = types.WebAppInfo(url=CARDS_WEBAPP_URL)
        builder = ReplyKeyboardBuilder()
        builder.add(types.KeyboardButton(text='Магические карты', web_app=webAppInfo))
        await bot.send_message(chat_id, "Предупреждение от карт\n\n"
                                             "В этом разделе ты сможешь узнать предупреждение от карт.\n\n"
                                             "Все просто!\n\n" 
                                             "МЫСЛЕННО задавай вопрос 🔮\n\n"
                                             "1-я карта отвечает на вопрос: Описание ситуации?\n"
                                             "2-я карта показывает: Возможные негативные последствия?\n"
                                             "3-я карта раскрывает: Совет для нейтрализации негативных последствий?\n\n"
                                             "Если у вас есть физическая колода на руках:\n"
                                             "Введите 3 карты, которые у вас выпали через запятую 🙌\n\n"
                                             "Если у вас нет физической колоды:\n"
                                             "Нажми кнопку в меню «Выбрать карты», и  выберите 3 карты из 7 карт.")
        await message.answer(text='Выбрать карты', reply_markup=builder.as_markup())
    else:
        if subscription_end and datetime.now() > subscription_end:
            await message.answer("Ваша подписка закончилась.")

        if user_data.get_user_questions(chat_id) >= 0:
            await state.clear()
            await state.set_state(dangerous.dan)
            webAppInfo = types.WebAppInfo(url=CARDS_WEBAPP_URL)
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text='Магические карты', web_app=webAppInfo))
            await bot.send_message(chat_id, "Предупреждение от карт\n\n"
                                            "В этом разделе ты сможешь узнать предупреждение от карт.\n\n"
                                            "Все просто!\n\n"
                                            "МЫСЛЕННО задавай вопрос 🔮\n\n"
                                            "1-я карта отвечает на вопрос: Описание ситуации?\n"
                                            "2-я карта показывает: Возможные негативные последствия?\n"
                                            "3-я карта раскрывает: Совет для нейтрализации негативных последствий?\n\n"
                                            "Если у вас есть физическая колода на руках:\n"
                                            "Введите 3 карты, которые у вас выпали через запятую 🙌\n\n"
                                            "Если у вас нет физической колоды:\n"
                                            "Нажми кнопку в меню «Выбрать карты», и  выберите 3 карты из 7 карт.")
            await message.answer(text='Выбрать карты', reply_markup=builder.as_markup())
        else:
            await bot.send_message(message.chat.id, "У вас закончились вопросы!")

@dp.message(dangerous.dan)
async def process_question(message: types.Message, state: FSMContext):
    if message.text:
        logger.log_command(message.chat.id, message.text)
    if message.text and re.match(r'^\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*$', message.text):
        chat_id = message.chat.id

        cardas = message.text

        msg = await bot.send_message(chat_id, "Происходит магия...")

        user_question = 'Ответь на эти вопросы 1-я карта отвечает на вопрос: Описание ситуации? 2-я карта показывает: Возможные негативные последствия ? 3-я карта раскрывает: Совет для нейтрализации негативных последствий? полагаясь на: ' + cardas + '. Напиши расклад и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'
        tarot_response = await get_tarot_reading(user_question)
        user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i != 4:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown")
                await asyncio.sleep(3)
            else:
                await bot.send_message(message.chat.id, f"{paragraph}", parse_mode="Markdown", reply_markup=main_kb(message.chat.id))

        await state.clear()
    elif F.content_type == ContentType.WEB_APP_DATA:
        chat_id = message.chat.id
        data = json.loads(message.web_app_data.data)
        cards12 = data["cards"]
        cardas = await get_card_names(cards12)

        msg = await bot.send_message(chat_id, "Происходит магия...")

        user_question = 'Ответь на эти вопросы 1-я карта отвечает на вопрос: Описание ситуации? 2-я карта показывает: Возможные негативные последствия ? 3-я карта раскрывает: Совет для нейтрализации негативных последствий? полагаясь на: ' + cardas + '. Напиши расклад и общий расклад. Напиши текст без оформления текста и без введения. Опиши каждую карту и в конце общий расклад, всё по абзацам.'

        tarot_response = await get_tarot_reading(user_question)

        subscription_end = user_data.get_subscription_end(chat_id)

        if not (subscription_end and datetime.now() < subscription_end):
            user_data.decrement_user_questions(message.chat.id)

        paragraphs = split_text_into_paragraphs(tarot_response)
        await bot.delete_message(chat_id, msg.message_id)
        for i, paragraph in enumerate(paragraphs):
            i += 1
            if i == 4:
                await bot.send_message(chat_id, paragraph, reply_markup=main_kb(message.chat.id))
            else:
                await photo_sender.send_photo(message.chat.id, cards12[i-1], caption=paragraph,
                                              parse_mode="Markdown")
                await asyncio.sleep(3)

        await state.clear()
    else:
        await bot.send_message(message.chat.id, "Неправильный ввод. Повторите попытку")

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == 'Индивидуальная консультация')
async def solo_reading(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    await message.answer("Заказать индивидуальную консультацию с таро, астрологией, дизайном человека: @RoxanaAmetist")


@dp.message(lambda message: message.text == 'Ежедневные бесплатные прогнозы')
async def cards(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    await message.answer("Подпишись для бесплатных ежедневных прогнозов на день: "
                         "\n"
                         "\n"
                         "https://t.me/follow_the_frensy")


@dp.message(lambda message: message.text == 'Как работает бот')
async def how_it_works(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    await message.answer("Как пользоваться ботом ⬇️\n\n"
                         "• Нажми на кнопку «Задать вопрос». \n"
                         "• Напиши свой вопрос для расклада и отправь боту. \n"
                         "• Сделай расклад и выпавшие карты введи в бота (карты вводи через запятую).\n"
                         "• А теперь жди трактовку расклада. \n\n"
                         "С ❤️, ваш персональный бот от гадалочки-Роксаночки"
                         "\n"
                         "\n"
                         "Ссылка на видео инструкцию по использованию бота:"
                         "\n"
                         "\n"
                         "https://www.youtube.com/shorts/FPpt3rNHXck?si=xGoInzxR6y_OQFky")


@dp.message(lambda message: message.text == 'Техподдержка')
async def support(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    await message.answer("Если у вас возникли проблемы с ботом, нажмите /start. "
                         "\n"
                         "Если бот так и не заработал в течение 10-15 минут, обратитесь в тех. поддержку @Roxana_Ametist_bot")


@dp.message(Command('agreement'))
async def show_agreement(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    await message.answer("Ознакомиться с доп. соглашением можно по ссылке:\n"
                         "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11")



#-----------------------------------------------------------------------------------------------------------------------


YOOTOKEN = os.getenv("YOOTOKEN")

@dp.message(lambda message: message.text == 'Оформить подписку')
async def oplata(message: Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    email = user_data.get_user_email(chat_id)
    if email:
        await message.answer("Выбери актуальную подписку для себя:", reply_markup=sub())
    else:
        await message.answer("Для того чтобы оформить подписку необходимо ввести почту. "
                             "\n"
                             "\n"
                             "Введите почту.")

        await state.set_state(Email.email_check)

@dp.message(Email.email_check)
async def email_box(message: Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    email_notvalid = message.text
    try:
        user_data.set_user_email(chat_id, email_notvalid)
        await message.answer("Email установлен. Выберите подписку.", reply_markup=sub())
        await state.clear()
    except ValueError:
        await state.clear()
        await state.set_state(Email.email_check)
        await message.answer("Email не установлен. Введите корректный email.")


def sub():
    sub1 = types.InlineKeyboardButton(text='10 запросов - 169 руб.', callback_data="sub_10_169")
    #sub2 = types.InlineKeyboardButton(text='30 запросов - 339 руб.', callback_data="sub_30_339")
    sub3 = types.InlineKeyboardButton(text='Месяц (безлимит) - 359 руб.', callback_data="sub_7d_399") #меняю
    sub4 = types.InlineKeyboardButton(text='3 Месяца (безлимит) - 999 руб.', callback_data="sub_14d_499")
    sub5 = types.InlineKeyboardButton(text='Год (безлимит) - 2999 руб.', callback_data="sub_30d_699")

    markup = InlineKeyboardBuilder()
    markup.row(sub1)
    #markup.row(sub2)
    markup.row(sub3)
    markup.row(sub4)
    markup.row(sub5)

    return markup.as_markup()

@dp.callback_query(lambda call: call.data.startswith("sub_"))
async def submonth(call: CallbackQuery):
    logger.log_command(call.message.chat.id, call.message.text)
    message = call.message
    chat_id = message.chat.id
    prices = {
        "sub_10_169": 16900,
        #"sub_30_339": 33900,
        "sub_7d_399": 35900,
        "sub_14d_499": 99900,
        "sub_30d_699": 299900,
    }
    selected_price = prices.get(call.data, 15000)
    await call.message.delete()

    idempotence_key = str(uuid.uuid4())

    Configuration.account_id = int(os.getenv("YOOKASSA_ACCOUNT_ID"))

    Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

    email = user_data.get_user_email(chat_id)

    order_manager.increment_order_number()

    idempotence_key = str(uuid.uuid4())
    payment = Payment.create({
        "amount": {
            "value": f"{int(selected_price / 100)}.00",
            "currency": "RUB"
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/Roxanaametist_Taro_bot"
        },
        "description": "Оплата подписки",
        "metadata": {
            "order_id": f"{order_manager.get_order_number()}"
        },
        "receipt": {
            "customer": {
                "email": f"{email}"
            },
            "items": [
                {
                    "description": "Подписка",
                    "quantity": 1,
                    "amount": {
                        "value": f"{int(selected_price / 100)}.00",
                        "currency": "RUB"
                    },
                    "vat_code": 1
                }
            ]
        }
    }, idempotence_key)

    confirmation_url = payment.confirmation.confirmation_url
    await bot.send_message(chat_id=message.chat.id, text="Ссылка на оплату подписки: "
                                                         f"\n {confirmation_url}")
    payment_id = payment.id

    await check_payment_status(payment_id, message.chat.id, selected_price)

async def check_payment_status(payment_id, chat_id, selected_price):
    for _ in range(60):
        zakaz = Payment.find_one(payment_id)


# 33900: "30",


        if zakaz.status == "succeeded":
            inv_pay = selected_price
            prices = {16900: "10", 35900: "31d", 99900: "93d", 299900: "365d"}
            selected_type = prices.get(inv_pay)


#elif selected_type == "30":
    #user_data.increment_user_questions(chat_id, 30)


            if selected_type == "10":
                user_data.increment_user_questions(chat_id, 10)
            elif selected_type == "31d":
                user_data.extend_subscription(chat_id, days=31)
            elif selected_type == "93d":
                user_data.extend_subscription(chat_id, days=93)
            elif selected_type == "365d":
                user_data.extend_subscription(chat_id, days=365)

            update_payment_data(inv_pay, selected_type)
            await bot.send_message(chat_id, f"Вам выдана подписка!", reply_markup=main_kb(chat_id))
            return

        elif zakaz.status == "canceled":
            await bot.send_message(chat_id, "Оплата отменена.")
            return
        await asyncio.sleep(10)

    await bot.send_message(chat_id, "Платеж не был завершен или отменен. Проверьте статус на сайте.")


@dp.pre_checkout_query(F.invoice_payload == "demo")
async def process_pre_checkout_query(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(Command("denginam"))
async def show_payment_data(message: types.Message):
    try:
        with open(PAYMENT_FILE, "r") as file:
            data = json.load(file)

        total_amount = data["total_amount"]
        subscriptions = data["subscriptions"]

        response = f"<b>Статистика платежей:</b>\n"
        response += f"<b>Общая сумма оплат:</b> {total_amount / 100:.2f} RUB\n"
        response += "<b>Подписки:</b>\n"
        for sub_type, count in subscriptions.items():
            response += f"- {sub_type}: {count} шт.\n"

        await message.reply(response, parse_mode=ParseMode.HTML)

    except FileNotFoundError:
        await message.reply("Данные о платежах отсутствуют.")




@dp.message(F.successful_payment)
async def process_payment(message):
    chat_id = message.from_user.id
    inv_pay = message.successful_payment.total_amount


@dp.message(Command("statistika123"))
async def show_statistika(message: types.Message):
    filt_ids = user_data.get_filtered_user_ids([531235523])
    gwr = 0
    for pid_id in filt_ids:
        gwr += 1
    await bot.send_message(message.chat.id, f"Количество пользователей: {gwr}")

@dp.message(Command("stats_by_date123"))
async def get_stats_by_date(message: types.Message):
    #Формат YYYY-MM-DD
    date = message.text.split()[-1]
    date_stats = logger.get_date_stats(date)

    if date_stats:
        response = f"Команды за {date}:\n"
        for log in date_stats:
            response += f"Пользователь {log['user_id']}: {log['command']} в {log['date']}\n"
    else:
        response = f"На {date} команд не найдено."

    await message.reply(response)

@dp.message(Command("stats_by_command123"))
async def get_command_stats(message: types.Message):
    command = message.text.split()[-1]
    command_stats = logger.get_command_stats(command)

    if command_stats:
        response = f"Статистика по команде {command}:\n"
        for log in command_stats:
            response += f"Пользователь {log['user_id']} использовал команду в {log['date']}\n"
    else:
        response = f"Команда {command} не найдена в логах."

    await message.reply(response)

@dp.message(Command("stats123"))
async def get_stats(message: types.Message):
    user_id = int(message.text.split()[-1])
    user_stats = logger.get_user_stats(user_id)

    if user_stats:
        response = f"Команды пользователя под id: {user_id}\n"
        for log in user_stats:
            response += f"{log['command']} в {log['date']}\n"
    else:
        response = "Пользователь не найден или не пользовался ботом."

    await message.reply(response)

@dp.message(Command("new_users_today123"))
async def get_new_users_today(message: types.Message):
    """
    Обработчик команды /new_users_today123.
    Возвращает количество новых пользователей за сегодня.
    """
    new_users_count = logger.get_new_users_today()
    await message.reply(f"Количество новых пользователей за сегодня: {new_users_count}")

@dp.message(Command("total_users123"))
async def get_total_users(message: types.Message):
    """
    Обработчик команды /total_users123.
    Возвращает общее количество уникальных пользователей бота.
    """
    total_users_count = logger.get_total_users()
    await message.reply(f"Общее количество пользователей бота: {total_users_count}")

@dp.message(Command("stats_last_x_days123"))
async def get_stats_last_x_days(message: types.Message):
    """
    Обработчик команды /stats_last_x_days123.
    Возвращает статистику за последние X дней.
    """
    try:
        x = int(message.text.split()[-1])
        if x <= 0:
            await message.reply("Число дней должно быть положительным.")
            return

        stats = logger.get_stats_last_x_days(x)

        if stats:
            response = f"Статистика за последние {x} дней:\n"
            for log in stats:
                response += f"Пользователь {log['user_id']} выполнил команду '{log['command']}' в {log['date']}\n"
        else:
            response = "За указанный период данных нет."

        await message.reply(response)
    except (IndexError, ValueError):
        await message.reply("Используйте команду в формате: /stats_last_x_days X (где X — число дней).")

@dp.message(Command("stats_date123"))
async def get_stats(message: types.Message):
    date_arg = message.text.split()[-1]

    if not date_arg:
        await message.answer("Пожалуйста, укажите дату в формате YYYY-MM-DD.")
        return
    try:
        input_date = datetime.strptime(date_arg, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        await message.answer("Неверный формат даты. Используйте формат YYYY-MM-DD.")
        return

    date_logs = logger.get_date_stats(date_arg)
    command_counts = {}

    for log in date_logs:
        command = log["command"]
        if command in command_counts:
            command_counts[command] += 1
        else:
            command_counts[command] = 1

    priority_commands = [
        '/start',
        '🔮✨  Задать вопрос  ✨🔮',
        '🔮✨Карта дня ✨🔮',
        '🔮✨Чувства Мысли Действия ✨🔮',
        '🔮✨Предупреждение от карт ✨🔮',
        'Получить дополнительные расклады!',
        'Индивидуальная консультация',
        'Как работает бот',
        'Техподдержка',
        'Оформить подписку',
        'Промокод',
        'Сообщение пользователям',
        'Назад'
    ]

    stats_message = f"Дата: {datetime.strptime(input_date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n\n"

    # Добавляем приоритетные команды
    for command in priority_commands:
        if command in command_counts:
            stats_message += f"*Команда:* {command} - *{command_counts[command]}* раз\n"
            del command_counts[command]
    stats_message += "\n"

    # Добавляем оставшиеся команды
    for command, count in command_counts.items():
        stats_message += f"*Команда:* {command} - *{count}* раз\n"

    # Разбиваем сообщение на части, чтобы каждая часть не превышала 4096 символов
    max_length = 4096
    messages = []
    current_message = ""

    # Разделяем текст по строкам
    for line in stats_message.split("\n"):
        # Если добавление новой строки не превышает лимит, добавляем её в текущее сообщение
        if len(current_message) + len(line) + 1 <= max_length:  # +1 для символа новой строки
            current_message += line + "\n"
        else:
            # Если превышает, сохраняем текущее сообщение и начинаем новое
            messages.append(current_message.strip())
            current_message = line + "\n"

    # Добавляем последнее сообщение, если оно не пустое
    if current_message.strip():
        messages.append(current_message.strip())

    # Отправляем все части сообщения
    for msg in messages:
        await message.answer(msg, parse_mode='Markdown')

@dp.message(Command("popolnit_na123"))
async def get_pulled(message: types.Message):
    count1 = int(message.text.split()[-1])
    filtered_ids = user_data.get_filtered_user_ids([343465637])
    for pid_chat_id in filtered_ids:
        if isinstance(await bot.get_chat_member(channel_id, pid_chat_id), ChatMemberMember) or isinstance(
                await bot.get_chat_member(channel_id, pid_chat_id), ChatMemberOwner):
            await bot.send_message(pid_chat_id, f"Вам добавились {count1} ежемесячных вопросов!")
            user_data.increment_user_questions(pid_chat_id, count1)

#-----------------------------------------------------Промокоды---------------------------------------------------------
# Словарь для хранения использованных промокодов
used_promocodes = {}

# Список допустимых промокодов
valid_promocodes = [
    'jzqtp', 'dxvwm', 'qbzsn', 'ykzjr', 'sodxe',
    'xgzkn', 'bwvth', 'tcufm', 'vhgqd', 'vmqzi',
    'plbkn', 'fgceu', 'wzpsd', 'gjkty', 'eqhqt',
    'lpluo', 'rzxwa', 'xovyd', 'tdcwm', 'qnnzu',
    'avwie', 'zwtlj', 'yhrme', 'ucxmf', 'kejan',
    'hivro', 'gqowi', 'xzahn', 'zfqtm', 'fqujd',
    'wdeki', 'xvupe', 'jpxzc', 'kvqbf', 'idgzb',
    'qflmr', 'tehdg', 'zwcnj', 'bsuoy', 'pxfpt',
    'orkmg', 'drtsn', 'hsyue', 'xlqkr', 'jzylb',
    'pzjxr', 'vmqwz', 'tsoek', 'wyzuh', 'smzoh',
    'gknvy', 'pdxlm', 'cbbif', 'doqpc', 'hqunw',
    'qfvsj', 'tqbpi', 'zslkw', 'ifuaw', 'zmduu',
    'fwclz', 'ehqrv', 'vhuhc', 'cfyir', 'tvoqz',
    'ceshg', 'llrwa', 'bsmpe', 'dpehr', 'qzvnf',
    'ajktv', 'rfmrq', 'uwkfy', 'ikzdt', 'idleu',
    'vycwq', 'ymgpr', 'bjyoq', 'dmdhe', 'wznmb',
    'fcvop', 'sifwz', 'ximbm', 'znmes', 'myvsd',
    'pnqdr', 'uaflz', 'ybtlk', 'cxxkr', 'ftxrj'
]

@dp.message(lambda message: message.text == 'Промокод')
async def promos(message: types.Message, state: FSMContext ):
    logger.log_command(message.chat.id, message.text)
    await state.set_state(Promo.prikol)
    await message.answer("Если у вас есть промокод, то введите его")


@dp.message(Promo.prikol)
async def apply_promocode(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    await state.clear()
    if message.text in valid_promocodes:
        # Проверяем, использовал ли пользователь промокод ранее
        if chat_id in used_promocodes and message.text in used_promocodes[chat_id]:
            await message.answer("Вы уже использовали этот промокод. Пожалуйста, попробуйте другой. ⚠️")
        else:
            # Начисляем вопросы и сохраняем информацию об использовании промокода
            user_data.increment_user_questions(chat_id, 1000)

            # Добавляем использованный промокод в список
            if chat_id not in used_promocodes:
                used_promocodes[chat_id] = []
            used_promocodes[chat_id].append(message.text)

            await message.answer("Промокод активирован! Вам начислено 100 вопросов 🎉")
    else:
        await message.answer("Некорректный промокод. Пожалуйста, попробуйте еще раз ⚠️")



#---------------------------------------------------------------------------------------------------------------------------------


def main_kb(chat_id):
    builder = ReplyKeyboardBuilder()
    button_dop_question = types.KeyboardButton(text='Получить дополнительные расклады!')
    button_ask_question = types.KeyboardButton(text='🔮✨  Задать вопрос  ✨🔮')
    button_day_one = types.KeyboardButton(text='🔮✨Карта дня ✨🔮')
    button_romantic = types.KeyboardButton(text='🔮✨Чувства Мысли Действия ✨🔮')
    button_yesno = types.KeyboardButton(text='🔮✨  Да/Нет  ✨🔮')
    button_pred = types.KeyboardButton(text='🔮✨Предупреждение от карт ✨🔮')
    button_solo_reading = types.KeyboardButton(text='Индивидуальная консультация')
    button_how_it_works = types.KeyboardButton(text='Как работает бот')
    button_support = types.KeyboardButton(text='Техподдержка')
    #button_cards = types.KeyboardButton(text='Ежедневные бесплатные прогнозы')
    button_oplata = types.KeyboardButton(text='Оформить подписку')
    button_promo = types.KeyboardButton(text='Промокод')
    button_send_messages = types.KeyboardButton(text='Сообщение пользователям')
    builder.row(button_ask_question)
    builder.row(button_day_one, button_yesno)
    builder.row(button_romantic)
    builder.row(button_pred)
    builder.row(button_solo_reading, button_oplata)
    builder.row(button_support, button_how_it_works)
    #демид так и должно быть все ок builder.row(button_cards)
    builder.row(button_promo)
    builder.row(button_dop_question)
    # Статичные админы + динамические из AdminManager
    static_admins = {491482483, 365515529, 664376580}
    if (chat_id in static_admins) or admin_manager.is_admin(chat_id):
        builder.row(button_send_messages)
    return builder.as_markup(resize_keyboard=True)

def back_kb():
    builder = ReplyKeyboardBuilder()
    button_back = types.KeyboardButton(text='Назад')
    builder.row(button_back)
    return builder.as_markup(resize_keyboard=True)
    #lox

#-------------------------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == 'Назад')
async def check_sub(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    await state.clear()
    chat_id = message.chat.id
    await bot.send_message(chat_id, "Вернулись в главное меню", reply_markup=main_kb(message.chat.id))

#---------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == 'Сообщение пользователям')
async def check_sub(message: types.Message, state: FSMContext):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    static_admins = {491482483, 365515529, 664376580}
    if not ((chat_id in static_admins) or admin_manager.is_admin(chat_id)):
        return
    await state.clear()
    await state.set_state(Mess_check.message_id)
    await bot.send_message(
        chat_id,
        "Отправьте сообщение для рассылки.\n\n"
        "Можно отправить:\n"
        "- текст\n"
        "- текст со ссылкой\n"
        "- фото с подписью\n\n"
        "Бот разошлёт это сообщение всем пользователям.",
        reply_markup=back_kb(),
    )

@dp.message(Mess_check.message_id)
async def parse_message(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    logger.log_command(chat_id, message.text or "<non-text message>")
    static_admins = {491482483, 365515529, 664376580}
    if not ((chat_id in static_admins) or admin_manager.is_admin(chat_id)):
        await state.clear()
        return
    await state.clear()
    filtered_ids = user_data.get_filtered_user_ids([chat_id])
    sent = 0
    failed = 0
    for pid_chat_id in filtered_ids:
        try:
            # copy_message сохраняет и текст, и ссылки (entities), и фото/видео/документы/подписи
            await bot.copy_message(
                chat_id=pid_chat_id,
                from_chat_id=chat_id,
                message_id=message.message_id,
            )
            sent += 1
        except Exception:
            failed += 1
    await bot.send_message(
        chat_id,
        f"Рассылка завершена.\nОтправлено: {sent}\nНе доставлено: {failed}",
        reply_markup=main_kb(message.chat.id),
    )

#----------------------------------------------------------------------------------------------------------------------------------

@dp.message(lambda message: message.text == 'Получить дополнительные расклады!')
async def check_sub(message: types.Message):
    logger.log_command(message.chat.id, message.text)
    chat_id = message.chat.id
    await bot.send_message(message.chat.id, f"Текущий баланс:{user_data.get_user_questions(message.chat.id)}")
    try:
        if isinstance(await bot.get_chat_member(channel_id, chat_id), ChatMemberMember) or isinstance(await bot.get_chat_member(channel_id, chat_id), ChatMemberOwner):
            if status_data.is_status_zero(chat_id):
                status_data.toggle_status(chat_id)
                user_data.increment_user_questions(chat_id, 15)
                await bot.send_message(chat_id, "Вы подписались на канал! Вам добавлено 15 вопросов.\n"
                                                "\n"
                                                "Следующее пополнение вашего аккаунта на 15 раскладов 1 числа следующего месяца.")
            else:
                await bot.send_message(chat_id, "Вопросы уже добавлены.\n"
                                                "\n"
                                                "Следующее пополнение вашего аккаунта на 15 раскладов 1 числа следующего месяца.")
        else:
            await bot.send_message(chat_id,
                                   "Вы не подписаны на канал! Вот ссылка на канал: https://t.me/follow_the_frensy")
    except:
        await bot.send_message(chat_id, "Ошибка. Обратитесь в техподдержку")

#-------------------------------------------------------------------------------------------------------------------------

async def main():

    # Арканы (1-22)
    arcana_names = [
        "Дурак", "Маг", "Верховная Жрица", "Императрица", "Император", "Верховная жрица",
        "Влюбленные", "Колесница", "Сила", "Отшельник", "Колесо Фортуны",
        "Правосудие", "Повешенный", "Смерть", "Умеренность", "Дьявол",
        "Башня", "Звезда", "Луна", "Солнце", "Суд", "Мир"
    ]
    for i, name in enumerate(arcana_names, start=1):
        tarot_cards[f"static/card{i}.jpg"] = name

    # Жезлы (23-36)
    wands_names = [
        "Туз Жезлов", "Двойка Жезлов", "Тройка Жезлов", "Четверка Жезлов", "Пятерка Жезлов",
        "Шестерка Жезлов", "Семерка Жезлов", "Восьмерка Жезлов", "Девятка Жезлов", "Десятка Жезлов",
        "Паж Жезлов", "Королева Жезлов", "Рыцарь Жезлов", "Король Жезлов"
    ]
    for i, name in enumerate(wands_names, start=23):
        tarot_cards[f"static/card{i}.jpg"] = name

    # Кубки (37 - 50)
    cups_names = [
        "Туз Кубков", "Двойка Кубков", "Тройка Кубков", "Четверка Кубков", "Пятерка Кубков",
        "Шестерка Кубков", "Семерка Кубков", "Восьмерка Кубков", "Девятка Кубков", "Десятка Кубков",
        "Паж Кубков", "Королева Кубков", "Рыцарь Кубков", "Король Кубков"
    ]
    for i, name in enumerate(cups_names, start=37):
        tarot_cards[f"static/card{i}.jpg"] = name

    # Мечи (51 - 64)
    swords_names = [
        "Туз Мечей", "Двойка Мечей", "Тройка Мечей", "Четверка Мечей", "Пятерка Мечей",
        "Шестерка Мечей", "Семерка Мечей", "Восьмерка Мечей", "Девятка Мечей", "Десятка Мечей",
        "Паж Мечей", "Королева Мечей", "Рыцарь Мечей", "Король Мечей"
    ]
    for i, name in enumerate(swords_names, start=51):
        tarot_cards[f"static/card{i}.jpg"] = name

    # Пентакли (65-78)
    pentacles_names = [
        "Туз Пентаклей", "Двойка Пентаклей", "Тройка Пентаклей", "Четверка Пентаклей", "Пятерка Пентаклей",
        "Шестерка Пентаклей", "Семерка Пентаклей", "Восьмерка Пентаклей", "Девятка Пентаклей", "Десятка Пентаклей",
        "Паж Пентаклей", "Королева Пентаклей", "Рыцарь Пентаклей", "Король Пентаклей"
    ]
    for i, name in enumerate(pentacles_names, start=65):
        tarot_cards[f"static/card{i}.jpg"] = name

    initialize_payment_file()
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем фоновые задачи до polling, иначе код ниже никогда не выполнится
    asyncio.create_task(pidor_doma())
    asyncio.create_task(periodic_30day_refill())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
