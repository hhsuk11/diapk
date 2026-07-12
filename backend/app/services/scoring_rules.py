from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.enums import RuleStatus, SeasonStatus
from app.models.scoring import ScoringRuleVersion
from app.models.season import Season
from app.services.scoring import ScoreConfig

LEGACY_RULE_NAME = "Legacy Discord MMR"
CURRENT_RULE_NAME = "Current MMR"


def legacy_score_config() -> ScoreConfig:
    return ScoreConfig()


def open_season(db: Session) -> Season | None:
    return db.scalar(
        select(Season).where(
            Season.status == SeasonStatus.OPEN.value,
            Season.disabled_at.is_(None),
        )
    )


def current_rule_for_admin(db: Session) -> ScoringRuleVersion:
    draft = db.scalar(
        select(ScoringRuleVersion)
        .where(ScoringRuleVersion.status == RuleStatus.DRAFT.value)
        .order_by(desc(ScoringRuleVersion.id))
        .limit(1)
    )
    if draft is not None:
        return draft

    latest = latest_rule(db)
    config = latest.config if latest is not None else legacy_score_config().model_dump()
    return create_editable_rule(db, config)


def editable_rule_for_update(db: Session) -> ScoringRuleVersion:
    draft = db.scalar(
        select(ScoringRuleVersion)
        .where(ScoringRuleVersion.status == RuleStatus.DRAFT.value)
        .order_by(desc(ScoringRuleVersion.id))
        .limit(1)
    )
    if draft is not None:
        return draft

    latest = latest_rule(db)
    config = latest.config if latest is not None else legacy_score_config().model_dump()
    return create_editable_rule(db, config)


def lock_current_rule_for_new_season(db: Session, admin_user_id: int | None) -> ScoringRuleVersion:
    rule = editable_rule_for_update(db)
    rule.name = f"Season MMR {utcnow().isoformat()}"
    rule.status = RuleStatus.LOCKED.value
    rule.created_by_admin_id = rule.created_by_admin_id or admin_user_id
    rule.locked_at = utcnow()
    rule.activated_at = rule.activated_at or utcnow()
    db.flush()
    return rule


def latest_rule(db: Session) -> ScoringRuleVersion | None:
    return db.scalar(select(ScoringRuleVersion).order_by(desc(ScoringRuleVersion.id)).limit(1))


def create_editable_rule(db: Session, config: dict) -> ScoringRuleVersion:
    normalized_config = ScoreConfig.model_validate(config).model_dump()
    rule = ScoringRuleVersion(
        name=CURRENT_RULE_NAME,
        status=RuleStatus.DRAFT.value,
        config=normalized_config,
        notes="Editable MMR settings used when starting a season.",
    )
    db.add(rule)
    db.flush()
    return rule
