from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin
from app.models.enums import GameSource, GameStatus


class Game(TimestampMixin, Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    legacy_game_id: Mapped[str | None] = mapped_column(String(40))
    legacy_row_number: Mapped[int | None] = mapped_column(Integer)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(30), default=GameSource.MANUAL.value)
    status: Mapped[str] = mapped_column(String(20), default=GameStatus.ACTIVE.value)
    winner_side: Mapped[str | None] = mapped_column(String(1))
    score_a: Mapped[int | None] = mapped_column(Integer)
    score_b: Mapped[int | None] = mapped_column(Integer)
    scoring_rule_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("scoring_rule_versions.id")
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    players: Mapped[list["GamePlayer"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
    )


class GamePlayer(TimestampMixin, Base):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("game_id", "side", "slot", name="uq_game_players_side_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(1), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name_at_game: Mapped[str | None] = mapped_column(String(40))
    is_all_character_bonus: Mapped[bool] = mapped_column(Boolean, default=False)

    game: Mapped[Game] = relationship(back_populates="players")
