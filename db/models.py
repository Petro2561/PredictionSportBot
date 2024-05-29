from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Player(Base):
    __tablename__ = 'player'
    id = Column(Integer, primary_key=True)
    points = Column(Integer)
    group = Column(String)
    tournament_id = Column(Integer, ForeignKey('tournament.id'))
    is_eliminated = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey('user.id'))

    user = relationship('User', back_populates='players')
    tournament = relationship('Tournament', back_populates='players')
    match_predictions = relationship('MatchPrediction', back_populates='player')
    tournament_predictions = relationship('TournamentPrediction', back_populates='player')

    __table_args__ = (UniqueConstraint('user_id', 'tournament_id', name='_user_tournament_uc'),)

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    name = Column(String)

    players = relationship('Player', back_populates='user')

class Tournament(Base):
    __tablename__ = 'tournament'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    results_points = Column(Integer)
    difference_points = Column(Integer, nullable=True)
    competition_official_name = Column(String, nullable=True)
    winner = Column(String, nullable=True)
    best_striker = Column(String, nullable=True)
    best_assistant = Column(String, nullable=True)

    players = relationship('Player', back_populates='tournament')
    tournament_predictions = relationship('TournamentPrediction', back_populates='tournament')

class Match(Base):
    __tablename__ = 'match'
    id = Column(Integer, primary_key=True)
    first_team_score = Column(Integer)
    second_team_score = Column(Integer)
    first_team = Column(String)
    second_team = Column(String)
    tour = Column(Integer)

    match_predictions = relationship('MatchPrediction', back_populates='match')

class MatchPrediction(Base):
    __tablename__ = 'match_prediction'
    id = Column(Integer, primary_key=True)
    first_team_score = Column(Integer)
    second_team_score = Column(Integer)
    match_id = Column(Integer, ForeignKey('match.id'))
    player_id = Column(Integer, ForeignKey('player.id'))
    points = Column(Integer, nullable=True)

    match = relationship('Match', back_populates='match_predictions')
    player = relationship('Player', back_populates='match_predictions')

    __table_args__ = (UniqueConstraint('match_id', 'player_id', name='_match_player_uc'),)

class TournamentPrediction(Base):
    __tablename__ = 'tournament_prediction'
    id = Column(Integer, primary_key=True)
    winner = Column(String, nullable=True)
    best_striker = Column(String, nullable=True)
    best_assistant = Column(String, nullable=True)
    tournament_id = Column(Integer, ForeignKey('tournament.id'))
    player_id = Column(Integer, ForeignKey('player.id'))

    tournament = relationship('Tournament', back_populates='tournament_predictions')
    player = relationship('Player', back_populates='tournament_predictions')

    __table_args__ = (UniqueConstraint('tournament_id', 'player_id', name='_tournament_player_uc'),)


if __name__ == '__main__':
    engine = create_engine('sqlite:///sqlite.db', echo=True)
    Base.metadata.create_all(engine)
