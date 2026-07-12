from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class Player(TimestampMixin, Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    current_tier: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    characters: Mapped[list["PlayerCharacter"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
    )


class PlayerCharacter(TimestampMixin, Base):
    __tablename__ = "player_characters"
    __table_args__ = (
        UniqueConstraint("player_id", "class_name", name="uq_player_characters_class"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    class_name: Mapped[str] = mapped_column(String(40), nullable=False)
    character_name: Mapped[str | None] = mapped_column(String(80))
    normalized_character_name: Mapped[str | None] = mapped_column(String(100))

    player: Mapped[Player] = relationship(back_populates="characters")
