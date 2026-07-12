from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.models.scoring import ScoringRuleVersion
from app.schemas.scoring import ScoringConfigUpdate, ScoringRuleRead
from app.services.scoring import ScoreConfig
from app.services.scoring_rules import (
    current_rule_for_admin,
    editable_rule_for_update,
    open_season,
)

router = APIRouter(prefix="/admin/scoring-rule", tags=["admin-scoring-rule"])


@router.get("", response_model=ScoringRuleRead)
def get_scoring_rule(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.MMR_MANAGE)),
) -> ScoringRuleRead:
    rule = current_rule_for_admin(db)
    db.commit()
    return read_scoring_rule(db, rule)


@router.put("", response_model=ScoringRuleRead)
def update_scoring_rule(
    payload: ScoringConfigUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.MMR_MANAGE)),
) -> ScoringRuleRead:
    rule = editable_rule_for_update(db)

    config = ScoreConfig.model_validate(payload.model_dump()).model_dump()
    rule.config = config
    rule.created_by_admin_id = rule.created_by_admin_id or principal.admin_user_id
    db.add(
        AuditLog(
            actor_email=principal.email,
            action="scoring_rule.update",
            entity_type="scoring_rule",
            entity_id=str(rule.id),
            details={"config": config},
        )
    )
    db.commit()
    db.refresh(rule)
    return read_scoring_rule(db, rule)


def read_scoring_rule(db: Session, rule: ScoringRuleVersion) -> ScoringRuleRead:
    current_open_season = open_season(db)
    return ScoringRuleRead(
        id=rule.id,
        name=rule.name,
        status=rule.status,
        editable=True,
        open_season_name=current_open_season.name if current_open_season is not None else None,
        config=ScoreConfig.model_validate(rule.config).model_dump(),
        updated_at=rule.updated_at,
    )
