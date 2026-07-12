from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scoring import ScoringConfigRead


class SeasonCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    open_immediately: bool = True


class SeasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = Field(validation_alias="display_name")
    sort_order: int
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    scoring_rule_version_id: int | None
    is_imported_snapshot: bool
    legacy_sheet_name: str | None
    disabled_at: datetime | None


class SeasonScoringRuleRead(BaseModel):
    season_id: int
    season_name: str
    rule_id: int
    rule_name: str
    config: ScoringConfigRead
