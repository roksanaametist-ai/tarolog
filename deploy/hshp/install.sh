#!/bin/bash
# Одноразовая установка Follow the Frensy на HSHP VPS.
# Запуск на сервере: sudo bash deploy/hshp/install.sh
set -euo pipefail

APP_DIR="/opt/targpt"
APP_USER="targpt"
REPO_URL="https://github.com/roksanaametist-ai/tarolog.git"
BRANCH="main"

echo "==> Пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx curl

echo "==> Пользователь ${APP_USER}"
id -u "${APP_USER}" &>/dev/null || useradd -r -m -s /bin/bash "${APP_USER}"
mkdir -p "${APP_DIR}/data"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "==> Клонирование репозитория"
if [ ! -d "${APP_DIR}/.git" ]; then
  sudo -u "${APP_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
  cd "${APP_DIR}"
  sudo -u "${APP_USER}" git fetch origin
  sudo -u "${APP_USER}" git checkout "${BRANCH}"
  sudo -u "${APP_USER}" git pull origin "${BRANCH}"
fi

echo "==> Python venv и зависимости"
sudo -u "${APP_USER}" bash -c "
  cd ${APP_DIR}
  python3 -m venv venv
  ./venv/bin/pip install -q --upgrade pip
  ./venv/bin/pip install -q -r requirements.txt
  ./venv/bin/pip install -q -r landing/requirements.txt
"

if [ ! -f "${APP_DIR}/.env" ]; then
  echo ""
  echo "!!! Создайте ${APP_DIR}/.env (скопируйте с локальной машины) и запустите снова:"
  echo "    nano ${APP_DIR}/.env"
  echo "    sudo bash ${APP_DIR}/deploy/hshp/install.sh"
  exit 1
fi

chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
chmod 600 "${APP_DIR}/.env"

# Дополняем пути данных, если не заданы
grep -q '^BOT_DATA_DIR=' "${APP_DIR}/.env" || echo "BOT_DATA_DIR=${APP_DIR}/data" >> "${APP_DIR}/.env"
grep -q '^LANDING_DATA_DIR=' "${APP_DIR}/.env" || echo "LANDING_DATA_DIR=${APP_DIR}/data" >> "${APP_DIR}/.env"

echo "==> Systemd"
cp "${APP_DIR}/deploy/hshp/targpt-bot.service" /etc/systemd/system/
cp "${APP_DIR}/deploy/hshp/targpt-landing.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable targpt-bot targpt-landing
systemctl restart targpt-bot targpt-landing

echo "==> Nginx (лендинг на /)"
NGINX_SITE="/etc/nginx/sites-available/followthefrensy.ru"
if [ -f "${NGINX_SITE}" ]; then
  if ! grep -q '127.0.0.1:5000' "${NGINX_SITE}"; then
    echo "Внимание: ${NGINX_SITE} уже существует. Добавьте вручную proxy на :5000 для /"
    echo "См. ${APP_DIR}/deploy/hshp/nginx-followthefrensy.conf"
  fi
else
  cp "${APP_DIR}/deploy/hshp/nginx-followthefrensy.conf" "${NGINX_SITE}"
  ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/followthefrensy.ru
  rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl reload nginx

echo ""
echo "==> Готово"
systemctl --no-pager status targpt-bot targpt-landing || true
curl -sf http://127.0.0.1:5000/health && echo " (landing OK)" || echo "landing health check failed"
echo "Проверьте: https://followthefrensy.ru/ и journalctl -u targpt-bot -n 20"
