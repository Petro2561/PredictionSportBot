from fastapi import Request
from sqladmin.authentication import AuthenticationBackend

from bot.config import load_config

config = load_config()


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        if (
            form.get("username") == config.sql_admin.login
            and form.get("password") == config.sql_admin.password
        ):
            request.session.update({"token": config.sql_admin.secret_key})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("token"))
