#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/prediction-sport-bot"
cd "$APP_DIR"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip redis-server

systemctl enable redis-server
systemctl start redis-server

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
if [ ! -f sqlite.db ]; then
  ./venv/bin/alembic upgrade head
else
  echo "sqlite.db уже есть — пропускаем alembic upgrade"
fi

install -m 644 deploy/systemd/prediction-bot.service /etc/systemd/system/prediction-bot.service
install -m 644 deploy/systemd/prediction-admin.service /etc/systemd/system/prediction-admin.service
systemctl daemon-reload
systemctl enable prediction-bot prediction-admin
systemctl restart prediction-bot prediction-admin
systemctl --no-pager status prediction-bot prediction-admin
