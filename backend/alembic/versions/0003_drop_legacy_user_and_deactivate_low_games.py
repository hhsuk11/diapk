"""drop legacy user id

Revision ID: 0003_drop_legacy_user_and_deactivate_low_games
Revises: 0002_drop_player_special_seal
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_drop_legacy_user_and_deactivate_low_games"
down_revision: str | None = "0002_drop_player_special_seal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if has_column("players", "legacy_user_id"):
        with op.batch_alter_table("players") as batch_op:
            batch_op.drop_column("legacy_user_id")


def downgrade() -> None:
    if not has_column("players", "legacy_user_id"):
        with op.batch_alter_table("players") as batch_op:
            batch_op.add_column(sa.Column("legacy_user_id", sa.String(length=120), nullable=True))
