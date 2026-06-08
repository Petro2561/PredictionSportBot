"""Один раз: вход в Google. Таблицы потом создаются в вашем Drive с правом редактирования."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environs import Env
from google_auth_oauthlib.flow import InstalledAppFlow

from bot.utils.google_oauth import save_oauth_token

SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _pick_redirect_uri(redirect_uris: list[str], port: int) -> str | None:
    preferred = [
        f"http://localhost:{port}/",
        f"http://127.0.0.1:{port}/",
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
        "http://localhost/",
        "http://localhost",
        "http://127.0.0.1/",
        "http://127.0.0.1",
    ]
    for candidate in preferred:
        if candidate in redirect_uris:
            return candidate
    for uri in redirect_uris:
        if "localhost" in uri or "127.0.0.1" in uri:
            return uri
    return redirect_uris[0] if redirect_uris else None


def _parse_port_from_redirect(redirect_uri: str, default: int) -> int:
    match = re.search(r":(\d+)", redirect_uri)
    return int(match.group(1)) if match else default


def _load_client_config() -> tuple[dict, str, int, str, str]:
    env = Env()
    env.read_env(PROJECT_ROOT / ".env")

    port = env.int("GOOGLE_OAUTH_PORT", 8090)
    client_type = env("GOOGLE_OAUTH_CLIENT_TYPE", "installed")
    redirect_override = env("GOOGLE_OAUTH_REDIRECT_URI", None)

    client_file = env(
        "GOOGLE_OAUTH_CLIENT_FILE",
        str(PROJECT_ROOT / "credentials" / "google-oauth-client.json"),
    )
    path = Path(client_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    client_id = env("CLIENT_ID", None) or env("GOOGLE_CLIENT_ID", None)
    client_secret = env("GOGLE_SECRET_KEY", None) or env("GOOGLE_CLIENT_SECRET", None)

    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if "web" in raw:
            client_type = "web"
        elif "installed" in raw:
            client_type = "installed"
        section = raw.get(client_type) or raw.get("web") or raw.get("installed") or {}
        client_id = section.get("client_id", client_id)
        client_secret = section.get("client_secret", client_secret)
        file_redirects = section.get("redirect_uris", [])
        redirect_uri = (
            redirect_override
            or _pick_redirect_uri(file_redirects, port)
            or f"http://localhost:{port}/"
        )
        port = _parse_port_from_redirect(redirect_uri, port)
        return raw, redirect_uri, port, client_type, client_id or ""

    if not client_id or not client_secret:
        raise SystemExit(
            "В .env укажите CLIENT_ID и GOGLE_SECRET_KEY,\n"
            "или скачайте JSON из Google Cloud → credentials/google-oauth-client.json"
        )

    redirect_uri = redirect_override or f"http://localhost:{port}/"
    section = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": [
            redirect_uri,
            f"http://127.0.0.1:{port}/",
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        ],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return {client_type: section}, redirect_uri, port, client_type, client_id


def _print_setup_help(client_id: str, redirect_uri: str, port: int, client_type: str) -> None:
    print("=" * 60)
    print("НАСТРОЙКА GOOGLE OAUTH")
    print("=" * 60)
    print(f"\nВаш CLIENT_ID:\n  {client_id}\n")
    print(f"Тип клиента в скрипте: {client_type}")
    print(f"Redirect URI запроса:\n  {redirect_uri}\n")

    if client_type == "web":
        print("У вас Web application — URI нужно добавить вручную:\n")
        print("  1. https://console.cloud.google.com/apis/credentials")
        print("  2. Откройте OAuth client с CLIENT_ID выше")
        print("  3. Authorized redirect URIs → добавьте ТОЧНО:")
        print(f"       {redirect_uri}")
        print(f"       http://127.0.0.1:{port}/")
        print("  4. SAVE → подождите 1–2 минуты")
        print("  5. (рекомендуется) Download JSON → credentials/google-oauth-client.json\n")
        input("Когда URI сохранён в Google Console, нажмите Enter...")
    else:
        print("Desktop app — redirect URI регистрировать обычно не нужно.\n")
        print("Если ошибка останется — создайте новый OAuth client:")
        print("  Google Cloud → Create credentials → OAuth client ID → Desktop app")
        print("  Обновите CLIENT_ID и GOGLE_SECRET_KEY в .env")
        print("  GOOGLE_OAUTH_CLIENT_TYPE = installed\n")


def main() -> None:
    raw_config, redirect_uri, port, client_type, client_id = _load_client_config()
    _print_setup_help(client_id, redirect_uri, port, client_type)

    flow = InstalledAppFlow.from_client_config(
        raw_config,
        SCOPES,
        redirect_uri=redirect_uri,
    )

    try:
        credentials = flow.run_local_server(
            port=port,
            redirect_uri_trailing_slash=redirect_uri.endswith("/"),
            open_browser=True,
        )
    except OSError:
        raise SystemExit(
            f"Порт {port} занят. Укажите в .env другой: GOOGLE_OAUTH_PORT=8091"
        ) from None
    except Exception as error:
        if "redirect_uri_mismatch" in str(error).lower():
            raise SystemExit(
                f"\nredirect_uri_mismatch для {redirect_uri}\n"
                "Добавьте этот URI в Google Console для CLIENT_ID:\n"
                f"  {client_id}\n"
                "Или создайте OAuth client типа Desktop app (проще)."
            ) from error
        print(f"Автовход не удался ({error}). Ручной режим:\n")
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        print(auth_url)
        response = input("\nВставьте URL из адресной строки после входа: ").strip()
        code = (
            response.split("code=", 1)[1].split("&", 1)[0]
            if "code=" in response
            else response
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

    if not credentials.refresh_token:
        raise SystemExit(
            "Refresh token не выдан. Удалите доступ на "
            "https://myaccount.google.com/permissions и запустите снова."
        )

    save_oauth_token(credentials.refresh_token)
    print("\nГотово: credentials/google-token.json")
    print("Перезапустите бота. Таблицы — в вашем Google Drive, можно редактировать.")


if __name__ == "__main__":
    main()
