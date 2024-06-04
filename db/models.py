from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.db import Base


class Player(Base):
    __tablename__ = "player"
    id = Column(Integer, primary_key=True)
    points = Column(Integer, default=0)
    group = Column(String, nullable=True)
    tournament_id = Column(Integer, ForeignKey("tournament.id"), nullable=False)
    is_eliminated = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)

    user = relationship("User", back_populates="players")
    match_predictions = relationship("MatchPrediction", back_populates="player")
    tournament_predictions = relationship(
        "TournamentPrediction", back_populates="player"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "tournament_id", name="_user_tournament_uc"),
    )


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    name = Column(String)
    telegram_id = Column(Integer, unique=True)

    players = relationship("Player", back_populates="user")
    tournaments = relationship("Tournament", back_populates="user")


class Tournament(Base):
    __tablename__ = "tournament"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    exact_score_points = Column(Integer, nullable=True)
    results_points = Column(Integer, nullable=True)
    difference_points = Column(Integer, nullable=True)
    competition_official_name = Column(String, nullable=True)
    winner = Column(Boolean, nullable=True)
    best_striker = Column(Boolean, nullable=True)
    best_assistant = Column(Boolean, nullable=True)
    next_deadline = Column(DateTime, nullable=True)
    end_of_next_tour = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)

    user = relationship("User", back_populates="tournaments")
    tournament_predictions = relationship(
        "TournamentPrediction", back_populates="tournament"
    )


class Match(Base):
    __tablename__ = "match"
    id = Column(Integer, primary_key=True)
    first_team_score = Column(Integer)
    second_team_score = Column(Integer)
    first_team = Column(String, nullable=False)
    second_team = Column(String, nullable=False)
    tour = Column(Integer, nullable=False)

    match_predictions = relationship("MatchPrediction", back_populates="match")


class MatchPrediction(Base):
    __tablename__ = "match_prediction"
    id = Column(Integer, primary_key=True)
    first_team_score = Column(Integer, nullable=False)
    second_team_score = Column(Integer, nullable=False)
    match_id = Column(Integer, ForeignKey("match.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("player.id"), nullable=False)
    points = Column(Integer, nullable=True)

    match = relationship("Match", back_populates="match_predictions")
    player = relationship("Player", back_populates="match_predictions")

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="_match_player_uc"),
    )


class TournamentPrediction(Base):
    __tablename__ = "tournament_prediction"
    id = Column(Integer, primary_key=True)
    winner = Column(String, nullable=True)
    best_striker = Column(String, nullable=True)
    best_assistant = Column(String, nullable=True)
    tournament_id = Column(Integer, ForeignKey("tournament.id"))
    player_id = Column(Integer, ForeignKey("player.id"))

    tournament = relationship("Tournament", back_populates="tournament_predictions")
    player = relationship("Player", back_populates="tournament_predictions")

    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id", name="_tournament_player_uc"),
    )
