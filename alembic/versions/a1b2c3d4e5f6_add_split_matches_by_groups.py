"""add split_matches_by_groups to tournament

Revision ID: a1b2c3d4e5f6
Revises: 9c9acf6f4b1f
Create Date: 2026-05-29 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c9acf6f4b1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tournament", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "split_matches_by_groups",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tournament", schema=None) as batch_op:
        batch_op.drop_column("split_matches_by_groups")
