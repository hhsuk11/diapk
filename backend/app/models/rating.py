from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin


class RatingEvent(TimestampMixin, Base):
    __tablename__ = "rating_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    before_score: Mapped[int] = mapped_column(Integer, nullable=False)
    after_score: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)


class SeasonPlayerStats(TimestampMixin, Base):
    __tablename__ = "season_player_stats"
    __table_args__ = (
        UniqueConstraint("season_id", "player_id", name="uq_season_player_stats_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float)
    tier: Mapped[str | None] = mapped_column(String(40))
    is_snapshot: Mapped[bool] = mapped_column(Boolean, default=False)


class SeasonPlayerClassStats(TimestampMixin, Base):
    __tablename__ = "season_player_class_stats"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "player_id",
            "class_name",
            name="uq_season_player_class_stats_player",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    class_name: Mapped[str] = mapped_column(String(40), nullable=False)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float)
    is_snapshot: Mapped[bool] = mapped_column(Boolean, default=False)
