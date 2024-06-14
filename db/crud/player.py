from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from db.crud.crud_base import CRUDBase
from db.models import Match, MatchPrediction, Player


class CRUDPlayer(CRUDBase):
    async def get_by_user_id(self, user_id: int, tournament_id: int, session: AsyncSession):
        result = await session.execute(
            select(self.model)
            .filter_by(user_id=user_id, tournament_id=tournament_id)
            .options(
                selectinload(self.model.match_predictions).joinedload(MatchPrediction.match).joinedload(Match.tour)
            )
        )
        return result.scalars().first()


crud_player = CRUDPlayer(Player)
