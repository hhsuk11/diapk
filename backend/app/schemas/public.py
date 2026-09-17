from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.core.time import serialize_utc


class SummaryRead(BaseModel):
    season_id: int | None
    season_name: str | None
    season_status: str | None
    total_seasons: int
    total_players: int
    total_games: int
    season_games: int
    ranked_players: int
    top_rating: int | None


class RankingRead(BaseModel):
    player_id: int
    player_name: str
    rank: int | None
    rating: int
    games_played: int
    wins: int
    losses: int
    win_rate: float | None
    tier: str | None


class ClassStatsRead(BaseModel):
    class_name: str
    wins: int
    losses: int
    win_rate: float | None


class PlayerStatsRead(BaseModel):
    player_id: int
    player_name: str
    rank: int | None
    trophy: str | None
    trophy_score: int = 0
    gold: int = 0
    silver: int = 0
    bronze: int = 0
    rating: int | None = None
    games_played: int
    wins: int
    losses: int
    win_rate: float | None
    class_stats: list[ClassStatsRead]


class DuoStatsRead(BaseModel):
    duo_name: str
    players: list[str]
    wins: int
    losses: int
    total_games: int
    win_rate: float | None


class PairRecordRead(BaseModel):
    wins: int
    losses: int
    win_rate: float | None


class ClassHeadToHeadRead(BaseModel):
    classes: list[str]
    matrix: dict[str, dict[str, PairRecordRead]]


class RecentGameRead(BaseModel):
    game_id: str
    legacy_game_id: str | None
    played_at: datetime
    class_name: str | None
    score: str
    result: str

    @field_serializer("played_at")
    def serialize_played_at(self, value: datetime) -> str | None:
        return serialize_utc(value)


class PlayerDetailRead(BaseModel):
    player_id: int
    player_name: str
    tier: str | None
    season_stats: PlayerStatsRead | None
    recent_games: list[RecentGameRead]
    best_duos: list[DuoStatsRead]
    worst_duos: list[DuoStatsRead]


class DuoMatchupRead(BaseModel):
    user1: str
    user2: str
    team_up: PairRecordRead
    vs: PairRecordRead
    class_head_to_head: ClassHeadToHeadRead


class TeamBuilderPlayerRead(BaseModel):
    player_id: int
    player_name: str
    current_tier: str | None
    class_ranks: dict[str, str | None] = Field(default_factory=dict)


class GamePlayerRead(BaseModel):
    player_id: int
    player_name: str
    side: str
    slot: int
    class_name: str | None
    rating_before: int | None = None
    rating_delta: int | None = None
    rating_recorded: bool = False


class GameSummaryRead(BaseModel):
    id: str
    legacy_game_id: str | None
    legacy_row_number: int | None
    season_id: int
    season_name: str | None = None
    played_at: datetime
    status: str
    winner_side: str | None
    score_a: int | None
    score_b: int | None
    team_a_average_score: int | None = None
    team_b_average_score: int | None = None
    players: list[GamePlayerRead]

    @field_serializer("played_at")
    def serialize_played_at(self, value: datetime) -> str | None:
        return serialize_utc(value)


class HistoryPageRead(BaseModel):
    season_id: int | None
    query: str | None = None
    all_seasons: bool = False
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[GameSummaryRead]
