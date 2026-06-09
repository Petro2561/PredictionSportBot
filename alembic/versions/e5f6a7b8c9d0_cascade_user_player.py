"""cascade delete player on user delete

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-09 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("player_user_id_fkey", "player", type_="foreignkey")
    op.create_foreign_key(
        "player_user_id_fkey",
        "player",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("player_user_id_fkey", "player", type_="foreignkey")
    op.create_foreign_key(
        "player_user_id_fkey",
        "player",
        "user",
        ["user_id"],
        ["id"],
    )
