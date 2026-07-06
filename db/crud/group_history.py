from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud.crud_base import CRUDBase
from db.models import GroupHistory


class CRUDGroupHistory(CRUDBase):
    async def get_last_group_history(self, tournament_id: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model)
            .where(self.model.tournament_id == tournament_id)
            .order_by(self.model.id.desc())
        )
        return db_obj.scalars().first()

    async def get_group_history_by_draw_number(
        self, tournament_id: int, draw_number: int, session: AsyncSession
    ):
        """draw_number: 1 = первое распределение в турнире (по id), 2 = второе, …"""
        if draw_number < 1:
            return None
        db_obj = await session.execute(
            select(self.model)
            .where(self.model.tournament_id == tournament_id)
            .order_by(self.model.id.asc())
            .offset(draw_number - 1)
            .limit(1)
        )
        return db_obj.scalars().first()


crud_group_history = CRUDGroupHistory(GroupHistory)
