from db.crud.crud_base import CRUDBase
from db.models import Match
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload


class CRUDMatch(CRUDBase):
    async def get_matches_by_tour(self, current_tour: int, tournament_id: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model).where(self.model.tour_id == current_tour, self.model.tournament_id == tournament_id).options(joinedload(self.model.match_predictions))
        )
        return db_obj.unique().scalars().all()
    
    async def get_match_by_id(
        self, match_id: int, session: AsyncSession
    ):
        db_obj = await session.execute(
            select(self.model).where(
                self.model.id == match_id
            )
        )
        return db_obj.scalars().first()
    



crud_match = CRUDMatch(Match)