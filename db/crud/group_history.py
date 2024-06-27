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


crud_group_history = CRUDGroupHistory(GroupHistory)
