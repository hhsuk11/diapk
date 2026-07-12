"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("is_super", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("email", name="uq_admin_users_email"),
    )

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column("current_tier", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamp_columns(),
        sa.UniqueConstraint("normalized_name", name="uq_players_normalized_name"),
    )

    op.create_table(
        "scoring_rule_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
    )

    op.create_table(
        "player_characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.String(length=40), nullable=False),
        sa.Column("character_name", sa.String(length=80), nullable=True),
        sa.Column("normalized_character_name", sa.String(length=100), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.UniqueConstraint("player_id", "class_name", name="uq_player_characters_class"),
    )

    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scoring_rule_version_id", sa.Integer(), nullable=True),
        sa.Column("is_imported_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("legacy_sheet_name", sa.String(length=120), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["scoring_rule_version_id"], ["scoring_rule_versions.id"]),
        sa.UniqueConstraint("name", name="uq_seasons_name"),
    )

    op.create_table(
        "permission_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=60), nullable=False),
        sa.Column("granted_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["granted_by_admin_id"], ["admin_users.id"]),
    )
    op.create_index(
        "ix_permission_grants_active",
        "permission_grants",
        ["admin_user_id", "permission", "revoked_at"],
    )

    op.create_table(
        "games",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("legacy_game_id", sa.String(length=40), nullable=True),
        sa.Column("legacy_row_number", sa.Integer(), nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("winner_side", sa.String(length=1), nullable=True),
        sa.Column("score_a", sa.Integer(), nullable=True),
        sa.Column("score_b", sa.Integer(), nullable=True),
        sa.Column("scoring_rule_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["scoring_rule_version_id"], ["scoring_rule_versions.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
        sa.UniqueConstraint("source", "legacy_row_number", name="uq_games_legacy_import_row"),
    )
    op.create_index("ix_games_legacy_game_id", "games", ["legacy_game_id"])
    op.create_index("ix_games_season_played_at", "games", ["season_id", "played_at"])

    op.create_table(
        "game_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.String(length=36), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=1), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("class_name_at_game", sa.String(length=40), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.UniqueConstraint("game_id", "side", "slot", name="uq_game_players_side_slot"),
    )

    op.create_table(
        "rating_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.String(length=36), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("before_score", sa.Integer(), nullable=False),
        sa.Column("after_score", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
    )
    op.create_index("ix_rating_events_player_season", "rating_events", ["player_id", "season_id"])

    op.create_table(
        "season_player_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("games_played", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("tier", sa.String(length=40), nullable=True),
        sa.Column("is_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
        sa.UniqueConstraint("season_id", "player_id", name="uq_season_player_stats_player"),
    )

    op.create_table(
        "season_player_class_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.String(length=40), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("is_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"]),
        sa.UniqueConstraint(
            "season_id",
            "player_id",
            "class_name",
            name="uq_season_player_class_stats_player",
        ),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("season_player_class_stats")
    op.drop_table("season_player_stats")
    op.drop_index("ix_rating_events_player_season", table_name="rating_events")
    op.drop_table("rating_events")
    op.drop_table("game_players")
    op.drop_index("ix_games_season_played_at", table_name="games")
    op.drop_index("ix_games_legacy_game_id", table_name="games")
    op.drop_table("games")
    op.drop_index("ix_permission_grants_active", table_name="permission_grants")
    op.drop_table("permission_grants")
    op.drop_table("seasons")
    op.drop_table("player_characters")
    op.drop_table("scoring_rule_versions")
    op.drop_table("players")
    op.drop_table("admin_users")
