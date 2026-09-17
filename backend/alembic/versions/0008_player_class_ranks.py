"""add player class ranks

Revision ID: 0008_player_class_ranks
Revises: 0007_season_rules_and_disable
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_player_class_ranks"
down_revision: str | None = "0007_season_rules_and_disable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("player_characters") as batch_op:
        batch_op.add_column(sa.Column("class_rank", sa.String(length=1), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("player_characters") as batch_op:
        batch_op.drop_column("class_rank")
