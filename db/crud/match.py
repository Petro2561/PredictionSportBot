from db.crud.crud_base import CRUDBase
from db.models import Match
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload


class CRUDMatch(CRUDBase):
    async def get_matches_by_tour(self, current_tour: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model).where(self.model.tour == current_tour).options(joinedload(self.model.match_predictions))
        )
        return db_obj.unique().scalars().all()


crud_match = CRUDMatch(Match)