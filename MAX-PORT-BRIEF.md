# Follow the Frensy — резюме бота + бриф для порта в MAX

> **Как использовать в новом диалоге Cursor:**  
> «Сделай бота Follow the Frensy для мессенджера MAX по файлу `MAX-PORT-BRIEF.md`. Логику раскладов/баланса/рефералки бери из `main.py`, транспорт — MAX Bot API.»

Дата слепка: **2026-07-16**

> С ноября 2026 поведение MAX-бота выровнено с текущим `main.py`, а не с этим снимком.
> Рефералка: +5 за нового друга. Согласие: ПД, затем оферта. Карты вводятся через запятую
> или миниапп. Меню, тарифы ЮKassa, промокоды и карта дня — как в Telegram.
> Запуск: `deploy/hshp/targpt-max.service`, webhook `https://followthefrensy.com/max/webhook`.

---

## 1. Что это (продукт)

**Follow the Frensy** — персональный ИИ-таролог Роксаны Аметист.

| | |
|--|--|
| Telegram-бот | [@Roxanaametist_Taro_bot](https://t.me/Roxanaametist_Taro_bot) |
| Канал | [t.me/follow_the_frensy](https://t.me/follow_the_frensy) |
| Сайт | [followthefrensy.ru](https://followthefrensy.ru/) |
| Консультации | [@roxanaametist](https://t.me/roxanaametist) |
| Владелец / admin id | `491482483` |

Тон: коротко, по делу, по-русски, без воды и «энергий вселенной». Бренд в UI: Follow the Frensy.

---

## 2. Что умеет бот сейчас (фичи)

### Расклады
- **Задать вопрос** — 1/3/5 карт (настройка пользователя), выбор в WebApp или авто
- **Да/Нет** — отдельный WebApp `/yesno`
- **Классические:** карта дня, карта на завтра (после 18:00, 1/вечер), СМД (чувства·мысли·действия), предупреждение, выбор из двух
- **Диалог с тарологом** — уточняющие ходы + доп. карта
- **Банк вопросов** по темам (любовь/работа/жизнь/я)
- **История раскладов** у пользователя + JSON `reading_history.json` / `user_questions.json`

### Экономика
- Старт: **5** вопросов
- Канал: **+5** раз в 30 дней (подписчикам)
- Рефералка (**упрощено 2026-07-16**):
  - друг зашёл по `ref_<id>` → рефереру **+5**, другу **+3**
  - **3 приглашённых аккаунта** → **месяц безлимита** (31 день), один раз
  - шеринг расклада `share_<id>` → +1 когда друг сделал 1-й расклад
- ЮKassa: ключи есть, **`PAYMENTS_ENABLED=0`** (оплата выкл., безлимит через друзей)
- Промокоды, баланс, админ-выдача вопросов

### Админка
- Кнопка **📊 Статистика** / `/admin123` — DAU7, расклады по kind, лиды, рефералы, оплаты
- `/who123`, `/grant123`, `/stats_date123 YYYY-MM-DD`, `/denginam`, секретная команда из `.env`
- Рассылка сообщений

### Прочее
- Лендинг + лиды (`landing/`)
- Заявка на живую консультацию
- Соглашение (Telegraph) при первом входе
- Inline-меню: старые кнопки снимаются, чтобы не копились

---

## 3. Стек и прод

### Код
- **Бот:** `main.py` (~7k строк), **aiogram 3**, polling, `MemoryStorage`
- **LLM:** OpenAI-совместимый клиент
  - провайдер: `TAROT_PROVIDER` = `openai` | `groq` (если не задан — openai при наличии ключа)
  - модели: `GROQ_TAROT_MODEL` (default `llama-3.3-70b-versatile`), fallback `llama-3.1-8b-instant`; OpenAI `gpt-4o-mini`
  - **на проде:** OpenAI-ключ часто 401 → падает на Groq; у Groq бывает лимит TPD 100k
- **Карты:** `static/card1.jpg`…`card78.jpg`, словарь имён в `main()` 
- **WebApp (выбор карт):** исходники `webapp/cards`, `webapp/yesno` → на сервере каталоги `sitetargpt-master` / `sitetargpt2-master` (локальных копий в репо нет)
- **Лендинг:** `landing/SiteApp.py` Flask → gunicorn `:5002`
- **Деплой:** VPS HSHP `37.46.18.192`, путь `/root/tarolog`, systemd `tarolog`

### Важные JSON (данные)
`user_data.json`, `logs.json`, `reading_history.json`, `user_questions.json`, `payment_data.json`, `payment_nurture.json`, `tomorrow_card.json`, `consultation_leads.json`, `status_data.json`, `user_agreements.json`, …

### Env (имена, без секретов)
`TELEGRAM_TOKEN`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `TAROT_PROVIDER`, `OPENAI_TAROT_MODEL`, `GROQ_TAROT_MODEL`, `YOOKASSA_*`, `PAYMENTS_ENABLED`, `CARDS_WEBAPP_URL`, `YESNO_WEBAPP_URL`, `CHANNEL_URL`, `CONSULTATION_URL`, `LANDING_BOT_URL`, `LANDING_BOT_START_PARAM`, `ADMIN_CMD_TOTAL_USERS`, `BOT_DATA_DIR`

Пример: `.env.example`

---

## 4. Ключевые куски кода (что переиспользовать в MAX)

| Логика | Где в `main.py` | Перенос в MAX |
|--------|-----------------|---------------|
| Колода + имена карт | конец `main()`, `tarot_cards` | **как есть** |
| Нормализация путей WebApp | `normalize_deck_card_path`, `cards_from_webapp_data` | адаптировать под MAX mini-app payload |
| Промпты / structured JSON | `TAROT_SYSTEM_PROMPT`, `get_tarot_reading_structured`, `tighten_tarot_text` | **как есть** |
| Доставка расклада | `deliver_structured_spread` | заменить `bot.send_*` на MAX API |
| Баланс / подписка | `UserData` | **как есть** (общий JSON или общая БД) |
| Рефералка 3→месяц | `maybe_award_referral_milestones`, `REFERRAL_UNLIMITED_*` | deep link MAX вместо `t.me/?start=ref_` |
| Админ-дашборд | `build_admin_dashboard_html` | текст без HTML или свой parse mode MAX |
| Карта на завтра | `TomorrowCardStore`, push loop | свой scheduler |

**Не копировать 1:1:** aiogram-хендлеры, Telegram WebApp JS bridge, YooKassa Telegram-flow, polling.

---

## 5. Бриф: сделать того же бота в MAX

### Цель
Тот же продукт Follow the Frensy в мессенджере **MAX**: расклады, баланс, рефералка 3→месяц, миниапп выбора карт, админка для Роксаны.

### Официально
- Docs: https://dev.max.ru/docs-api  
- API host: `platform-api2.max.ru`  
- Прод: **webhook HTTPS** (не long polling)  
- Токен бота: обычно через кабинет для **ИП/ООО** — https://business.max.ru/self  
- Мини-приложения: кнопка `open_app` + MAX Bridge (`window.WebApp.initData`)  
- Кнопки: inline_keyboard (callback / link / open_app / request_contact)

### Архитектура порта (рекомендуемая)
```
shared/                 # вынести из main.py
  deck.py               # tarot_cards, draw, orientation
  llm.py                # get_tarot_reading*
  economy.py            # UserData, referrals, balance
  readings.py           # deliver logic без Telegram

max_bot/
  app.py                # webhook FastAPI/Flask
  handlers.py           # команды MAX
  keyboards.py

max_miniapp/            # форк webapp/cards + yesno под MAX Bridge
```

На первом этапе допустим **дубликат логики** в `max_bot/` с копией нужных функций — лишь бы быстрее запустилось; рефакторинг shared — вторым шагом.

### MVP MAX (порядок работ)
1. Завести бота MAX, webhook на VPS (новый systemd, например `targpt-max`)
2. `/start` + соглашение + баланс 5
3. Кнопки: Задать вопрос / Классика / Баланс / Бонусы / Консультация
4. Расклад без миниаппа (авто-вытягивание карт) + LLM
5. Рефералка: 3 инвайта → месяц (адаптировать deep link MAX)
6. Миниапп выбора карт (порт `webapp/cards`)
7. Админ-статистика для id владельца
8. (Опционально) оплата / канал-бонус — после MVP

### Что НЕ тащить в MVP
- ЮKassa (пока выкл и в TG)
- Полный паритет всех классических раскладов сразу — хватит: вопрос, да/нет, карта дня
- Рассылка / промокоды / карта на завтра — фаза 2

### Общие данные или раздельные?
- **Проще для старта:** отдельный `user_data_max.json` (не смешивать TG id и MAX id)
- **Потом:** единый аккаунт по телефону (`request_contact`) — опционально

### Критерии «готово»
- [ ] Пользователь в MAX получает трактовку на русском по 3 картам  
- [ ] Баланс списывается / безлимит по подписке работает  
- [ ] 3 реферала → месяц безлимита  
- [ ] Роксана видит админ-сводку  
- [ ] Миниапп открывается из кнопки и возвращает выбранные карты  

### Промпт для нового чата (скопировать)

```
Нужен порт Telegram-бота Follow the Frensy в мессенджер MAX.

Контекст: файл MAX-PORT-BRIEF.md в репо TarGPT3.
Логика раскладов/экономики/рефералки — в main.py.
Не переписывай всё с нуля: выдели shared-ядро или скопируй нужные функции,
транспорт сделай на MAX Bot API (webhook, platform-api2.max.ru).

Сделай MVP по чеклисту из §5 MAX-PORT-BRIEF.md.
Рефералка: 3 приглашённых → 31 день безлимита.
PAYMENTS пока выключены.
Админ: telegram/max id владельца 491482483 (уточни формат user id в MAX).
Миниапп — после текстового MVP.
Пиши код в папку max_bot/ (+ при необходимости shared/), не ломай текущий Telegram main.py.
```

---

## 6. Известные грабли (TG, учесть в MAX)

1. Пути карт из миниаппа `/cards/static/cardN.jpg` → нормализовать к `static/cardN.jpg` (уже есть `normalize_deck_card_path`)
2. Markdown в админ-стате ломается на текстах вопросов → в TG уже HTML + escape
3. Чужие/мертвые API-ключи → всегда свой Groq/OpenAI аккаунт
4. Два источника миниаппа: править `webapp/`, деплоить в `sitetargpt*` через `upload-miniapp-now.ps1` (не старый `upload-miniapp.ps1`)
5. `MemoryStorage` — FSM сбрасывается при рестарте

---

## 7. Быстрые ссылки на файлы

- Бот: `main.py`
- Зависимости: `requirements.txt`
- Env-пример: `.env.example`
- Миниаппы: `webapp/cards/index.html`, `webapp/yesno/index.html`
- Лендинг: `landing/SiteApp.py`
- Деплой TG: `DEPLOY-HSHP.md`, `deploy/hshp/`
- Этот бриф: `MAX-PORT-BRIEF.md`
