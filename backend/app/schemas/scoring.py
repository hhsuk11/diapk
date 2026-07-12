from datetime import datetime

from pydantic import BaseModel, Field


class ScoringConfigRead(BaseModel):
    initial_score: int
    placement_game_count: int
    placement_win_points: int
    winner_k: float
    loser_k: float
    winner_expected_score_constant: float
    loser_expected_score_constant: float
    all_character_bonus_ratio: float
    loss_scale: float
    tier_thresholds: dict[str, int]


class ScoringConfigUpdate(BaseModel):
    initial_score: int = Field(ge=0, le=5000)
    placement_game_count: int = Field(ge=1, le=100)
    placement_win_points: int = Field(ge=0, le=500)
    winner_k: float = Field(gt=0, le=500)
    loser_k: float = Field(gt=0, le=500)
    winner_expected_score_constant: float = Field(gt=0, le=5000)
    loser_expected_score_constant: float = Field(gt=0, le=5000)
    all_character_bonus_ratio: float = Field(ge=0, le=2)
    loss_scale: float = Field(ge=0, le=2)
    tier_thresholds: dict[str, int]


class ScoringRuleRead(BaseModel):
    id: int
    name: str
    status: str
    editable: bool
    open_season_name: str | None
    config: ScoringConfigRead
    updated_at: datetime
