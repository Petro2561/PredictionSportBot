#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NGROK_BIN="$ROOT_DIR/bin/ngrok"
ENV_FILE="$ROOT_DIR/.env"
PORT="${WEBAPP_PORT:-8080}"

if [[ ! -x "$NGROK_BIN" ]]; then
  echo "ngrok не найден. Скачайте: curl -L -o bin/ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-arm64.zip && unzip -o bin/ngrok.zip -d bin && chmod +x bin/ngrok"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Файл .env не найден"
  exit 1
fi

read_env() {
  local key="$1"
  grep -E "^${key}[[:space:]]*=" "$ENV_FILE" | head -1 | sed -E "s/^${key}[[:space:]]*=[[:space:]]*//" | sed 's/[[:space:]]*$//'
}

NGROK_AUTHTOKEN="$(read_env NGROK_AUTHTOKEN)"
WEBAPP_PORT="$(read_env WEBAPP_PORT)"

if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
  echo "Добавьте в .env токен ngrok:"
  echo "NGROK_AUTHTOKEN = ваш_токен"
  echo "Получить: https://dashboard.ngrok.com/get-started/your-authtoken"
  exit 1
fi

PORT="${WEBAPP_PORT:-8080}"

"$NGROK_BIN" config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true

if ! lsof -i :"$PORT" >/dev/null 2>&1; then
  echo "Порт $PORT свободен. Запустите бота: python main.py"
  exit 1
fi

if lsof -i :4040 >/dev/null 2>&1 || lsof -i :4041 >/dev/null 2>&1; then
  echo "ngrok уже запущен — читаю URL из локального API"
else
  echo "Запускаю ngrok http $PORT ..."
  nohup "$NGROK_BIN" http "$PORT" --log=stdout > /tmp/ngrok-prediction-bot.log 2>&1 &
  NGROK_PID=$!
  disown "$NGROK_PID" 2>/dev/null || true
fi

for _ in {1..20}; do
  sleep 0.5
  PUBLIC_URL="$(python3 -c "
import json, urllib.request
port = ${PORT}
for api_port in (4040, 4041, 4042):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{api_port}/api/tunnels', timeout=1) as r:
            data = json.loads(r.read().decode())
    except Exception:
        continue
    for t in data.get('tunnels', []):
        if t.get('proto') == 'https' and str(port) in t.get('config', {}).get('addr', ''):
            print(t['public_url'])
            raise SystemExit
" 2>/dev/null || true)"
  if [[ -n "$PUBLIC_URL" ]]; then
    break
  fi
done

if [[ -z "$PUBLIC_URL" ]]; then
  echo "Не удалось получить публичный URL. Лог: /tmp/ngrok-prediction-bot.log"
  kill "$NGROK_PID" 2>/dev/null || true
  exit 1
fi

if grep -q '^WEBAPP_URL' "$ENV_FILE"; then
  sed -i '' "s|^WEBAPP_URL = .*|WEBAPP_URL = $PUBLIC_URL|" "$ENV_FILE"
else
  echo "WEBAPP_URL = $PUBLIC_URL" >> "$ENV_FILE"
fi

echo ""
echo "Туннель готов:"
echo "  $PUBLIC_URL"
echo ""
echo "WEBAPP_URL обновлён в .env"
echo ""
echo "Важно: не закрывайте терминал с ngrok — иначе будет ERR_NGROK_3200 (endpoint offline)."
echo "Если туннель упал, запустите этот скрипт снова."
echo "Затем нажмите /start в боте (перезапуск бота не обязателен)."
if [[ -n "${NGROK_PID:-}" ]]; then
  echo "ngrok PID: $NGROK_PID (лог: /tmp/ngrok-prediction-bot.log)"
fi
