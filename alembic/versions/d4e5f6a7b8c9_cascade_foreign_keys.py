"""cascade delete on child foreign keys

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-08 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CASCADE_FKS = (
    ("match_prediction", "match_prediction_match_id_fkey", "match", ["match_id"], ["id"]),
    (
        "match_prediction",
        "match_prediction_player_id_fkey",
        "player",
        ["player_id"],
        ["id"],
    ),
    ("match", "match_tour_id_fkey", "tour", ["tour_id"], ["id"]),
    ("match", "match_tournament_id_fkey", "tournament", ["tournament_id"], ["id"]),
    ("player", "player_tournament_id_fkey", "tournament", ["tournament_id"], ["id"]),
    ("tour", "tour_tournament_id_fkey", "tournament", ["tournament_id"], ["id"]),
    (
        "tournament_prediction",
        "tournament_prediction_tournament_id_fkey",
        "tournament",
        ["tournament_id"],
        ["id"],
    ),
    (
        "tournament_prediction",
        "tournament_prediction_player_id_fkey",
        "player",
        ["player_id"],
        ["id"],
    ),
    (
        "group_history",
        "group_history_tournament_id_fkey",
        "tournament",
        ["tournament_id"],
        ["id"],
    ),
    (
        "reset_points",
        "reset_points_tournament_id_fkey",
        "tournament",
        ["tournament_id"],
        ["id"],
    ),
    ("reset_points", "reset_points_tour_id_fkey", "tour", ["tour_id"], ["id"]),
)


def _replace_fk(table, name, ref_table, local_cols, remote_cols, ondelete: str | None):
    op.drop_constraint(name, table, type_="foreignkey")
    op.create_foreign_key(
        name, table, ref_table, local_cols, remote_cols, ondelete=ondelete
    )


def upgrade() -> None:
    for table, name, ref_table, local_cols, remote_cols in _CASCADE_FKS:
        _replace_fk(table, name, ref_table, local_cols, remote_cols, ondelete="CASCADE")


def downgrade() -> None:
    for table, name, ref_table, local_cols, remote_cols in reversed(_CASCADE_FKS):
        _replace_fk(table, name, ref_table, local_cols, remote_cols, ondelete=None)
