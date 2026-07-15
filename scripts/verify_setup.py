#!/usr/bin/env python3
"""Проверка зависимостей и .env перед запуском бота."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PACKAGES = (
    ("dotenv", "python-dotenv"),
    ("aiogram", "aiogram"),
    ("openai", "openai"),
    ("yookassa", "yookassa"),
)

REQUIRED_ENV = ("TELEGRAM_TOKEN", "GROQ_API_KEY")
OPTIONAL_ENV = ("YOOKASSA_ACCOUNT_ID", "YOOKASSA_SECRET_KEY")


def check_imports() -> bool:
    ok = True
    for module, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(module)
            print(f"OK: {pip_name}")
        except ImportError:
            print(f"MISSING: {pip_name}  (pip install {pip_name})")
            ok = False
    return ok


def check_env() -> bool:
    from dotenv import load_dotenv
    import os

    env_path = ROOT / ".env"
    load_dotenv(env_path)
    ok = True

    if not env_path.exists():
        print(f"WARN: нет файла {env_path}")
        print("      скопируйте .env.example -> .env и заполните значения")
        ok = False

    for key in REQUIRED_ENV:
        if os.getenv(key):
            print(f"OK: {key}")
        else:
            print(f"MISSING: {key}")
            ok = False

    for key in OPTIONAL_ENV:
        if os.getenv(key):
            print(f"OK: {key}")
        else:
            print(f"WARN: {key} не задан (оплата YooKassa не будет работать)")

    return ok


def check_syntax() -> bool:
    import ast

    main_py = ROOT / "main.py"
    try:
        ast.parse(main_py.read_text(encoding="utf-8"), filename=str(main_py))
        print(f"OK: синтаксис {main_py.name}")
        return True
    except SyntaxError as e:
        print(f"FAIL: синтаксис {main_py.name}:{e.lineno} — {e.msg}")
        return False


def main() -> int:
    print("=== Проверка TarGPT3 ===\n")
    results = [
        ("Пакеты", check_imports()),
        ("Переменные окружения", check_env()),
        ("Синтаксис main.py", check_syntax()),
    ]
    print()
    if all(r[1] for r in results):
        print("Всё готово к запуску: python main.py")
        return 0
    print("Есть проблемы. Установите зависимости:")
    print(f"  pip install -r {ROOT / 'requirements.txt'}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
