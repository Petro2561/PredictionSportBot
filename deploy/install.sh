#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/prediction-sport-bot"
REPO_URL="https://github.com/Petro2561/PredictionSportBot.git"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip redis-server

systemctl enable redis-server
systemctl start redis-server

if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  cd "$APP_DIR"
  git pull --ff-only origin main
fi

cd "$APP_DIR"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/alembic upgrade head

install -m 644 deploy/systemd/prediction-bot.service /etc/systemd/system/prediction-bot.service
install -m 644 deploy/systemd/prediction-admin.service /etc/systemd/system/prediction-admin.service
systemctl daemon-reload
systemctl enable prediction-bot prediction-admin

echo "Установка завершена. Проверьте $APP_DIR/.env и credentials/, затем:"
echo "  systemctl restart prediction-bot prediction-admin"
