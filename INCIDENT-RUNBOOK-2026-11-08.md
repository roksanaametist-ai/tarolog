# Runbook: «59 дней» у админа + проверка Карины (2026-11-08)

Всё вводить в консоли VNC на DE. Каждая команда — **одна строка**, вставлять целиком.
Шаги 1–4 только читают. Шаг 5 меняет данные — только для админа `491482483`.
Код оплаты, DNS, MSK не трогаем.

---

## Почему могло остаться 59 (по коду)

1. **Правка ушла не в тот файл / не сохранилась.** При старте бот читает ТОЛЬКО sqlite
   (`documents` → `users`). `user_data.json` при этом игнорируется. Если скрипт запускали
   не из той папки (или `BOT_DATA_DIR` в unit указывает в другое место), `sqlite3.connect`
   молча создаёт НОВЫЙ пустой файл — правка «прошла», а бот читает старый.
2. **На сервере старая версия кода, где главный — `shared_wallet.json`.** В ней срок
   читается из кошелька по «каноническому» ключу. Если TG админа связан с MAX (`/link`),
   запись лежит под `max:…`, а не `tg:491482483` — правка `tg:` мимо.
3. **После правки снова сработала выдача.** `fulfill_invoice` берёт базу из
   `shared_wallet.json` и **прибавляет** 31 день. Если счёт выдали вручную, а в
   `robokassa_invoices.json` он не помечен `fulfilled`, то повторный ResultURL
   (Robokassa повторяет уведомления) или ручной вызов снова даст +31 → ~07.01.2027 → 59.

Шаги 1–4 покажут, какой из трёх случаев.

---

## 1. Где живёт бот и его данные

```bash
systemctl cat tarolog | grep -E 'WorkingDirectory|ExecStart|Environment'; grep -h BOT_DATA_DIR /root/tarolog/.env 2>/dev/null; pgrep -af 'main.py'
```

Ждём: одна строка `main.py`, папка `/root/tarolog`. Если `BOT_DATA_DIR` указывает
в другое место — в шагах 2–5 делать `cd` туда вместо `/root/tarolog`.
Две строки `main.py` — второй процесс, остановиться и сообщить.

## 2. Срок подписки во всех трёх местах (админ и Карина)

```bash
cd /root/tarolog && venv/bin/python -c 'import json,sqlite3;d=json.loads(sqlite3.connect("bot_state.sqlite3").execute("select payload from documents where name=?",("users",)).fetchone()[0]);u=json.load(open("user_data.json"));w=json.load(open("shared_wallet.json"));[print(k,"| sqlite:",d.get(k,{}).get("subscription_end"),"| json:",u.get(k,{}).get("subscription_end"),"| bind:",w["bind"].get("tg:"+k),"| wallet:",w["wallets"].get(w["bind"].get("tg:"+k) or "tg:"+k,{}).get("subscription_end")) for k in ("491482483","845342364")]'
```

Как читать:
- sqlite ≈ `2027-01-0x` → правка не записалась или её перекрыли (причина 1 или 3).
- sqlite ≈ `2026-12-07`, а в боте 59 → на сервере старый код, смотреть `wallet` (причина 2).
- `bind:` не `None` → кошелёк админа под другим ключом, это и есть промах.

## 3. Статус счетов обоих

```bash
venv/bin/python -c 'import json;d=json.load(open("robokassa_invoices.json"))["invoices"];[print(k,v.get("chat_id"),v.get("status"),"fulfilled=",v.get("fulfilled"),v.get("plan_key")) for k,v in d.items() if str(v.get("chat_id")) in ("491482483","845342364")]'
```

Ждём: InvId 20 → `845342364`, InvId 21 → `491482483`. Если у админа два `paid` — вот откуда 2 месяца.

## 4. Доходит ли ResultURL до DE (проверка причины A)

```bash
grep -h 'robokassa/result' /var/log/nginx/access.log* 2>/dev/null | tail -5; journalctl --since 2026-11-01 --no-pager | grep -i 'robokassa' | tail -15
```

- Ни одной строки `robokassa/result` → уведомления до DE не доходят (A подтверждена).
- Есть строки с кодом 200 → уведомления доходили, бот выдал месяц сам, а ручная выдача
  добавила второй. Тогда главная причина — двойная выдача (B), а не блокировка.
- Есть строки с 4xx/5xx → доходят, но обработчик падает (вопрос к коду, не к сети).

## 5. Исправление админа (только если в шаге 2 не `2026-12-07`)

5.1 Остановить бота (чтобы он не перезаписал правку из памяти):

```bash
systemctl stop tarolog
```

5.2 Копии файлов:

```bash
cd /root/tarolog && for f in bot_state.sqlite3 user_data.json shared_wallet.json; do cp -a "$f" "$f.bak-20261108"; done
```

5.3 Записать ровно одну дату во все три места (в кошелёк — по настоящему ключу):

```bash
venv/bin/python -c 'import json,sqlite3;E="2026-12-07 19:04:05";K="491482483";c=sqlite3.connect("bot_state.sqlite3");d=json.loads(c.execute("select payload from documents where name=?",("users",)).fetchone()[0]);d[K]["subscription_end"]=E;c.execute("update documents set payload=?,revision=revision+1 where name=?",(json.dumps(d,ensure_ascii=False,separators=(",",":")),"users"));c.commit();u=json.load(open("user_data.json"));u[K]["subscription_end"]=E;json.dump(u,open("user_data.json","w"),ensure_ascii=False,indent=2);w=json.load(open("shared_wallet.json"));ck=w["bind"].get("tg:"+K) or "tg:"+K;r=w["wallets"].get(ck);(r.__setitem__("subscription_end",E) if r else None);json.dump(w,open("shared_wallet.json","w"),ensure_ascii=False,indent=2);print("written, wallet key:",ck,"found:",bool(r))'
```

5.4 Запустить и перепроверить:

```bash
systemctl start tarolog; sleep 3; systemctl is-active tarolog; pgrep -af 'main.py'
```

Потом снова **шаг 2** — должно быть `2026-12-07` везде. Владелица открывает «🎁 Бонусы»
заново (новое сообщение, не старое). Ждём ~28.

Если опять 59 — значит, бот перезаписывает срок после старта: снова шаги 3–4 и
`journalctl -u tarolog --since "10 min ago" --no-pager | tail -40`.

## 6. Защита от повторного +31 (нужно «да» владелицы)

Если в шаге 3 у счетов админа `fulfilled=None` — повтор ResultURL снова прибавит месяц.
Пометить их выданными — это правка файла данных оплаты (не кода). Делать только с явного «да».

---

## Карина за 1 минуту

Шаг 2 (строка `845342364`) + шаг 3 (InvId 20):
- срок ≈ дата оплаты + 31 день, InvId 20 `paid` / `fulfilled=True` → всё в порядке;
- срок пустой или в прошлом, а InvId 20 `pending` → месяц ей не выдан. Выдавать тем же
  способом, что шаг 5 (стоп → копии → одна дата = время оплаты + 31 день → старт),
  только после «да» владелицы.
