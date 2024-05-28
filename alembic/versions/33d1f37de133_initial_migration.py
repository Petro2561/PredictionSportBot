"""Initial migration

Revision ID: 33d1f37de133
Revises: 
Create Date: 2024-05-28 22:51:57.169865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33d1f37de133'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('match',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('first_team_score', sa.Integer(), nullable=True),
    sa.Column('second_team_score', sa.Integer(), nullable=True),
    sa.Column('first_team', sa.String(), nullable=True),
    sa.Column('second_team', sa.String(), nullable=True),
    sa.Column('tour', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tournament',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('results_points', sa.Integer(), nullable=True),
    sa.Column('difference_points', sa.Integer(), nullable=True),
    sa.Column('competition_official_name', sa.String(), nullable=True),
    sa.Column('winner', sa.String(), nullable=True),
    sa.Column('best_striker', sa.String(), nullable=True),
    sa.Column('best_assistant', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('player',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=True),
    sa.Column('group', sa.String(), nullable=True),
    sa.Column('tournament_id', sa.Integer(), nullable=True),
    sa.Column('is_eliminated', sa.Boolean(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournament.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'tournament_id', name='_user_tournament_uc')
    )
    op.create_table('match_prediction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('first_team_score', sa.Integer(), nullable=True),
    sa.Column('second_team_score', sa.Integer(), nullable=True),
    sa.Column('match_id', sa.Integer(), nullable=True),
    sa.Column('player_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['match_id'], ['match.id'], ),
    sa.ForeignKeyConstraint(['player_id'], ['player.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('match_id', 'player_id', name='_match_player_uc')
    )
    op.create_table('tournament_prediction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('winner', sa.String(), nullable=True),
    sa.Column('best_striker', sa.String(), nullable=True),
    sa.Column('best_assistant', sa.String(), nullable=True),
    sa.Column('tournament_id', sa.Integer(), nullable=True),
    sa.Column('player_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['player.id'], ),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournament.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tournament_id', 'player_id', name='_tournament_player_uc')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('tournament_prediction')
    op.drop_table('match_prediction')
    op.drop_table('player')
    op.drop_table('user')
    op.drop_table('tournament')
    op.drop_table('match')
    # ### end Alembic commands ###
