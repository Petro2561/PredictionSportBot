"""SQLAdmin: uvicorn admin.main:app --reload --port 8000"""

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin import widgets as sqladmin_widgets
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.middleware.sessions import SessionMiddleware

# WTForms 3.x требует validation_attrs у Input-виджетов; sqladmin BooleanInputWidget без него.
if not getattr(sqladmin_widgets.BooleanInputWidget, "validation_attrs", None):
    sqladmin_widgets.BooleanInputWidget.validation_attrs = ["required", "disabled"]

from admin.helpers import get_player_label
from bot.config import load_config
from db.db import DATABASE_URL
from db.models import Match, Player, Tour, Tournament, TournamentPrediction, User

from .auth import AdminAuth

config = load_config()
engine = create_async_engine(DATABASE_URL, echo=False)

app = FastAPI(title="PredictionSportBot Admin")
app.add_middleware(SessionMiddleware, secret_key=config.sql_admin.secret_key)

admin = Admin(
    app=app,
    engine=engine,
    authentication_backend=AdminAuth(secret_key=config.sql_admin.secret_key),
)


def _format_model_id(model, attr) -> str:
    attr_name = attr.key if hasattr(attr, "key") else str(attr)
    value = getattr(model, attr_name, None)
    return f"#{value}" if value is not None else "—"


class TournamentAdmin(ModelView, model=Tournament):
    name = "Турнир"
    name_plural = "Турниры"
    icon = "fa-solid fa-trophy"

    column_list = [
        Tournament.id,
        Tournament.name,
        Tournament.current_tour_id,
        Tournament.exact_score_points,
        Tournament.results_points,
        Tournament.difference_points,
    ]
    column_searchable_list = [Tournament.name]
    column_sortable_list = [Tournament.id, Tournament.name, Tournament.current_tour_id]
    column_default_sort = [(Tournament.id, False)]

    form_columns = [
        Tournament.name,
        Tournament.current_tour,
        Tournament.exact_score_points,
        Tournament.results_points,
        Tournament.difference_points,
        Tournament.competition_official_name,
        Tournament.best_striker,
        Tournament.best_assistant,
        Tournament.telegram_group_id,
    ]

    form_ajax_refs = {
        "current_tour": {
            "fields": ["number"],
            "order_by": "number",
        },
    }

    column_formatters = {
        Tournament.current_tour_id: _format_model_id,
    }

    column_labels = {
        Tournament.name: "Название",
        Tournament.current_tour_id: "Текущий тур (ID)",
        Tournament.current_tour: "Текущий тур",
        Tournament.exact_score_points: "Очки за точный счёт",
        Tournament.results_points: "Очки за исход",
        Tournament.difference_points: "Очки за разницу",
        Tournament.competition_official_name: "Официальное название",
        Tournament.best_striker: "Собирать прогноз на бомбардира",
        Tournament.best_assistant: "Собирать прогноз на ассистента",
        Tournament.telegram_group_id: "ID группы Telegram",
    }


class TourAdmin(ModelView, model=Tour):
    name = "Тур"
    name_plural = "Туры"
    icon = "fa-solid fa-calendar"

    column_list = [
        Tour.id,
        Tour.number,
        Tour.tournament_id,
        Tour.next_deadline,
        Tour.split_matches_by_groups,
    ]
    column_searchable_list = [Tour.number]
    column_sortable_list = [Tour.id, Tour.number, Tour.next_deadline, Tour.tournament_id]
    column_default_sort = [(Tour.number, False)]

    form_columns = [
        Tour.tournament,
        Tour.number,
        Tour.next_deadline,
        Tour.split_matches_by_groups,
    ]

    form_ajax_refs = {
        "tournament": {
            "fields": ["name"],
            "order_by": "name",
        },
    }

    column_formatters = {
        Tour.tournament_id: _format_model_id,
    }

    column_labels = {
        Tour.number: "Номер тура",
        Tour.tournament_id: "Турнир (ID)",
        Tour.tournament: "Турнир",
        Tour.next_deadline: "Дедлайн / начало тура",
        Tour.split_matches_by_groups: "Делить матчи тура по группам",
    }


class MatchAdmin(ModelView, model=Match):
    name = "Матч"
    name_plural = "Матчи"
    icon = "fa-solid fa-futbol"

    column_list = [
        Match.id,
        Match.tournament_id,
        Match.tour_id,
        Match.first_team,
        Match.second_team,
        Match.first_team_score,
        Match.second_team_score,
    ]
    column_searchable_list = [Match.first_team, Match.second_team]
    column_sortable_list = [
        Match.id,
        Match.tour_id,
        Match.tournament_id,
        Match.first_team,
        Match.second_team,
    ]
    column_default_sort = [(Match.id, False)]

    form_columns = [
        Match.tournament,
        Match.tour,
        Match.first_team,
        Match.second_team,
        Match.first_team_score,
        Match.second_team_score,
    ]

    form_ajax_refs = {
        "tournament": {
            "fields": ["name"],
            "order_by": "name",
        },
        "tour": {
            "fields": ["number"],
            "order_by": "number",
        },
    }

    column_formatters = {
        Match.tournament_id: _format_model_id,
        Match.tour_id: _format_model_id,
    }

    column_labels = {
        Match.tournament_id: "Турнир (ID)",
        Match.tour_id: "Тур (ID)",
        Match.tournament: "Турнир",
        Match.tour: "Тур",
        Match.first_team: "Команда 1",
        Match.second_team: "Команда 2",
        Match.first_team_score: "Счёт 1",
        Match.second_team_score: "Счёт 2",
    }


class TournamentPredictionAdmin(ModelView, model=TournamentPrediction):
    name = "Прогноз турнира"
    name_plural = "Прогнозы турнира"
    icon = "fa-solid fa-star"

    column_list = [
        TournamentPrediction.id,
        TournamentPrediction.tournament_id,
        TournamentPrediction.player_id,
        TournamentPrediction.best_striker,
        TournamentPrediction.best_assistant,
    ]
    column_searchable_list = [
        TournamentPrediction.best_striker,
        TournamentPrediction.best_assistant,
    ]
    column_sortable_list = [
        TournamentPrediction.id,
        TournamentPrediction.tournament_id,
        TournamentPrediction.player_id,
    ]
    column_default_sort = [(TournamentPrediction.id, False)]

    form_columns = [
        TournamentPrediction.tournament_id,
        TournamentPrediction.player_id,
        TournamentPrediction.best_striker,
        TournamentPrediction.best_assistant,
    ]

    column_formatters = {
        TournamentPrediction.player_id: lambda model, _: get_player_label(
            model.player_id
        ),
        TournamentPrediction.tournament_id: _format_model_id,
    }

    column_labels = {
        TournamentPrediction.tournament_id: "Турнир (ID)",
        TournamentPrediction.player_id: "Игрок",
        TournamentPrediction.best_striker: "Бомбардир",
        TournamentPrediction.best_assistant: "Ассистент",
    }


class UserAdmin(ModelView, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
    can_create = False
    can_delete = False

    column_list = [User.id, User.name, User.username, User.telegram_id]
    column_searchable_list = [User.name, User.username]
    form_columns = [User.name, User.username, User.telegram_id]

    column_labels = {
        User.name: "Имя",
        User.username: "Username",
        User.telegram_id: "Telegram ID",
    }


class PlayerAdmin(ModelView, model=Player):
    name = "Игрок"
    name_plural = "Игроки"
    icon = "fa-solid fa-users"
    can_create = False
    can_delete = False

    column_list = [
        Player.id,
        Player.tournament_id,
        Player.group,
        Player.points,
        Player.is_eliminated,
    ]
    column_searchable_list = [Player.group]
    column_sortable_list = [Player.id, Player.points, Player.tournament_id]
    form_columns = [
        Player.group,
        Player.points,
        Player.is_eliminated,
    ]

    column_formatters = {
        Player.id: lambda model, _: get_player_label(model.id),
        Player.tournament_id: _format_model_id,
    }

    column_labels = {
        Player.id: "Игрок",
        Player.tournament_id: "Турнир (ID)",
        Player.group: "Группа",
        Player.points: "Очки",
        Player.is_eliminated: "Выбыл",
    }


admin.add_view(TournamentAdmin)
admin.add_view(TourAdmin)
admin.add_view(MatchAdmin)
admin.add_view(TournamentPredictionAdmin)
admin.add_view(PlayerAdmin)
admin.add_view(UserAdmin)
