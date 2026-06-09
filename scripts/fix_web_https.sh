#!/usr/bin/env bash
# Запускать на сервере из корня проекта: bash scripts/fix_web_https.sh
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=".env"
HTTP_URL="http://87.249.44.152"
HTTPS_URL="https://87-249-44-152.sslip.io"

read_env() {
  grep -E "^${1}[[:space:]]*=" "$ENV_FILE" 2>/dev/null | head -1 | sed -E "s/^${1}[[:space:]]*=[[:space:]]*//" | tr -d ' '
}

set_webapp_url() {
  local url="$1"
  if grep -qE '^WEBAPP_URL[[:space:]]*=' "$ENV_FILE"; then
    sed -i "s|^WEBAPP_URL[[:space:]]*=.*|WEBAPP_URL = ${url}|" "$ENV_FILE"
  else
    echo "WEBAPP_URL = ${url}" >>"$ENV_FILE"
  fi
}

echo "=== 1. WEBAPP_URL → HTTP (компьютер) ==="
set_webapp_url "$HTTP_URL"
grep WEBAPP_URL "$ENV_FILE"
docker compose up -d --force-recreate bot

echo
echo "=== 2. Проверка HTTP ==="
curl -sS -D - -o /dev/null --max-time 5 "$HTTP_URL/" | head -5
curl -sS -D - -o /dev/null --max-time 5 "$HTTP_URL/p/test" | head -3

echo
echo "=== 3. Сброс сертификатов Caddy и перезапуск ==="
docker compose stop web
rm -rf caddy_data caddy_config
docker compose up -d web
echo "Ждём выдачу сертификата (до 60 с)..."
for i in $(seq 1 12); do
  sleep 5
  if curl -sS --max-time 5 "$HTTPS_URL/" >/dev/null 2>&1; then
    echo "HTTPS отвечает."
    break
  fi
  echo "  попытка $i/12..."
done

echo
echo "=== 4. Логи Caddy (последние 30 строк) ==="
docker compose logs web --tail=30

echo
if curl -sS --max-time 8 "$HTTPS_URL/" >/dev/null 2>&1; then
  echo "=== 5. HTTPS работает → WEBAPP_URL для телефона ==="
  set_webapp_url "$HTTPS_URL"
  docker compose up -d --force-recreate bot
  grep WEBAPP_URL "$ENV_FILE"
  echo "Готово. Нажмите «Сделать прогноз» в боте заново."
else
  echo "=== 5. HTTPS пока не работает ==="
  echo "Оставлен WEBAPP_URL = $HTTP_URL (компьютер: откройте ссылку в Chrome)."
  echo "Телефон: Telegram не открывает http:// — нужен HTTPS."
  echo "Проверьте в панели Timeweb, что порты 80 и 443 открыты для VPS."
  echo "Повторите: docker compose logs web --tail=50"
fi
