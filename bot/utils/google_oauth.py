import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials

from bot.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TOKEN_FILE = PROJECT_ROOT / "credentials" / "google-token.json"


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def load_oauth_client() -> tuple[str, str]:
    config = load_config()
    if config.google.client_id and config.google.client_secret:
        return config.google.client_id, config.google.client_secret

    client_file = getattr(config.google, "oauth_client_file", None)
    if not client_file:
        env = __import__("environs").Env()
        env.read_env()
        client_file = env("GOOGLE_OAUTH_CLIENT_FILE", None)

    if client_file:
        path = _resolve_path(client_file)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            section = data.get("web") or data.get("installed") or {}
            client_id = section.get("client_id")
            client_secret = section.get("client_secret")
            if client_id and client_secret:
                return client_id, client_secret

    raise ValueError(
        "Укажите CLIENT_ID и GOGLE_SECRET_KEY в .env "
        "или GOOGLE_OAUTH_CLIENT_FILE с JSON из Google Cloud."
    )


def save_oauth_token(refresh_token: str) -> None:
    client_id, client_secret = load_oauth_client()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(
        json.dumps(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_refresh_token() -> str | None:
    config = load_config()
    if config.google.refresh_token:
        return config.google.refresh_token
    if TOKEN_FILE.exists():
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        return data.get("refresh_token")
    return None


def oauth_is_configured() -> bool:
    try:
        load_oauth_client()
    except ValueError:
        return False
    return load_refresh_token() is not None


def get_oauth_credentials(scopes: tuple[str, ...]) -> OAuthCredentials:
    client_id, client_secret = load_oauth_client()
    refresh_token = load_refresh_token()
    if not refresh_token:
        raise ValueError(
            "Один раз выполните: python scripts/google_oauth_setup.py\n"
            "Таблицы будут создаваться в вашем Google Drive — вы сможете их редактировать."
        )
    credentials = OAuthCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )
    credentials.refresh(Request())
    return credentials
