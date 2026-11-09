# Откат: бот Москва ↔ Германия (2026-11-05)

## Сейчас цель переключения
- Живой бот → **Москва** `153.76.169.102` (`/opt/targpt`, `tarolog`)
- Германия `37.46.18.192` (`/root/tarolog`) — сайт/карты, бот **остановлен**

## Быстрый откат на Германию

### 1) Москва — остановить бота
```bash
ssh -i C:\Users\roxan\.ssh\id_ed25519_hshp root@153.76.169.102
systemctl stop tarolog
systemctl disable tarolog   # опционально, чтобы не поднялся после ребута
systemctl is-active tarolog   # ожидаем: inactive
```

### 2) Германия — через VNC HSHP (SSH из РФ может не пройти из‑за РКН)
```bash
systemctl start tarolog
systemctl enable tarolog
systemctl is-active tarolog
journalctl -u tarolog -n 20 --no-pager
```
В логе должно быть `Start polling` / `Run polling`, без `Conflict`.

### 3) Прокси на Москве (вернуть как было, если меняли)
В `/opt/targpt/.env` снова:
```
TELEGRAM_PROXY=socks5://37.46.18.192:1080
```
(или значение из бэкапа `/opt/targpt/.env.bak-before-msk-cutover-*`)

### 4) ResultURL Robokassa
Если меняли на Москву — вернуть в кабинете / `.env`:
```
ROBOKASSA_RESULT_URL=https://followthefrensy.ru/robokassa/result
```
(пока DNS на Германии — колбэки снова могут не доходить при блоке IP.)

## Бэкапы, сделанные при cutover
- Москва: `/opt/targpt/.env.bak-before-msk-cutover-20261105`
- Москва rollback doc: `/root/ROLLBACK-MSK-BOT.md`
- Локально: `C:\Users\roxan\Projects\TarGPT3\ROLLBACK-MSK-BOT.md`
- Германия: не трогать код; только `systemctl stop/start tarolog`

## DNS (важно для ResultURL)
- До cutover A `followthefrensy.ru` → `37.46.18.192` (DE)
- После cutover A должен смотреть на `153.76.169.102` (MSK), иначе колбэки Robokassa снова упрутся в блок
- Откат DNS: вернуть A на `37.46.18.192`

## Проверка после отката
1. Написать боту в Telegram — ответ есть.
2. `systemctl is-active tarolog` на DE = active, на MSK = inactive.
3. В логах DE нет `Conflict: terminated by other getUpdates`.
