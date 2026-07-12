from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.admin import AdminUser, PermissionGrant
from app.models.enums import ALL_PERMISSIONS, Permission


@dataclass(frozen=True)
class Principal:
    email: str | None
    is_authenticated: bool
    is_super: bool
    permissions: frozenset[str]
    admin_user_id: int | None = None

    def can(self, permission: Permission | str) -> bool:
        permission_value = permission.value if isinstance(permission, Permission) else permission
        return self.is_super or permission_value in self.permissions


def get_current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    if settings.auth_mode == "dev":
        admin_user = db.scalar(select(AdminUser).where(AdminUser.email == settings.dev_admin_email))
        if admin_user is None:
            admin_user = AdminUser(
                email=settings.dev_admin_email,
                display_name="Local Admin",
                is_super=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        elif not admin_user.is_super or admin_user.disabled_at is not None:
            admin_user.is_super = True
            admin_user.disabled_at = None
            db.commit()
            db.refresh(admin_user)
        return Principal(
            email=admin_user.email,
            is_authenticated=True,
            is_super=True,
            permissions=ALL_PERMISSIONS,
            admin_user_id=admin_user.id,
        )

    session_user = request.session.get("user")
    if not isinstance(session_user, dict):
        return Principal(
            email=None, is_authenticated=False, is_super=False, permissions=frozenset()
        )

    email = str(session_user.get("email") or "").strip().lower()
    if not email:
        return Principal(
            email=None, is_authenticated=False, is_super=False, permissions=frozenset()
        )
    return load_admin_principal(email, db)


def load_admin_principal(email: str, db: Session) -> Principal:
    admin_user = db.scalar(select(AdminUser).where(AdminUser.email == email))
    if admin_user is None or admin_user.disabled_at is not None:
        return Principal(
            email=email, is_authenticated=True, is_super=False, permissions=frozenset()
        )

    grants = db.scalars(
        select(PermissionGrant.permission).where(
            PermissionGrant.admin_user_id == admin_user.id,
            PermissionGrant.revoked_at.is_(None),
        )
    ).all()
    return Principal(
        email=admin_user.email,
        is_authenticated=True,
        is_super=admin_user.is_super,
        permissions=frozenset(grants),
        admin_user_id=admin_user.id,
    )


def require_permission(permission: Permission) -> Callable[[Principal], Principal]:
    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.is_authenticated or not principal.can(permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return principal

    return dependency
