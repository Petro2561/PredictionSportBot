import html
import json
import logging
from pathlib import Path

from aiohttp import web

from bot.bot import main_bot
from bot.utils.prediction_submit import save_player_predictions
from bot.webapp_sessions import get_latest_session_for_user, get_prediction_session

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"


def _read_webapp_asset(relative_path: str) -> str:
    return (WEBAPP_DIR / relative_path).read_text(encoding="utf-8")


def _default_score(value) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _render_matches_html(matches: list[dict]) -> str:
    if not matches:
        return (
            '<div class="empty-state">Матчи для прогноза не найдены.<br><br>'
            "Откройте форму через бота: /start → «Сделать прогноз» → «Открыть в браузере».<br>"
            "Не заходите на главную страницу ngrok вручную — нужна полная ссылка вида /p/...</div>"
        )

    cards: list[str] = []
    for index, match in enumerate(matches):
        home = html.escape(str(match.get("firstTeam", "")))
        away = html.escape(str(match.get("secondTeam", "")))
        home_score = _default_score(match.get("firstScore"))
        away_score = _default_score(match.get("secondScore"))
        cards.append(
            f'<section class="match-card" data-index="{index}">'
            f'<div class="match-number">Матч {index + 1}</div>'
            f'<h2 class="match-title">{home} — {away}</h2>'
            f'<div class="score-row">'
            f'<div class="score-field">'
            f'<label for="home-{index}">{home}</label>'
            f'<input id="home-{index}" type="number" min="0" max="99" '
            f'inputmode="numeric" value="{home_score}" placeholder="0" required />'
            f"</div>"
            f'<div class="score-separator">:</div>'
            f'<div class="score-field">'
            f'<label for="away-{index}">{away}</label>'
            f'<input id="away-{index}" type="number" min="0" max="99" '
            f'inputmode="numeric" value="{away_score}" placeholder="0" required />'
            f"</div></div><div class=\"error-text\"></div></section>"
        )
    return "".join(cards)


def _build_prediction_html(session_id: str, session: dict) -> str:
    matches = session.get("matches", [])
    content = (WEBAPP_DIR / "prediction.html").read_text(encoding="utf-8")
    matches_json = json.dumps(matches, ensure_ascii=False)
    content = content.replace(
        '<link rel="stylesheet" href="/css/form.css" />',
        f"<style>{_read_webapp_asset('css/form.css')}</style>",
    )
    content = content.replace(
        '<script src="https://telegram.org/js/telegram-web-app.js"></script>',
        '<script async src="https://telegram.org/js/telegram-web-app.js"></script>',
    )
    content = content.replace('<script src="/js/prediction.js"></script>', "")
    content = content.replace(
        '<div id="matches"></div>',
        f'<div id="matches">{_render_matches_html(matches)}</div>',
    )
    submit_disabled = "" if matches else " disabled"
    content = content.replace(
        '<button id="submit-btn" class="btn btn-primary" type="button">Отправить</button>',
        f'<button id="submit-btn" class="btn btn-primary" type="button"{submit_disabled}>Отправить</button>',
    )
    inject = (
        f'<script>window.__PREDICTION_SID__="{session_id}";'
        f"window.__PREDICTION_MATCHES__={matches_json};</script>"
        f"<script>{_read_webapp_asset('js/prediction.js')}</script>"
    )
    return content.replace("</body>", f"{inject}</body>")


async def _get_matches(request: web.Request) -> web.Response:
    session_id = request.rel_url.query.get("sid")
    telegram_id = request.rel_url.query.get("uid")
    session = None
    if session_id:
        session = get_prediction_session(session_id)
    elif telegram_id:
        try:
            matches = get_latest_session_for_user(int(telegram_id))
        except ValueError:
            return web.json_response({"error": "invalid uid"}, status=400)
        else:
            if matches is None:
                return web.json_response({"error": "session not found"}, status=404)
            return web.json_response(matches)
    else:
        return web.json_response({"error": "missing sid or uid"}, status=400)
    if session is None:
        return web.json_response({"error": "session not found"}, status=404)
    return web.json_response(session["matches"])


async def _submit_predictions(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "invalid json"}, status=400)

    session_id = body.get("sid")
    predictions = body.get("predictions")
    if not session_id or not isinstance(predictions, list):
        return web.json_response({"error": "missing sid or predictions"}, status=400)

    session = get_prediction_session(session_id)
    if session is None:
        return web.json_response({"error": "session not found"}, status=404)

    tournament_id = session.get("tournament_id")
    user_id = session.get("user_id")
    if not tournament_id or not user_id:
        return web.json_response({"error": "session incomplete"}, status=400)

    try:
        message = await save_player_predictions(tournament_id, user_id, predictions)
    except ValueError as error:
        return web.json_response({"error": str(error)}, status=400)
    except Exception:
        logger.exception("Failed to save predictions for session %s", session_id)
        return web.json_response({"error": "failed to save predictions"}, status=500)

    telegram_id = session.get("telegram_id")
    if telegram_id:
        try:
            await main_bot.send_message(telegram_id, message)
        except Exception:
            logger.exception("Failed to notify user %s in Telegram", telegram_id)

    return web.json_response({"ok": True, "message": message})


async def _prediction_page(request: web.Request) -> web.Response:
    session_id = request.match_info["sid"]
    session = get_prediction_session(session_id)
    if session is None:
        raise web.HTTPNotFound(text="Сессия прогноза не найдена или истекла")
    content = _build_prediction_html(session_id, session)
    logger.info(
        "Prediction page sid=%s user_id=%s matches=%s",
        session_id,
        session.get("user_id"),
        len(session.get("matches", [])),
    )
    return web.Response(text=content, content_type="text/html")


async def start_webapp_server(host: str = "0.0.0.0", port: int = 8080) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/api/matches", _get_matches)
    app.router.add_post("/api/predictions", _submit_predictions)
    app.router.add_get("/p/{sid}", _prediction_page)
    app.router.add_get("/", _redirect_to_prediction)
    app.router.add_static("/", WEBAPP_DIR, show_index=False)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("WebApp server started at http://%s:%s", host, port)
    return runner


async def _redirect_to_prediction(request: web.Request) -> web.Response:
    raise web.HTTPFound("/prediction.html")
