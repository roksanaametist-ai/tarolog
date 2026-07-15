# Follow the Frensy — лендинг-портал

Интерактивный одностраничный сайт: эмоциональный вход → боль → доверие → услуги → лид → «сжигание» → соцсети → «Перерождение».

## Запуск локально

```bash
cd landing
pip install -r requirements.txt
set FLASK_DEBUG=1
python SiteApp.py
```

Откройте http://127.0.0.1:5000

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `LANDING_BOT_URL` | Ссылка на бота, напр. `https://t.me/YourBot` |
| `LANDING_BOT_START_PARAM` | Параметр `/start`, напр. `site` → `?start=site` |
| `LANDING_DATA_DIR` | Папка для `leads.json` (на Amvera: `/data`) |
| `SOCIAL_*` | Ссылки на соцсети |
| `CONSULTATION_URL` | Запись на консультацию |
| `LANDING_SCHOOL_URL` | Школа эзотерических искусств |

Лиды сохраняются в `leads.json`.

## Деплой на Amvera

Корень проекта на хостинге — папка `landing`, `scriptName: SiteApp.py`.

## Связка с ботом

1. В `.env` укажите `LANDING_BOT_URL` и при необходимости `LANDING_BOT_START_PARAM=site`.
2. В `main.py` можно обработать `/start site` — начисление 5 раскладов (сейчас новые пользователи и так получают 5 при регистрации).
3. После отправки формы сайт открывает бота в новой вкладке.

## Свои материалы

- Портрет: положите `static/images/portrait.jpg` и замените `src` в `templates/index.html`.
- Логотип-ракушка / астронавт: замените SVG в hero или подключите PNG/WebP в `static/images/`.
