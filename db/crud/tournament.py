from sqlalchemy import select
from db.crud.crud_base import CRUDBase
from db.models import Match, MatchPrediction, Player, Tournament
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
                joinedload(self.model.players)
                .joinedload(Player.match_predictions)
                .joinedload(MatchPrediction.match),
                joinedload(self.model.current_tour),
                joinedload(self.model.matches).joinedload(Match.tour),
            )
        )
        return result.scalars().unique().first()


crud_tournament = CRUDTournament(Tournament)
