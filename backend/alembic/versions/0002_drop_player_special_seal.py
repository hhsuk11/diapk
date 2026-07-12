"""drop player special seal

Revision ID: 0002_drop_player_special_seal
Revises: 0001_initial_schema
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_drop_player_special_seal"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not has_column("players", "special_seal"):
        return

    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("special_seal")


def downgrade() -> None:
    if has_column("players", "special_seal"):
        return

    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(
            sa.Column("special_seal", sa.Boolean(), nullable=False, server_default=sa.false())
        )
