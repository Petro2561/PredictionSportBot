"""move split_matches_by_groups from tournament to tour

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tour", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "split_matches_by_groups",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE tour
            SET split_matches_by_groups = (
                SELECT split_matches_by_groups
                FROM tournament
                WHERE tournament.id = tour.tournament_id
            )
            """
        )
    )

    with op.batch_alter_table("tournament", schema=None) as batch_op:
        batch_op.drop_column("split_matches_by_groups")


def downgrade() -> None:
    with op.batch_alter_table("tournament", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "split_matches_by_groups",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE tournament
            SET split_matches_by_groups = COALESCE(
                (
                    SELECT split_matches_by_groups
                    FROM tour
                    WHERE tour.id = tournament.current_tour_id
                ),
                1
            )
            """
        )
    )

    with op.batch_alter_table("tour", schema=None) as batch_op:
        batch_op.drop_column("split_matches_by_groups")
