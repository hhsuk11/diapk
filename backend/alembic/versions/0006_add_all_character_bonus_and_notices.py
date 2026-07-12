"""add all-character bonus and notices

Revision ID: 0006_add_all_character_bonus_and_notices
Revises: 0005_allow_in_progress_games
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_all_character_bonus_and_notices"
down_revision: str | None = "0005_allow_in_progress_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in set(inspector.get_table_names())


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    if not has_column("game_players", "is_all_character_bonus"):
        with op.batch_alter_table("game_players") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_all_character_bonus",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )

    if not has_table("notices"):
        op.create_table(
            "notices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            *timestamp_columns(),
            sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["updated_by_admin_id"], ["admin_users.id"]),
        )
        op.create_index("ix_notices_public", "notices", ["deleted_at", "is_published"])


def downgrade() -> None:
    if has_table("notices"):
        op.drop_index("ix_notices_public", table_name="notices")
        op.drop_table("notices")

    if has_column("game_players", "is_all_character_bonus"):
        with op.batch_alter_table("game_players") as batch_op:
            batch_op.drop_column("is_all_character_bonus")
