from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud.crud_base import CRUDBase
from db.models import Player


class CRUDPlayer(CRUDBase):
    async def get_by_user_id(self, user_id: int, tournament_id: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model).where(self.model.user_id == user_id, self.model.tournament_id == tournament_id)
        )
        return db_obj.scalars().first()
    
crud_player = CRUDPlayer(Player)