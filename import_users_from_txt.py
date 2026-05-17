import argparse
import asyncio
import json
import os
import random
import re
from datetime import datetime, timedelta
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


async def resolve_user_by_username(bot: Bot, username: str) -> Optional[int]:
    try:
        chat = await bot.get_chat(username)
        return int(chat.id)
    except Exception:
        return None


def load_user_data(path: str) -> Dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_data(path: str, data: Dict[str, dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_retry_after_seconds(exc: Exception) -> Optional[int]:
    """Достаёт секунды ожидания из ошибки Telegram FloodWait."""
    text = str(exc).lower()
    m = re.search(r"retry after[:\s]+(\d+)", text)
    if m:
        return int(m.group(1))
    for t in text.replace(",", " ").split():
        if t.isdigit():
            val = int(t)
            if val > 0:
                return val
    return None


def save_progress(
    progress_path: str,
    next_index: int,
    total: int,
    extra: Optional[dict] = None,
) -> None:
    payload = {
        "next_index": next_index,
        "total": total,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if extra:
        payload.update(extra)
    with open(progress_path, "w", encoding="utf-8") as pf:
        json.dump(payload, pf, ensure_ascii=False, indent=2)


def normalize_username(raw: str) -> Optional[str]:
    v = (raw or "").strip()
    if not v:
        return None
    if not v.startswith("@"):
        v = "@" + v
    # Telegram username: 5-32 символа после @, латиница/цифры/_
    body = v[1:]
    if len(body) < 5 or len(body) > 32:
        return None
    if not all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in body):
        return None
    return "@" + body.lower()


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


async def run_usernames(
    source_path: str,
    user_data_path: str,
    token: str,
    dry_run: bool,
    delay_min: float,
    delay_max: float,
    batch_size: int,
    pause_seconds: float,
    progress_path: str,
    max_flood_wait: int,
    max_consecutive_not_found: int,
) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = load_user_data(user_data_path)
    started_at = datetime.now()

    usernames: list[str] = []
    try:
        with open(source_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                u = normalize_username(line)
                if u:
                    usernames.append(u)
    except FileNotFoundError:
        print(f"Файл не найден: {source_path}")
        return

    # Дедуп по порядку
    seen = set()
    uniq_usernames = []
    for u in usernames:
        if u not in seen:
            seen.add(u)
            uniq_usernames.append(u)

    # Прогресс: индекс последней обработанной строки
    start_idx = 0
    if os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as pf:
                p = json.load(pf)
                start_idx = int(p.get("next_index", 0))
                resume_after = p.get("resume_after")
                if p.get("aborted_by_flood") and resume_after:
                    try:
                        ra = datetime.strptime(resume_after, "%Y-%m-%d %H:%M:%S")
                        if datetime.now() < ra:
                            wait_min = int((ra - datetime.now()).total_seconds() // 60) + 1
                            print(
                                f"Импорт приостановлен из-за FloodWait. "
                                f"Подождите ещё ~{wait_min} мин (до {resume_after}) и запустите снова.",
                                flush=True,
                            )
                            return
                    except ValueError:
                        pass
        except Exception:
            start_idx = 0

    total = len(uniq_usernames)
    if start_idx >= total:
        print("Все ники уже обработаны по progress-файлу.")
        return

    print(
        f"Старт проверки ников: всего={total}, стартовый индекс={start_idx}, dry-run={'да' if dry_run else 'нет'}",
        flush=True,
    )
    print(
        f"Лимит FloodWait: если больше {max_flood_wait} сек — скрипт остановится и сохранит прогресс.",
        flush=True,
    )

    checked = 0
    added = 0
    already_exists = 0
    not_found = 0
    aborted_by_flood = False
    stopped_low_yield = False
    progress_saved = False
    resume_index = start_idx
    consecutive_not_found = 0
    flood_wait_secs = 0

    bot = Bot(token=token)
    try:
        for idx in range(start_idx, total):
            resume_index = idx
            username = uniq_usernames[idx]
            checked += 1
            found_user_id: Optional[int] = None

            async def fetch_user_id() -> Optional[int]:
                chat = await bot.get_chat(username)
                return int(chat.id)

            try:
                found_user_id = await fetch_user_id()
            except Exception as e:
                secs = parse_retry_after_seconds(e)
                if secs is not None:
                    flood_wait_secs = secs
                    if secs > max_flood_wait:
                        resume_at = (datetime.now() + timedelta(seconds=secs + 60)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        print(
                            (
                                f"[{idx + 1}/{total}] FloodWait {secs} сек ({secs // 3600} ч) "
                                f"для {username}. Останавливаю импорт (лимит {max_flood_wait} сек)."
                            ),
                            flush=True,
                        )
                        print(f"Продолжить можно после: {resume_at}", flush=True)
                        if not dry_run:
                            save_user_data(user_data_path, data)
                        save_progress(
                            progress_path,
                            idx,
                            total,
                            {
                                "aborted_by_flood": True,
                                "flood_wait_seconds": secs,
                                "resume_after": resume_at,
                                "stats": {
                                    "checked": checked,
                                    "added": added,
                                    "exists": already_exists,
                                    "not_found": not_found,
                                },
                            },
                        )
                        aborted_by_flood = True
                        progress_saved = True
                        break

                    wait_for = min(secs + 2, max_flood_wait)
                    print(
                        f"[{idx + 1}/{total}] FloodWait {secs} сек, жду {wait_for} сек и повторяю...",
                        flush=True,
                    )
                    await asyncio.sleep(wait_for)
                    try:
                        found_user_id = await fetch_user_id()
                    except Exception as retry_err:
                        retry_secs = parse_retry_after_seconds(retry_err)
                        if retry_secs is not None and retry_secs > max_flood_wait:
                            resume_at = (datetime.now() + timedelta(seconds=retry_secs + 60)).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            print(
                                f"[{idx + 1}/{total}] Повторный FloodWait {retry_secs} сек. Останавливаю.",
                                flush=True,
                            )
                            if not dry_run:
                                save_user_data(user_data_path, data)
                            save_progress(
                                progress_path,
                                idx,
                                total,
                                {
                                    "aborted_by_flood": True,
                                    "flood_wait_seconds": retry_secs,
                                    "resume_after": resume_at,
                                },
                            )
                            aborted_by_flood = True
                            progress_saved = True
                            break

            if aborted_by_flood:
                break

            if found_user_id is None:
                not_found += 1
                consecutive_not_found += 1
            else:
                consecutive_not_found = 0
                key = str(found_user_id)
                if key in data:
                    already_exists += 1
                else:
                    data[key] = {
                        "questions": 5,
                        "subscription_end": None,
                        "email": None,
                        "last_refill_at": now_str,
                        "username": username,
                        "first_name": None,
                        "last_name": None,
                        "phone": None,
                        "imported_from_usernames": True,
                    }
                    added += 1

            if (
                max_consecutive_not_found > 0
                and consecutive_not_found >= max_consecutive_not_found
                and added == 0
            ):
                print(
                    (
                        f"[{idx + 1}/{total}] Подряд {consecutive_not_found} ников без добавления. "
                        "Импорт остановлен — для холодной базы это обычно бесполезно."
                    ),
                    flush=True,
                )
                save_progress(
                    progress_path,
                    idx + 1,
                    total,
                    {
                        "stopped_low_yield": True,
                        "stats": {
                            "checked": checked,
                            "added": added,
                            "exists": already_exists,
                            "not_found": not_found,
                        },
                    },
                )
                if not dry_run:
                    save_user_data(user_data_path, data)
                stopped_low_yield = True
                progress_saved = True
                break

            # Сохраняем прогресс и (если не dry-run) базу
            if (idx + 1) % 25 == 0:
                save_progress(
                    progress_path,
                    idx + 1,
                    total,
                    {
                        "stats": {
                            "checked": checked,
                            "added": added,
                            "exists": already_exists,
                            "not_found": not_found,
                        },
                    },
                )
                if not dry_run:
                    save_user_data(user_data_path, data)

                elapsed = max((datetime.now() - started_at).total_seconds(), 1.0)
                speed = checked / elapsed
                progress_pct = ((idx + 1) / total) * 100 if total else 100.0
                print(
                    (
                        f"[{idx + 1}/{total}] {progress_pct:.2f}% | "
                        f"checked={checked}, added={added}, exists={already_exists}, not_found={not_found} | "
                        f"speed={speed:.2f} ник/сек"
                    ),
                    flush=True,
                )

            # rate limit protection
            await asyncio.sleep(random.uniform(delay_min, delay_max))
            if batch_size > 0 and (checked % batch_size == 0):
                print(
                    f"[{idx + 1}/{total}] Батч-пауза {pause_seconds} сек (после {checked} проверок)",
                    flush=True,
                )
                await asyncio.sleep(pause_seconds)

    except KeyboardInterrupt:
        print("\nОстановлено вручную (Ctrl+C). Сохраняю прогресс...", flush=True)
        save_progress(
            progress_path,
            resume_index,
            total,
            {"stopped_manual": True},
        )
        if not dry_run:
            save_user_data(user_data_path, data)
        progress_saved = True
    finally:
        await bot.session.close()

    if not progress_saved and checked > 0:
        save_progress(
            progress_path,
            min(start_idx + checked, total),
            total,
            {
                "stats": {
                    "checked": checked,
                    "added": added,
                    "exists": already_exists,
                    "not_found": not_found,
                },
            },
        )
        if not dry_run:
            save_user_data(user_data_path, data)

    print("Проверка ников завершена.")
    print(f"Всего ников в файле: {total}")
    print(f"Проверено в этом запуске: {checked}")
    print(f"Добавлено новых пользователей: {added}")
    print(f"Уже были в базе: {already_exists}")
    print(f"Не найдены/недоступны: {not_found}")
    print(f"Режим dry-run: {'да' if dry_run else 'нет'}")
    print(f"Файл прогресса: {progress_path}")
    if aborted_by_flood:
        hrs = flood_wait_secs // 3600
        print(
            f"Импорт остановлен из-за FloodWait (~{hrs} ч). "
            "Запустите ту же команду позже — продолжит с сохранённого места.",
            flush=True,
        )
    if stopped_low_yield:
        print(
            "Импорт остановлен: слишком много ников подряд не добавились. "
            "Для продолжения увеличьте --max-consecutive-not-found или поставьте 0.",
            flush=True,
        )


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
    parser.add_argument(
        "--usernames-file",
        help="Путь к txt с никами (@username) по одному в строке",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=1.2,
        help="Минимальная пауза между проверками ников",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=2.0,
        help="Максимальная пауза между проверками ников",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=60,
        help="После скольких проверок делать длинную паузу",
    )
    parser.add_argument(
        "--batch-pause",
        type=float,
        default=25.0,
        help="Длина длинной паузы между батчами (сек)",
    )
    parser.add_argument(
        "--progress-file",
        default="username_import_progress.json",
        help="Файл для сохранения прогресса проверки ников",
    )
    parser.add_argument(
        "--max-flood-wait",
        type=int,
        default=180,
        help="Если FloodWait больше этого значения (сек), скрипт завершится и сохранит прогресс",
    )
    parser.add_argument(
        "--max-consecutive-not-found",
        type=int,
        default=150,
        help="Остановить импорт, если подряд столько ников не добавились (0 = не останавливать)",
    )
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        env_map = load_env_file(".env")
        token = env_map.get("TELEGRAM_TOKEN")

    if not token:
        print("Не найден TELEGRAM_TOKEN (ни в env, ни в .env).")
        return

    if args.usernames_file:
        asyncio.run(
            run_usernames(
                source_path=args.usernames_file,
                user_data_path=args.db,
                token=token,
                dry_run=args.dry_run,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
                batch_size=args.batch_size,
                pause_seconds=args.batch_pause,
                progress_path=args.progress_file,
                max_flood_wait=args.max_flood_wait,
                max_consecutive_not_found=args.max_consecutive_not_found,
            )
        )
    else:
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
