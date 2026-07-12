from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin
from app.models.enums import SeasonStatus


class Season(TimestampMixin, Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SeasonStatus.DRAFT.value)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scoring_rule_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("scoring_rule_versions.id"),
    )
    is_imported_snapshot: Mapped[bool] = mapped_column(Boolean, default=False)
    legacy_sheet_name: Mapped[str | None] = mapped_column(String(120))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_display_name: Mapped[str | None] = mapped_column(String(120))

    @property
    def display_name(self) -> str:
        return self.disabled_display_name or self.name
