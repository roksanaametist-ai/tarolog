# Деплой на HSHP VPS (followthefrensy.ru)

**HSHP** ([hshp.host](https://hshp.host/)) — VPS с root-доступом. Домен `followthefrensy.ru` уже указывает на этот сервер:

| URL | Статус |
|-----|--------|
| `https://followthefrensy.ru/cards` | WebApp уже работает |
| `https://followthefrensy.ru/yesno` | WebApp уже работает |
| `https://followthefrensy.ru/` | Пока дефолтная страница nginx — нужен лендинг |
| Telegram-бот | Нужен systemd-сервис на VPS |

**Amvera для этого проекта не нужен**, если всё крутится на HSHP.

### YooKassa — автопродление

В личном кабинете ЮKassa для магазина включите **Автоплатежи**. Без этого `save_payment_method` не сработает, и карта не сохранится.

Безлимит (месяц / 3 мес / год) продлевается фоном на VPS (`recurring_billing_loop` в `main.py`). Пакет 10 запросов — разовый.

---

## Архитектура на одном VPS

```
nginx (80/443)
├── /              → Gunicorn → landing/SiteApp.py (порт 5000)
├── /static/       → landing/static/
├── /cards         → уже настроено (WebApp, не трогать)
└── /yesno         → уже настроено (WebApp, не трогать)

systemd
├── targpt-bot.service      → python main.py (polling 24/7)
└── targpt-landing.service  → gunicorn SiteApp:app

/opt/targpt/data/           → JSON бота + leads.json
```

---

## 1. Подготовка сервера (SSH)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx

sudo useradd -r -m -s /bin/bash targpt || true
sudo mkdir -p /opt/targpt/data
sudo chown -R targpt:targpt /opt/targpt
```

---

## 2. Клонирование и окружение

Под пользователем `targpt` (или через `sudo -u targpt`):

```bash
cd /opt/targpt
git clone https://github.com/roksanaametist-ai/tarolog.git .
git checkout main

python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -r landing/requirements.txt gunicorn
```

Скопируйте `.env` с локальной машины (секреты не в git):

```bash
nano /opt/targpt/.env
```

Обязательно на сервере:

```env
BOT_DATA_DIR=/opt/targpt/data
LANDING_DATA_DIR=/opt/targpt/data
LANDING_BOT_URL=https://t.me/Roxanaametist_Taro_bot
LANDING_BOT_START_PARAM=site
CARDS_WEBAPP_URL=https://followthefrensy.ru/cards
YESNO_WEBAPP_URL=https://followthefrensy.ru/yesno
# ... остальное из локального .env
```

```bash
chmod 600 /opt/targpt/.env
```

---

## 3. Systemd-сервисы

```bash
sudo cp /opt/targpt/deploy/hshp/targpt-bot.service /etc/systemd/system/
sudo cp /opt/targpt/deploy/hshp/targpt-landing.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable targpt-bot targpt-landing
sudo systemctl start targpt-bot targpt-landing
sudo systemctl status targpt-bot targpt-landing
```

Логи:

```bash
journalctl -u targpt-bot -f
journalctl -u targpt-landing -f
```

---

## 4. Nginx

**Важно:** на сервере уже есть конфиг для `/cards` и `/yesno`. Не перезаписывайте весь nginx целиком — добавьте только прокси для `/` и статику лендинга.

Пример: `deploy/hshp/nginx-followthefrensy.conf`

```bash
sudo nano /etc/nginx/sites-available/followthefrensy.ru
# вставьте/объедините с существующим конфигом
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS (если ещё нет):

```bash
sudo certbot --nginx -d followthefrensy.ru -d www.followthefrensy.ru
```

---

## 5. Проверка

- [ ] `curl -s http://127.0.0.1:5000/health` → `{"status":"ok"}`
- [ ] `https://followthefrensy.ru/` — лендинг, не «Welcome to nginx»
- [ ] Форма лида → `/opt/targpt/data/leads.json`
- [ ] Кнопка на сайте → бот с `?start=site`
- [ ] `journalctl -u targpt-bot` → `Start polling`
- [ ] `/cards` и `/yesno` по-прежнему открываются

---

## 6. Обновление кода

```bash
cd /opt/targpt
sudo -u targpt git pull origin main
sudo -u targpt ./venv/bin/pip install -r requirements.txt -r landing/requirements.txt
sudo systemctl restart targpt-bot targpt-landing
```

---

## Частые проблемы

| Симптом | Решение |
|---------|---------|
| Бот не отвечает | `systemctl status targpt-bot`, проверить `TELEGRAM_TOKEN` в `.env` |
| Два инстанса бота | Остановить локальный `run-bot.ps1` и старый процесс на сервере |
| 502 на главной | `targpt-landing` не запущен или nginx не проксирует на `:5000` |
| Сломались /cards | Откатить nginx, WebApp location не должен проксироваться на Flask |
| Данные пропали | Убедиться, что `BOT_DATA_DIR` и `LANDING_DATA_DIR` = `/opt/targpt/data` |

Готовые unit-файлы: `deploy/hshp/`.
