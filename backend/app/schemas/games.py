from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import GameSource


class TeamPlayerIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    class_name: str | None = Field(default=None, max_length=40)
    is_all_character_bonus: bool = False


class GameCreate(BaseModel):
    season_id: int
    played_at: datetime | None = None
    source: Literal["team_builder", "manual"] = GameSource.MANUAL.value
    legacy_game_id: str | None = Field(default=None, max_length=40)
    team_a: list[TeamPlayerIn]
    team_b: list[TeamPlayerIn]
    winner_side: Literal["A", "B"]
    score_a: int = Field(ge=0)
    score_b: int = Field(ge=0)

    @field_validator("team_a", "team_b")
    @classmethod
    def validate_team_size(cls, value: list[TeamPlayerIn]) -> list[TeamPlayerIn]:
        if len(value) != 4:
            raise ValueError("A team must have exactly four players")
        return value

    @model_validator(mode="after")
    def validate_winner_score(self) -> "GameCreate":
        winner_score = self.score_a if self.winner_side == "A" else self.score_b
        loser_score = self.score_b if self.winner_side == "A" else self.score_a
        if winner_score <= loser_score:
            raise ValueError("Winner score must be greater than loser score")
        return self


class GameStart(BaseModel):
    season_id: int
    played_at: datetime | None = None
    source: Literal["team_builder"] = GameSource.TEAM_BUILDER.value
    team_a: list[TeamPlayerIn]
    team_b: list[TeamPlayerIn]

    @field_validator("team_a", "team_b")
    @classmethod
    def validate_team_size(cls, value: list[TeamPlayerIn]) -> list[TeamPlayerIn]:
        if len(value) != 4:
            raise ValueError("A team must have exactly four players")
        return value


class GameResultUpdate(BaseModel):
    winner_side: Literal["A", "B"]
    score_a: int = Field(ge=0)
    score_b: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_winner_score(self) -> "GameResultUpdate":
        winner_score = self.score_a if self.winner_side == "A" else self.score_b
        loser_score = self.score_b if self.winner_side == "A" else self.score_a
        if winner_score <= loser_score:
            raise ValueError("Winner score must be greater than loser score")
        return self


class GameStateChange(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class GameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    season_id: int
    legacy_game_id: str | None
    legacy_row_number: int | None
    played_at: datetime
    source: str
    status: str
    winner_side: str | None
    score_a: int | None
    score_b: int | None
    scoring_rule_version_id: int | None
    canceled_at: datetime | None
    cancel_reason: str | None
    restored_at: datetime | None
