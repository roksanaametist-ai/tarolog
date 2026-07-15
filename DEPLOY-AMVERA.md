# Деплой на Amvera (бот + лендинг)

Нужны **два отдельных проекта** в [панели Amvera](https://cloud.amvera.ru/projects).

Репозиторий GitHub: `https://github.com/roksanaametist-ai/tarolog.git`

---

## Шаг 0. Подготовка (обязательно)

На Amvera уходит только то, что **закоммичено и запушено** в GitHub. Сейчас в репозитории много незакоммиченных файлов (`amvera.yml`, `landing/`, `requirements.txt`, правки `main.py` и т.д.).

1. Закоммитьте изменения (без `.env`, `users.txt`, `базы/`).
2. Запушьте в `main`:
   ```powershell
   git push origin main
   ```

> Если нужна помощь с коммитом — напишите «закоммить и запушь».

### Важно: один репозиторий — два приложения

В корне `main` лежит `amvera.yml` **для бота**. Amvera читает `amvera.yml` только из корня репозитория.

Для лендинга используем **отдельную ветку `landing`** с другим `amvera.yml` в корне (шаблон: `scripts/amvera-landing-root.yml`).

| Проект Amvera | Ветка GitHub | `amvera.yml` в корне |
|---------------|--------------|----------------------|
| Бот | `main` | `main.py`, `requirements.txt` |
| Лендинг | `landing` | `landing/SiteApp.py`, `landing/requirements.txt` |

Создание ветки `landing` (один раз, после пуша в `main`):

```powershell
git checkout main
git pull origin main
git checkout -b landing
Copy-Item scripts\amvera-landing-root.yml amvera.yml -Force
git add amvera.yml
git commit -m "Amvera config for landing deploy"
git push -u origin landing
git checkout main
```

---

## Шаг 1. Проект «Бот» (Telegram, 24/7)

### 1.1 Создание проекта

1. [cloud.amvera.ru/projects](https://cloud.amvera.ru/projects) → **Создать**
2. Имя, например: `targpt-bot` или `follow-the-frensy-bot`
3. Окружение: **Python pip** (версия 3.12 подтянется из `amvera.yml`)

### 1.2 Репозиторий

**Вариант A — GitHub (удобнее для обновлений):**

1. Вкладка **Репозиторий** → **Подключить GitHub**
2. Git service: **GitHub**
3. Ветка: **`main`**
4. Secret — сгенерировать и скопировать
5. В GitHub: Settings → Webhooks → Add webhook
   - Payload URL — из Amvera
   - Secret — тот же
   - Content type: `application/json`
   - Events: **Just the push event** (или «Send me everything»)
6. Если репозиторий приватный — добавьте **Personal Access Token** в Amvera

**Вариант B — push в git Amvera:**

```powershell
git remote add amvera-bot https://git.amvera.ru/<ваш-логин>/<имя-проекта-бота>
git push amvera-bot main
```

### 1.3 Постоянное хранилище

Вкладка **Настройки** (или **Хранилище**) → включить **Persistence** / папку **`/data`**.

Без этого JSON с пользователями, платежами и промокодами пропадут при пересборке.

### 1.4 Переменные окружения

Вкладка **Переменные**. Секреты (`TELEGRAM_TOKEN`, ключи API) — тип **Секрет**.

Скопируйте из локального `.env`:

| Переменная | Обязательно | Пример / значение |
|------------|-------------|-------------------|
| `TELEGRAM_TOKEN` | да | из BotFather |
| `GROQ_API_KEY` | да | из console.groq.com |
| `GROQ_TAROT_MODEL` | нет | `llama-3.3-70b-versatile` |
| `YOOKASSA_ACCOUNT_ID` | да | shop id |
| `YOOKASSA_SECRET_KEY` | да | secret key |
| `CHANNEL_URL` | да | `https://t.me/follow_the_frensy` |
| `GROUP_INVITE_URL` | нет | ссылка на группу |
| `CONSULTATION_URL` | да | `https://t.me/roxanaametist` |
| `LANDING_BOT_START_PARAM` | да | `site` |
| `CARDS_WEBAPP_URL` | да | `https://followthefrensy.ru/cards` |
| `YESNO_WEBAPP_URL` | да | `https://followthefrensy.ru/yesno` |
| `BOT_RETURN_URL` | да | `https://t.me/Roxanaametist_Taro_bot` |
| `ADMIN_CMD_TOTAL_USERS` | нет | `u9k2m7p4q1` |
| `PYTHONUNBUFFERED` | рекомендуется | `1` (логи в реальном времени) |

`BOT_DATA_DIR` **не задавайте** — по умолчанию `/data`.

### 1.5 Сборка и проверка

1. Дождитесь статуса **Успешно развернуто**
2. Логи приложения: строка **`Start polling`**
3. В Telegram: `/start` у @Roxanaametist_Taro_bot

---

## Шаг 2. Проект «Лендинг» (сайт)

### 2.1 Создание проекта

1. **Создать** второй проект, например: `targpt-landing`
2. Окружение: **Python pip**

### 2.2 Репозиторий

Тот же GitHub-репозиторий, но ветка **`landing`** (не `main`).

Webhook настраивается так же, как для бота, с веткой **`landing`**.

Или push в git Amvera:

```powershell
git remote add amvera-landing https://git.amvera.ru/<ваш-логин>/<имя-проекта-лендинга>
git push amvera-landing landing
```

### 2.3 Постоянное хранилище

Включить **`/data`** — туда пишется `leads.json` (`LANDING_DATA_DIR=/data`).

### 2.4 Переменные окружения

| Переменная | Обязательно | Значение |
|------------|-------------|----------|
| `LANDING_BOT_URL` | да | `https://t.me/Roxanaametist_Taro_bot` |
| `LANDING_BOT_START_PARAM` | да | `site` |
| `LANDING_DATA_DIR` | да | `/data` |
| `CONSULTATION_URL` | да | `https://t.me/roxanaametist` |
| `SOCIAL_TELEGRAM` | да | `https://t.me/follow_the_frensy` |
| `SOCIAL_TIKTOK` | нет | ссылка на TikTok (пока можно не задавать) |
| `SOCIAL_VK` | нет | ссылка на ВК |
| `SOCIAL_YOUTUBE` | нет | ссылка на YouTube |
| `PYTHONUNBUFFERED` | рекомендуется | `1` |

### 2.5 Домен (опционально)

Вкладка **Настройки** → **Добавить доменное имя** → бесплатный домен Amvera или свой (`followthefrensy.ru`).

### 2.6 Проверка

1. Откройте URL проекта в браузере
2. `https://<ваш-домен>/health` → `{"status":"ok"}`
3. Заполните форму лида → в Amvera, вкладка **Репозиторий** → папка **Data** → `leads.json`
4. Кнопка «Получить 5 раскладов» → Telegram с `?start=site`

---

## Шаг 3. Чеклист после деплоя

- [ ] Бот: `/start` отвечает
- [ ] Бот: `/start site` — приветствие «с сайта»
- [ ] Лендинг: форма сохраняет лид в `/data/leads.json`
- [ ] Лендинг → бот: deep link `?start=site`
- [ ] Бот: кнопка «Выбрать карты» (WebApp `followthefrensy.ru/cards`)
- [ ] Заполнить `SOCIAL_TIKTOK`, `SOCIAL_VK`, `SOCIAL_YOUTUBE` в лендинге (когда будут ссылки)

---

## Шаг 4. Обновление кода

```powershell
# Изменения в боте и общем коде:
git checkout main
# ... правки ...
git add .
git commit -m "описание"
git push origin main
# Amvera (бот) пересоберётся по webhook

# Подтянуть те же правки в лендинг:
git checkout landing
git merge main
# Если менялся только landing/ — amvera.yml в корне не трогайте
git push origin landing
git checkout main
```

---

## Шаг 5. Фото на сайт

Положите в репозиторий:

`landing/static/images/portrait.jpg`

Закоммитьте в `main`, смержите в `landing`, запушьте обе ветки.

---

## Частые проблемы

| Симптом | Что проверить |
|---------|----------------|
| Бот не стартует | `TELEGRAM_TOKEN`, логи сборки, `requirements.txt` |
| Лендинг 502 | `host=0.0.0.0`, `containerPort: 5000` в `amvera.yml` |
| Лендинг запускает бота | Проект лендинга привязан к ветке **`landing`**, не `main` |
| Данные пропали | Persistence `/data` включён в настройках проекта |
| Нет логов | `PYTHONUNBUFFERED=1` |
| Два бота / conflict | Только **один** инстанс бота с тем же токеном (не запускайте локально и на Amvera одновременно) |

Поддержка Amvera: support@amvera.ru (укажите логин и имя проекта).
