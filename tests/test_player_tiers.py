import app.models  # noqa: F401
from app.db.base import Base
from app.models.enums import RuleStatus, SeasonStatus
from app.models.player import Player
from app.models.rating import SeasonPlayerStats
from app.models.scoring import ScoringRuleVersion
from app.models.season import Season
from app.services.player_tiers import sync_player_tiers_from_latest_closed_season
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_sync_player_tiers_uses_latest_closed_season_stats() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        rule = ScoringRuleVersion(
            name="test",
            status=RuleStatus.LOCKED.value,
            config={
                "tier_thresholds": {
                    "마스터": 1600,
                    "다이아": 1400,
                    "플래티넘": 1250,
                    "골드": 1100,
                    "실버": 950,
                }
            },
        )
        older = Season(
            name="old",
            sort_order=1,
            status=SeasonStatus.CLOSED.value,
            scoring_rule_version_id=None,
        )
        previous = Season(
            name="previous",
            sort_order=2,
            status=SeasonStatus.CLOSED.value,
            scoring_rule_version_id=None,
        )
        next_season = Season(
            name="next",
            sort_order=3,
            status=SeasonStatus.OPEN.value,
            scoring_rule_version_id=None,
        )
        player_with_saved_tier = Player(
            display_name="Saved",
            normalized_name="saved",
            current_tier="아이언",
            is_active=True,
        )
        player_from_rating = Player(
            display_name="Rating",
            normalized_name="rating",
            current_tier=None,
            is_active=True,
        )
        db.add_all([rule, older, previous, next_season, player_with_saved_tier, player_from_rating])
        db.flush()

        previous.scoring_rule_version_id = rule.id
        next_season.scoring_rule_version_id = rule.id
        db.add_all(
            [
                SeasonPlayerStats(
                    season_id=older.id,
                    player_id=player_with_saved_tier.id,
                    rating=1700,
                    tier="마스터",
                ),
                SeasonPlayerStats(
                    season_id=previous.id,
                    player_id=player_with_saved_tier.id,
                    rating=1120,
                    tier="골드",
                ),
                SeasonPlayerStats(
                    season_id=previous.id,
                    player_id=player_from_rating.id,
                    rating=1420,
                    tier=None,
                ),
            ]
        )

        changed = sync_player_tiers_from_latest_closed_season(
            db,
            before_sort_order=next_season.sort_order,
        )

        assert changed == 2
        assert player_with_saved_tier.current_tier == "골드"
        assert player_from_rating.current_tier == "다이아"
