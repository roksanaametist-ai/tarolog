# Follow the Frensy — бот в MAX

Тот же продукт, что Telegram-бот в `main.py`. Транспорт — MAX Bot API (webhook). Анкеты раздельные (`user_data_max.json`), а вопросы и подписка общие: в «Мой баланс» есть код, его нужно отправить второму боту командой `/link КОД`. Файл кошелька — `shared_wallet.json` рядом с данными Telegram (`BOT_DATA_DIR`).

## Что совпадает с Telegram

- Меню: вопрос, карта дня, да/нет, чувства/мысли/действия, предупреждение, баланс, консультация, подписка, поддержка, как работает, пригласить друга (+5), группа, промокод, дополнительные расклады, у админа — рассылка и статистика
- Согласие: сначала персональные данные, затем оферта 18+
- Расклад: вопрос, потом 3–6 карт через запятую (да/нет — одна карта, классика — три). Кнопка миниаппа открывает те же `CARDS_WEBAPP_URL` / `YESNO_WEBAPP_URL`
- Карта дня — один раз в сутки, без списания баланса
- Рефералка: новый пользователь по `ref_<id>` даёт пригласившему +5
- Тарифы ЮKassa: 169 / 359 / 999 / 2999 и автопродление
- Промокоды из Telegram (+100 вопросов)
- Заглушка нейросети `LLM_PUBLIC_STUB` (по умолчанию включена, админы из `MAX_ADMIN_IDS` получают трактовку)

Канал Telegram из MAX не виден. Кнопка «Я подписан на канал» начисляет те же +5 и дальше раз в 30 дней.

## Env

В корневой `.env` (см. `.env.example`):

```
MAX_BOT_TOKEN=
MAX_WEBHOOK_SECRET=my-secret-min5chars
MAX_WEBHOOK_URL=https://followthefrensy.com/max/webhook
MAX_BOT_USERNAME=username_without_at
MAX_ADMIN_IDS=ваш_max_user_id
MAX_PORT=8088
```

`491482483` — это Telegram id. Пока в `MAX_ADMIN_IDS` не записан id из MAX, статистики и рассылки не будет.

## Запуск

```bash
python -m max_bot
```

Health: `GET /health`  
Webhook: `POST /max/webhook`

На VPS: `deploy/hshp/targpt-max.service`, nginx location `/max/webhook` → `127.0.0.1:8088`.

```bash
python -m max_bot.register_webhook --url https://followthefrensy.com/max/webhook
```
