from sqlalchemy import select
from db.crud.crud_base import CRUDBase
from db.models import Match, Player, Tournament
from sqlalchemy.orm import joinedload


class CRUDTournament(CRUDBase):
    async def get_tournament(self, id, session):
        result = await session.execute(
            select(self.model).where(self.model.id==id)
            .options(
                joinedload(self.model.user),
                joinedload(self.model.players).joinedload(Player.user),
                joinedload(self.model.players).joinedload(
                    Player.tournament_predictions
                ),
                joinedload(self.model.current_tour),
                joinedload(self.model.matches).joinedload(Match.tour),
            )
        )
        return result.scalars().first()


crud_tournament = CRUDTournament(Tournament)
