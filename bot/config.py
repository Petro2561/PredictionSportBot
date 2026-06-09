from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    token: str
    admin_ids: list[int] | None


@dataclass
class WebApp:
    url: str
    port: int


@dataclass
class GoogleSheets:
    service_account_file: str | None
    drive_folder_id: str | None
    spreadsheet_id: str | None
    spreadsheet_sheet_name: str
    share_email: str | None
    skip_deadline_check: bool
    client_id: str | None
    client_secret: str | None
    refresh_token: str | None


@dataclass
class SqlAdmin:
    login: str
    password: str
    secret_key: str
    port: int


@dataclass
class Config:
    tg_bot: TgBot
    webapp: WebApp
    default_tournament_id: int
    google: GoogleSheets
    sql_admin: SqlAdmin


def load_config(path: str | None = None) -> Config:
    env = Env()
    # Переменные из docker-compose environment важнее .env (нужно для host network бота)
    env.read_env(path)
    return Config(
        tg_bot=TgBot(
            token=env("BOT_TOKEN"), admin_ids=list(map(int, env.list("ADMIN_IDS")))
        ),
        webapp=WebApp(
            url=env("WEBAPP_URL", "http://localhost:8080"),
            port=env.int("WEBAPP_PORT", 8080),
        ),
        default_tournament_id=env.int("DEFAULT_TOURNAMENT_ID", 1),
        google=GoogleSheets(
            service_account_file=env("GOOGLE_SERVICE_ACCOUNT_FILE", None),
            drive_folder_id=env("GOOGLE_DRIVE_FOLDER_ID", None),
            spreadsheet_id=env("GOOGLE_SPREADSHEET_ID", None),
            spreadsheet_sheet_name=env("GOOGLE_SPREADSHEET_SHEET_NAME", "Стадия 1"),
            share_email=env("GOOGLE_SHEETS_SHARE_EMAIL", None),
            skip_deadline_check=env.bool("GOOGLE_SHEETS_SKIP_DEADLINE", False),
            client_id=env("CLIENT_ID", None) or env("GOOGLE_CLIENT_ID", None),
            client_secret=env("GOGLE_SECRET_KEY", None)
            or env("GOOGLE_CLIENT_SECRET", None),
            refresh_token=env("GOOGLE_REFRESH_TOKEN", None),
        ),
        sql_admin=SqlAdmin(
            login=env("ADMIN_LOGIN", "admin"),
            password=env("ADMIN_PASSWORD", "admin"),
            secret_key=env("ADMIN_SECRET_KEY", "change-me-in-production"),
            port=env.int("ADMIN_PORT", 8000),
        ),
    )


def is_bot_admin(telegram_id: int) -> bool:
    config = load_config()
    return bool(config.tg_bot.admin_ids and telegram_id in config.tg_bot.admin_ids)
