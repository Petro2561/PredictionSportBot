from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.crud.crud_base import CRUDBase
from db.models import MatchPrediction


class CRUDMatchPrediction(CRUDBase):
    async def get_match_prediction_by_match_id_and_player_id(
        self, match_id: int, player_id: int, session: AsyncSession
    ):
        db_obj = await session.execute(
            select(self.model).where(
                self.model.match_id == match_id, self.model.player_id == player_id
            )
        )
        return db_obj.scalars().first()


crud_match_prediction = CRUDMatchPrediction(MatchPrediction)
