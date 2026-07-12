from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.core.time import utcnow
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.models.notice import Notice
from app.schemas.notices import NoticeCreate, NoticeRead, NoticeUpdate

router = APIRouter(prefix="/notices", tags=["notices"])
admin_router = APIRouter(prefix="/admin/notices", tags=["admin-notices"])


@router.get("", response_model=list[NoticeRead])
def list_public_notices(db: Session = Depends(get_db)) -> list[Notice]:
    return list(
        db.scalars(
            select(Notice)
            .where(
                Notice.deleted_at.is_(None),
                Notice.is_published.is_(True),
            )
            .order_by(
                desc(Notice.is_pinned),
                desc(Notice.published_at),
                desc(Notice.created_at),
            )
        ).all()
    )


@admin_router.get("", response_model=list[NoticeRead])
def list_admin_notices(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.NOTICE_MANAGE)),
) -> list[Notice]:
    return list(
        db.scalars(
            select(Notice)
            .where(Notice.deleted_at.is_(None))
            .order_by(
                desc(Notice.is_pinned),
                desc(Notice.published_at),
                desc(Notice.created_at),
            )
        ).all()
    )


@admin_router.post("", response_model=NoticeRead, status_code=status.HTTP_201_CREATED)
def create_notice(
    payload: NoticeCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.NOTICE_MANAGE)),
) -> Notice:
    now = utcnow()
    notice = Notice(
        title=payload.title.strip(),
        body=payload.body.strip(),
        is_published=payload.is_published,
        is_pinned=payload.is_pinned,
        published_at=now if payload.is_published else None,
        created_by_admin_id=principal.admin_user_id,
        updated_by_admin_id=principal.admin_user_id,
    )
    db.add(notice)
    db.flush()
    add_notice_audit(db, principal, "notice.create", notice)
    db.commit()
    db.refresh(notice)
    return notice


@admin_router.put("/{notice_id}", response_model=NoticeRead)
def update_notice(
    notice_id: int,
    payload: NoticeUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.NOTICE_MANAGE)),
) -> Notice:
    notice = get_notice_or_404(db, notice_id)
    was_published = notice.is_published

    if payload.title is not None:
        notice.title = payload.title.strip()
    if payload.body is not None:
        notice.body = payload.body.strip()
    if payload.is_published is not None:
        notice.is_published = payload.is_published
    if payload.is_pinned is not None:
        notice.is_pinned = payload.is_pinned

    if not was_published and notice.is_published:
        notice.published_at = utcnow()
    if not notice.is_published:
        notice.published_at = None
        notice.is_pinned = False

    notice.updated_by_admin_id = principal.admin_user_id
    add_notice_audit(db, principal, "notice.update", notice)
    db.commit()
    db.refresh(notice)
    return notice


@admin_router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.NOTICE_MANAGE)),
) -> None:
    notice = get_notice_or_404(db, notice_id)
    notice.deleted_at = utcnow()
    notice.updated_by_admin_id = principal.admin_user_id
    add_notice_audit(db, principal, "notice.delete", notice)
    db.commit()


def get_notice_or_404(db: Session, notice_id: int) -> Notice:
    notice = db.scalar(
        select(Notice).where(
            Notice.id == notice_id,
            Notice.deleted_at.is_(None),
        )
    )
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return notice


def add_notice_audit(
    db: Session,
    principal: Principal,
    action: str,
    notice: Notice,
) -> None:
    db.add(
        AuditLog(
            actor_email=principal.email,
            action=action,
            entity_type="notice",
            entity_id=str(notice.id),
            details={
                "title": notice.title,
                "is_published": notice.is_published,
                "is_pinned": notice.is_pinned,
            },
        )
    )
