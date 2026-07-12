"""allow in-progress games

Revision ID: 0005_allow_in_progress_games
Revises: 0004_reactivate_all_players
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_allow_in_progress_games"
down_revision: str | None = "0004_reactivate_all_players"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.alter_column("winner_side", existing_type=sa.String(length=1), nullable=True)
        batch_op.alter_column("score_a", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("score_b", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute(sa.text("UPDATE games SET winner_side = 'A' WHERE winner_side IS NULL"))
    op.execute(sa.text("UPDATE games SET score_a = 0 WHERE score_a IS NULL"))
    op.execute(sa.text("UPDATE games SET score_b = 0 WHERE score_b IS NULL"))
    with op.batch_alter_table("games") as batch_op:
        batch_op.alter_column("winner_side", existing_type=sa.String(length=1), nullable=False)
        batch_op.alter_column("score_a", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("score_b", existing_type=sa.Integer(), nullable=False)
