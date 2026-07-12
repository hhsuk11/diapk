"""fix season rules and add one-way season disable

Revision ID: 0007_season_rules_and_disable
Revises: 0006_add_all_character_bonus_and_notices
Create Date: 2026-07-11
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0007_season_rules_and_disable"
down_revision: str | None = "0006_add_all_character_bonus_and_notices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_CONFIG = {
    "initial_score": 1000,
    "placement_game_count": 20,
    "placement_win_points": 20,
    "winner_k": 40,
    "loser_k": 40,
    "winner_expected_score_constant": 700,
    "loser_expected_score_constant": 1500,
    "all_character_bonus_ratio": 0.2,
    "loss_scale": 0.9,
    "tier_thresholds": {
        "마스터": 1600,
        "다이아": 1400,
        "플래티넘": 1250,
        "골드": 1100,
        "실버": 950,
    },
}


def has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not has_column("seasons", "disabled_at"):
        with op.batch_alter_table("seasons") as batch_op:
            batch_op.add_column(sa.Column("disabled_at", sa.DateTime(timezone=True)))
            batch_op.add_column(sa.Column("disabled_display_name", sa.String(length=120)))

    connection = op.get_bind()
    metadata = sa.MetaData()
    rules = sa.Table("scoring_rule_versions", metadata, autoload_with=connection)
    seasons = sa.Table("seasons", metadata, autoload_with=connection)
    legacy_rule_id = connection.scalar(
        sa.select(rules.c.id).where(rules.c.name == "Legacy Discord MMR").limit(1)
    )
    if legacy_rule_id is None:
        now = datetime.now(timezone.utc)
        result = connection.execute(
            rules.insert().values(
                name="Legacy Discord MMR",
                status="LOCKED",
                config=LEGACY_CONFIG,
                notes="Legacy GAS/Discord scoring rule assigned to historical seasons.",
                locked_at=now,
                activated_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        legacy_rule_id = result.inserted_primary_key[0]

    connection.execute(
        seasons.update()
        .where(seasons.c.status == "CLOSED")
        .values(scoring_rule_version_id=legacy_rule_id)
    )


def downgrade() -> None:
    if has_column("seasons", "disabled_at"):
        with op.batch_alter_table("seasons") as batch_op:
            batch_op.drop_column("disabled_display_name")
            batch_op.drop_column("disabled_at")
