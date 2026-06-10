#!/usr/bin/env bash
# Проверка доступа VPS к Telegram API. Запуск: bash scripts/check_telegram_network.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== curl api.telegram.org ==="
curl -4 -sS -o /dev/null -w "IPv4: HTTP %{http_code}, %{time_total}s\n" --max-time 15 https://api.telegram.org || echo "IPv4: FAIL"
curl -6 -sS -o /dev/null -w "IPv6: HTTP %{http_code}, %{time_total}s\n" --max-time 15 https://api.telegram.org 2>/dev/null || echo "IPv6: FAIL или недоступен"

echo
echo "=== getMe из контейнера бота ==="
docker compose exec -T bot python -c "
import asyncio
from bot.bot import main_bot

async def main():
    me = await main_bot.get_me()
    print('OK:', me.username, me.id)

asyncio.run(main())
" || echo "getMe: FAIL — бот не достучался до Telegram"

echo
echo "=== последние ошибки сети в логах ==="
docker compose logs bot --tail=30 2>&1 | grep -E "TelegramNetworkError|Failed to fetch|Сеть Telegram" | tail -10 || echo "(нет недавних ошибок)"
