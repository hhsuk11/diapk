from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.models.setting import AppSetting
from app.schemas.settings import AdminSettingsRead, AdminSettingsUpdate, PublicSettingsRead

DISCORD_URL_KEY = "discord_url"

router = APIRouter(prefix="/settings", tags=["settings"])
admin_router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


@router.get("", response_model=PublicSettingsRead)
def get_public_settings(db: Session = Depends(get_db)) -> PublicSettingsRead:
    return PublicSettingsRead(discord_url=get_setting_value(db, DISCORD_URL_KEY))


@admin_router.get("", response_model=AdminSettingsRead)
def get_admin_settings(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> AdminSettingsRead:
    return AdminSettingsRead(discord_url=get_setting_value(db, DISCORD_URL_KEY))


@admin_router.put("", response_model=AdminSettingsRead)
def update_admin_settings(
    payload: AdminSettingsUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> AdminSettingsRead:
    set_setting_value(db, DISCORD_URL_KEY, payload.discord_url)
    db.add(
        AuditLog(
            actor_email=principal.email,
            action="settings.update",
            entity_type="app_settings",
            entity_id=DISCORD_URL_KEY,
            details={"discord_url": payload.discord_url},
        )
    )
    db.commit()
    return AdminSettingsRead(discord_url=get_setting_value(db, DISCORD_URL_KEY))


def get_setting_value(db: Session, key: str) -> str | None:
    setting = db.get(AppSetting, key)
    return setting.value if setting is not None else None


def set_setting_value(db: Session, key: str, value: str | None) -> None:
    setting = db.get(AppSetting, key)
    if setting is None:
        db.add(AppSetting(key=key, value=value))
        return
    setting.value = value
