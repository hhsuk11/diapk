from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.db.session import get_db
from app.models.admin import AdminUser, PermissionGrant
from app.models.audit import AuditLog
from app.models.enums import ALL_PERMISSIONS, Permission
from app.schemas.admins import AdminPermissionUpdate, AdminUserRead

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=list[AdminUserRead])
def list_admin_users(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> list[AdminUserRead]:
    users = db.scalars(select(AdminUser).order_by(AdminUser.created_at.desc())).all()
    return [read_admin_user(db, user) for user in users]


@router.put("/{admin_user_id}/permissions", response_model=AdminUserRead)
def update_admin_permissions(
    admin_user_id: int,
    payload: AdminPermissionUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> AdminUserRead:
    admin_user = db.get(AdminUser, admin_user_id)
    if admin_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    requested_permissions = set(payload.permissions)
    unknown_permissions = requested_permissions - ALL_PERMISSIONS
    if unknown_permissions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown permissions: {', '.join(sorted(unknown_permissions))}",
        )

    active_grants = db.scalars(
        select(PermissionGrant).where(
            PermissionGrant.admin_user_id == admin_user.id,
            PermissionGrant.revoked_at.is_(None),
        )
    ).all()
    grant_by_permission = {grant.permission: grant for grant in active_grants}

    for grant in active_grants:
        if grant.permission not in requested_permissions:
            db.delete(grant)

    for permission in sorted(requested_permissions):
        if permission not in grant_by_permission:
            db.add(
                PermissionGrant(
                    admin_user_id=admin_user.id,
                    permission=permission,
                    granted_by_admin_id=principal.admin_user_id,
                )
            )

    admin_user.is_super = payload.is_super
    admin_user.disabled_at = None
    log_admin_user_action(
        db,
        principal,
        action="admin_user:permissions:update",
        admin_user=admin_user,
        details={"is_super": payload.is_super, "permissions": sorted(requested_permissions)},
    )
    db.commit()
    db.refresh(admin_user)
    return read_admin_user(db, admin_user)


@router.post("/{admin_user_id}/disable", response_model=AdminUserRead)
def disable_admin_user(
    admin_user_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> AdminUserRead:
    admin_user = db.get(AdminUser, admin_user_id)
    if admin_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")
    if principal.admin_user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot disable your own admin account",
        )

    from app.core.time import utcnow

    admin_user.disabled_at = utcnow()
    log_admin_user_action(
        db,
        principal,
        action="admin_user:disable",
        admin_user=admin_user,
        details={"email": admin_user.email},
    )
    db.commit()
    db.refresh(admin_user)
    return read_admin_user(db, admin_user)


@router.post("/{admin_user_id}/restore", response_model=AdminUserRead)
def restore_admin_user(
    admin_user_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> AdminUserRead:
    admin_user = db.get(AdminUser, admin_user_id)
    if admin_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found")

    admin_user.disabled_at = None
    log_admin_user_action(
        db,
        principal,
        action="admin_user:restore",
        admin_user=admin_user,
        details={"email": admin_user.email},
    )
    db.commit()
    db.refresh(admin_user)
    return read_admin_user(db, admin_user)


def read_admin_user(db: Session, admin_user: AdminUser) -> AdminUserRead:
    permissions = db.scalars(
        select(PermissionGrant.permission).where(
            PermissionGrant.admin_user_id == admin_user.id,
            PermissionGrant.revoked_at.is_(None),
        )
    ).all()
    return AdminUserRead(
        id=admin_user.id,
        email=admin_user.email,
        display_name=admin_user.display_name,
        is_super=admin_user.is_super,
        is_disabled=admin_user.disabled_at is not None,
        permissions=sorted(permissions),
        created_at=admin_user.created_at,
        updated_at=admin_user.updated_at,
    )


def log_admin_user_action(
    db: Session,
    principal: Principal,
    action: str,
    admin_user: AdminUser,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            actor_email=principal.email,
            action=action,
            entity_type="admin_user",
            entity_id=str(admin_user.id),
            details=details,
        )
    )
