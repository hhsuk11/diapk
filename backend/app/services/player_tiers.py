from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.enums import SeasonStatus
from app.models.player import Player
from app.models.rating import SeasonPlayerStats
from app.models.scoring import ScoringRuleVersion
from app.models.season import Season
from app.services.scoring import ScoreConfig
from app.services.season_stats import tier_for_rating


def sync_player_tiers_from_latest_closed_season(
    db: Session,
    *,
    before_sort_order: int | None = None,
) -> int:
    previous_season = latest_closed_season(db, before_sort_order=before_sort_order)
    if previous_season is None:
        return 0

    rule = (
        db.get(ScoringRuleVersion, previous_season.scoring_rule_version_id)
        if previous_season.scoring_rule_version_id is not None
        else None
    )
    config = ScoreConfig.model_validate(rule.config if rule is not None else {})
    stats = db.scalars(
        select(SeasonPlayerStats).where(SeasonPlayerStats.season_id == previous_season.id)
    ).all()

    changed = 0
    for stat in stats:
        player = db.get(Player, stat.player_id)
        if player is None:
            continue
        next_tier = stat.tier or tier_for_rating(stat.rating, config)
        if player.current_tier != next_tier:
            player.current_tier = next_tier
            changed += 1
    return changed


def latest_closed_season(db: Session, *, before_sort_order: int | None = None) -> Season | None:
    stmt = (
        select(Season)
        .where(
            Season.status == SeasonStatus.CLOSED.value,
            Season.disabled_at.is_(None),
        )
        .order_by(desc(Season.sort_order), desc(Season.id))
        .limit(1)
    )
    if before_sort_order is not None:
        stmt = stmt.where(Season.sort_order < before_sort_order)
    return db.scalar(stmt)
