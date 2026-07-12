from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.core.time import utcnow
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission, RuleStatus, SeasonStatus
from app.models.scoring import ScoringRuleVersion
from app.models.season import Season
from app.schemas.scoring import ScoringConfigRead
from app.schemas.seasons import SeasonCreate, SeasonRead, SeasonScoringRuleRead
from app.services.player_tiers import sync_player_tiers_from_latest_closed_season
from app.services.response_cache import clear_public_response_cache
from app.services.scoring import ScoreConfig
from app.services.scoring_rules import lock_current_rule_for_new_season

router = APIRouter(prefix="/seasons", tags=["seasons"])
admin_router = APIRouter(prefix="/admin/seasons", tags=["admin-seasons"])


@router.get("", response_model=list[SeasonRead])
def list_seasons(db: Session = Depends(get_db)) -> list[Season]:
    return list(
        db.scalars(
            select(Season)
            .where(Season.disabled_at.is_(None))
            .order_by(Season.sort_order.desc(), Season.id.desc())
        ).all()
    )


@admin_router.get("", response_model=list[SeasonRead])
def list_admin_seasons(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.SEASON_MANAGE)),
) -> list[Season]:
    stmt = select(Season)
    if not include_disabled:
        stmt = stmt.where(Season.disabled_at.is_(None))
    return list(db.scalars(stmt.order_by(Season.sort_order.desc(), Season.id.desc())).all())


@admin_router.get("/{season_id}/scoring-rule", response_model=SeasonScoringRuleRead)
def get_season_scoring_rule(
    season_id: int,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.SEASON_MANAGE)),
) -> SeasonScoringRuleRead:
    season = get_season_or_404(db, season_id)
    if season.scoring_rule_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="이 시즌에 저장된 MMR 규칙이 없습니다.",
        )
    rule = db.get(ScoringRuleVersion, season.scoring_rule_version_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시즌 MMR 규칙을 찾을 수 없습니다.",
        )
    return SeasonScoringRuleRead(
        season_id=season.id,
        season_name=season.display_name,
        rule_id=rule.id,
        rule_name=rule.name,
        config=ScoringConfigRead.model_validate(
            ScoreConfig.model_validate(rule.config).model_dump()
        ),
    )


@admin_router.post("", response_model=SeasonRead, status_code=status.HTTP_201_CREATED)
def create_season(
    payload: SeasonCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.SEASON_MANAGE)),
) -> Season:
    open_season = db.scalar(select(Season).where(Season.status == SeasonStatus.OPEN.value))
    if payload.open_immediately and open_season is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 열린 시즌이 있습니다: {open_season.name}",
        )

    name = (payload.name or next_season_name(db)).strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Season name is required",
        )

    existing = db.scalar(
        select(Season).where(Season.name == name, Season.disabled_at.is_(None))
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 존재하는 시즌입니다: {name}",
        )

    now = utcnow()
    season = Season(
        name=name,
        sort_order=season_sort_order(name, fallback=next_sort_order(db)),
        status=SeasonStatus.OPEN.value if payload.open_immediately else SeasonStatus.DRAFT.value,
        starts_at=now if payload.open_immediately else None,
        ends_at=None,
        scoring_rule_version_id=lock_current_rule_for_new_season(
            db, principal.admin_user_id
        ).id,
        is_imported_snapshot=False,
    )
    db.add(season)
    db.flush()
    if season.status == SeasonStatus.OPEN.value:
        sync_player_tiers_from_latest_closed_season(
            db,
            before_sort_order=season.sort_order,
        )
    add_season_audit(db, principal, "season.create", season, None)
    db.commit()
    clear_public_response_cache()
    db.refresh(season)
    return season


@admin_router.post("/{season_id}/open", response_model=SeasonRead)
def open_season(
    season_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.SEASON_MANAGE)),
) -> Season:
    season = get_season_or_404(db, season_id)
    ensure_season_enabled(season)
    if season.status == SeasonStatus.OPEN.value:
        return season

    latest_enabled_season_id = db.scalar(
        select(Season.id)
        .where(Season.disabled_at.is_(None))
        .order_by(Season.sort_order.desc(), Season.id.desc())
        .limit(1)
    )
    if season.id != latest_enabled_season_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="가장 최근 시즌만 다시 시작할 수 있습니다.",
        )

    open_season = db.scalar(
        select(Season).where(
            Season.status == SeasonStatus.OPEN.value,
            Season.id != season.id,
        )
    )
    if open_season is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 열린 시즌이 있습니다: {open_season.name}",
        )

    old_status = season.status
    season.status = SeasonStatus.OPEN.value
    season.starts_at = season.starts_at or utcnow()
    season.ends_at = None
    sync_player_tiers_from_latest_closed_season(
        db,
        before_sort_order=season.sort_order,
    )
    add_season_audit(db, principal, "season.open", season, old_status)
    db.commit()
    clear_public_response_cache()
    db.refresh(season)
    return season


@admin_router.post("/{season_id}/close", response_model=SeasonRead)
def close_season(
    season_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.SEASON_MANAGE)),
) -> Season:
    season = get_season_or_404(db, season_id)
    ensure_season_enabled(season)
    if season.status == SeasonStatus.CLOSED.value:
        return season

    old_status = season.status
    season.status = SeasonStatus.CLOSED.value
    season.ends_at = utcnow()
    add_season_audit(db, principal, "season.close", season, old_status)
    db.commit()
    clear_public_response_cache()
    db.refresh(season)
    return season


@admin_router.post("/{season_id}/disable", response_model=SeasonRead)
def disable_season(
    season_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.SEASON_MANAGE)),
) -> Season:
    if not principal.is_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a super administrator can disable a season",
        )
    season = get_season_or_404(db, season_id)
    if season.disabled_at is not None:
        return season
    if season.status == SeasonStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="진행중 시즌은 마감한 뒤 비활성화할 수 있습니다.",
        )

    original_name = season.display_name
    season.disabled_display_name = original_name
    season.name = f"{original_name} [disabled-{season.id}]"
    season.disabled_at = utcnow()
    add_season_audit(db, principal, "season.disable", season, season.status)
    db.commit()
    clear_public_response_cache()
    db.refresh(season)
    return season


def get_season_or_404(db: Session, season_id: int) -> Season:
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return season


def ensure_season_enabled(season: Season) -> None:
    if season.disabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="비활성화된 시즌은 변경할 수 없습니다.",
        )


def add_season_audit(
    db: Session,
    principal: Principal,
    action: str,
    season: Season,
    old_status: str | None,
) -> None:
    db.add(
        AuditLog(
            actor_email=principal.email,
            action=action,
            entity_type="season",
            entity_id=str(season.id),
            details={
                "season_name": season.name,
                "old_status": old_status,
                "new_status": season.status,
            },
        )
    )


def next_season_name(db: Session) -> str:
    return f"시즌{next_sort_order(db)}"


def next_sort_order(db: Session) -> int:
    max_sort_order = db.scalar(select(func.max(Season.sort_order))) or 0
    return max_sort_order + 1


def season_sort_order(name: str, fallback: int) -> int:
    digits = "".join(character for character in name if character.isdigit())
    return int(digits) if digits else fallback


def ensure_legacy_discord_rule(db: Session) -> ScoringRuleVersion:
    rule = db.scalar(
        select(ScoringRuleVersion).where(ScoringRuleVersion.name == "Legacy Discord MMR")
    )
    if rule is not None:
        return rule

    rule = ScoringRuleVersion(
        name="Legacy Discord MMR",
        status=RuleStatus.ACTIVE.value,
        config={
            "initial_score": 1000,
            "placement_game_count": 20,
            "placement_win_points": 20,
            "winner_k": 40,
            "loser_k": 40,
            "winner_expected_score_constant": 700,
            "loser_expected_score_constant": 1500,
            "all_character_bonus_ratio": 0.2,
            "loss_scale": 0.9,
        },
        notes="Python implementation of legacy 점수MMR_디스코드 rules.",
        activated_at=utcnow(),
    )
    db.add(rule)
    db.flush()
    return rule
