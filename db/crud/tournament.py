from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud.crud_base import CRUDBase
from db.models import Tournament


class CRUDTournament(CRUDBase):
    pass

crud_tournament = CRUDTournament(Tournament)