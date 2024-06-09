from db.crud.crud_base import CRUDBase
from db.models import Match
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class CRUDMatch(CRUDBase):
    async def get_matches_by_tour(self, current_tour: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model).where(self.model.tour == current_tour)
        )
        return db_obj.scalars().first()


crud_match = CRUDMatch(Match)