#!/usr/bin/env bash
# Починка исходящего трафика из Docker-контейнеров на VPS (Timeweb и др.)
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Запустите от root: sudo $0"
  exit 1
fi

echo "==> Включаем IP forwarding для Docker NAT"
sysctl -w net.ipv4.ip_forward=1
if ! grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf 2>/dev/null; then
  echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
fi

echo "==> Перезапуск Docker"
systemctl restart docker

echo "==> Пересоздание контейнеров"
cd "$(dirname "$0")/.."
docker compose down
docker compose up -d

echo "==> Проверка сети (бот в network_mode: host)"
sleep 3
docker compose exec -T bot python -c "
import urllib.request
print('status:', urllib.request.urlopen('https://api.telegram.org', timeout=15).status)
"
docker compose logs bot --tail=5
