"""reactivate all players

Revision ID: 0004_reactivate_all_players
Revises: 0003_drop_legacy_user_and_deactivate_low_games
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_reactivate_all_players"
down_revision: str | None = "0003_drop_legacy_user_and_deactivate_low_games"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE players SET is_active = 1"))


def downgrade() -> None:
    # Player activation is now managed manually; keep downgrade non-destructive.
    pass
