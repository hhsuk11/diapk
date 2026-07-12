from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_super: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    permissions: Mapped[list["PermissionGrant"]] = relationship(
        back_populates="admin_user",
        foreign_keys="PermissionGrant.admin_user_id",
    )


class PermissionGrant(TimestampMixin, Base):
    __tablename__ = "permission_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(60), nullable=False)
    granted_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    admin_user: Mapped[AdminUser] = relationship(
        back_populates="permissions",
        foreign_keys=[admin_user_id],
    )
