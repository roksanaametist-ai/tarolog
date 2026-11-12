# Follow the Frensy — бот + лендинг

## Быстрый старт (Windows)

```powershell
cd "путь\к\TarGPT3"
.\setup.ps1          # один раз: venv + пакеты
.\run-bot.ps1        # запуск бота
.\run-landing.ps1    # запуск сайта (в другом окне)
```

Проверка: `.\venv\Scripts\python.exe .\scripts\verify_setup.py`

## Структура

| Часть | Папка / файл | Назначение |
|-------|----------------|------------|
| Бот | `main.py` | Telegram-таролог |
| Лендинг | `landing/` | Сайт с формой лидов |
| Данные бота | `BOT_DATA_DIR` или корень проекта | JSON с пользователями |
| Секреты | `.env` | Токены (не коммитить!) |

## Деплой

**Продакшен (HSHP VPS, `followthefrensy.ru`):** см. `DEPLOY-HSHP.md`  
Бот — systemd, лендинг — Gunicorn + nginx. WebApp `/cards` и `/yesno` уже на сервере.

**Альтернатива (Amvera):** см. `DEPLOY-AMVERA.md` — два облачных проекта, если VPS не используете.

## Связка сайт → бот

1. На лендинге: `LANDING_BOT_URL=https://t.me/ВашБот`
2. `LANDING_BOT_START_PARAM=site` → ссылка `?start=site`
3. Бот помечает таких пользователей и показывает приветствие с сайта

## Свои материалы

- **Фото на сайте:** положите `landing/static/images/portrait.jpg` (или `.png`)
- **Соцсети:** в `.env` раскомментируйте и заполните `SOCIAL_INSTAGRAM`, `SOCIAL_TIKTOK`, …
- **Карты WebApp:** `CARDS_WEBAPP_URL`, `YESNO_WEBAPP_URL` в `.env`

## Полезные команды

```powershell
.\venv\Scripts\Activate.ps1
python main.py
python scripts\verify_setup.py
```
