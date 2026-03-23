import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

from aiogram import Bot


def load_env_file(path: str = ".env") -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def parse_user_line(line: str) -> Optional[Tuple[int, str, str, str, str]]:
    raw = line.strip()
    if not raw or raw.startswith("User_ID"):
        return None

    # Формат: User_ID,Username,First_Name,Last_Name,Phone
    # Берем максимум 5 частей, чтобы не "ломать" строку при лишних запятых.
    parts = [p.strip() for p in raw.split(",", 4)]
    while len(parts) < 5:
        parts.append("")

    user_id_raw = parts[0]
    if not user_id_raw.isdigit():
        return None

    user_id = int(user_id_raw)
    username = parts[1]
    first_name = parts[2]
    last_name = parts[3]
    phone = parts[4]
    return user_id, username, first_name, last_name, phone


async def bot_can_access_user(bot: Bot, user_id: int) -> bool:
    try:
        await bot.get_chat(user_id)
        return True
    except Exception:
        return False


def load_user_data(path: str) -> Dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_data(path: str, data: Dict[str, dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def run(
    source_path: str,
    user_data_path: str,
    token: str,
    dry_run: bool,
    check_bot_access: bool,
) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = load_user_data(user_data_path)

    total_rows = 0
    invalid_rows = 0
    already_exists = 0
    skipped_no_access = 0
    added = 0

    bot = Bot(token=token)
    try:
        with open(source_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_user_line(line)
                if parsed is None:
                    continue

                total_rows += 1
                user_id, username, first_name, last_name, phone = parsed
                key = str(user_id)

                if key in data:
                    already_exists += 1
                    continue

                if check_bot_access:
                    ok = await bot_can_access_user(bot, user_id)
                    if not ok:
                        skipped_no_access += 1
                        continue

                data[key] = {
                    "questions": 5,
                    "subscription_end": None,
                    "email": None,
                    "last_refill_at": now_str,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "imported_from_user_txt": True,
                }
                added += 1
    except FileNotFoundError:
        print(f"Файл не найден: {source_path}")
        return
    except Exception as e:
        print(f"Ошибка чтения {source_path}: {e}")
        return
    finally:
        await bot.session.close()

    if not dry_run:
        save_user_data(user_data_path, data)

    print("Импорт завершен.")
    print(f"Всего валидных строк: {total_rows}")
    print(f"Некорректных строк: {invalid_rows}")
    print(f"Уже были в базе: {already_exists}")
    print(f"Пропущены (бот не видит пользователя): {skipped_no_access}")
    print(f"Добавлено: {added}")
    print(f"Режим dry-run: {'да' if dry_run else 'нет'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Импорт пользователей из user.txt в user_data.json"
    )
    parser.add_argument("--source", default="user.txt", help="Путь к user.txt")
    parser.add_argument(
        "--db", default="user_data.json", help="Путь к user_data.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать статистику, не записывать файл",
    )
    parser.add_argument(
        "--no-bot-check",
        action="store_true",
        help="Не проверять через Telegram API доступность пользователя для бота",
    )
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        env_map = load_env_file(".env")
        token = env_map.get("TELEGRAM_TOKEN")

    if not token:
        print("Не найден TELEGRAM_TOKEN (ни в env, ни в .env).")
        return

    asyncio.run(
        run(
            source_path=args.source,
            user_data_path=args.db,
            token=token,
            dry_run=args.dry_run,
            check_bot_access=not args.no_bot_check,
        )
    )


if __name__ == "__main__":
    main()
