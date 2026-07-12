from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScoreConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    initial_score: int = 1000
    placement_game_count: int = 20
    placement_win_points: int = 20
    winner_k: float = 40.0
    loser_k: float = 40.0
    winner_expected_score_constant: float = 700.0
    loser_expected_score_constant: float = 1500.0
    all_character_bonus_ratio: float = 0.2
    loss_scale: float = 0.9
    tier_thresholds: dict[str, int] = Field(
        default_factory=lambda: {
            "마스터": 1600,
            "다이아": 1400,
            "플래티넘": 1250,
            "골드": 1100,
            "실버": 950,
        }
    )

    # Kept only so older draft configs can still be loaded without failing.
    placement_bonus: int = 0
    expected_score_constant: float | None = None
    all_character_bonus: float | None = None


class TeamRatingInput(BaseModel):
    side: Literal["A", "B"]
    ratings: list[int] = Field(min_length=1)


class PlayerRatingInput(BaseModel):
    player_id: int
    side: Literal["A", "B"]
    rating: int = 0
    wins: int = 0
    losses: int = 0
    all_character_count: int = 0
    is_all_character_bonus: bool = False


class RatingDelta(BaseModel):
    side: Literal["A", "B"]
    delta: int
    expected_rate: float


class PlayerRatingResult(BaseModel):
    player_id: int
    side: Literal["A", "B"]
    before_score: int
    after_score: int
    delta: int
    expected_rate: float
    placement_completed: bool = False


class LegacyMmrPolicy:
    """Python implementation of the legacy `점수MMR_디스코드` sheet rules.

    The old GAS flow delegated most MMR arithmetic to formulas in the
    `점수MMR_디스코드` sheet. This class mirrors those formulas directly:

    - placement score stays 0 until the configured placement game count;
    - placement completion score is initial + wins * placement points
      + placement all-character win bonus;
    - after placement, each player is compared against the opposite team's
      average sheet score, not simply team average vs team average;
    - winners and losers use separate expected-rate constants.
    """

    def __init__(self, config: ScoreConfig | None = None) -> None:
        self.config = config or ScoreConfig()

    def calculate_team_delta(
        self,
        team_a: TeamRatingInput,
        team_b: TeamRatingInput,
        winner_side: Literal["A", "B"],
        score_a: int,
        score_b: int,
    ) -> list[RatingDelta]:
        """Compatibility helper for older tests/callers.

        Real season recomputation uses calculate_player_results(), because the
        legacy sheet calculates a different delta for each player.
        """
        if score_a < 0 or score_b < 0:
            raise ValueError("Scores must not be negative")

        winner_score = score_a if winner_side == "A" else score_b
        loser_score = score_b if winner_side == "A" else score_a
        if winner_score <= loser_score:
            raise ValueError("Winner score must be greater than loser score")

        avg_a = self._team_average(team_a.ratings)
        avg_b = self._team_average(team_b.ratings)
        expected_a = self._expected_rate(avg_a, avg_b, self.config.winner_expected_score_constant)
        expected_b = self._expected_rate(avg_b, avg_a, self.config.loser_expected_score_constant)
        loser_factor = 1 - (loser_score / winner_score / 2)

        if winner_side == "A":
            delta_a = ceil(self.config.winner_k * (1 - expected_a))
            delta_b = self._google_round(
                self.config.loser_k * (0 - expected_b) * self.config.loss_scale * loser_factor
            )
        else:
            delta_b = ceil(self.config.winner_k * (1 - expected_b))
            delta_a = self._google_round(
                self.config.loser_k * (0 - expected_a) * self.config.loss_scale * loser_factor
            )

        return [
            RatingDelta(side="A", delta=delta_a, expected_rate=expected_a),
            RatingDelta(side="B", delta=delta_b, expected_rate=expected_b),
        ]

    def calculate_player_results(
        self,
        team_a: list[PlayerRatingInput],
        team_b: list[PlayerRatingInput],
        winner_side: Literal["A", "B"],
        score_a: int,
        score_b: int,
    ) -> list[PlayerRatingResult]:
        if score_a < 0 or score_b < 0:
            raise ValueError("Scores must not be negative")

        winner_score = score_a if winner_side == "A" else score_b
        loser_score = score_b if winner_side == "A" else score_a
        if winner_score <= loser_score:
            raise ValueError("Winner score must be greater than loser score")

        normalized_a = [player.model_copy(update={"side": "A"}) for player in team_a]
        normalized_b = [player.model_copy(update={"side": "B"}) for player in team_b]

        current_scores = {
            player.player_id: self._sheet_current_score(player)
            for player in [*normalized_a, *normalized_b]
        }
        avg_a = self._team_average([current_scores[player.player_id] for player in normalized_a])
        avg_b = self._team_average([current_scores[player.player_id] for player in normalized_b])
        score_factor = 1 - (loser_score / winner_score / 2)

        results: list[PlayerRatingResult] = []
        for player in [*normalized_a, *normalized_b]:
            won = player.side == winner_side
            own_score = current_scores[player.player_id]
            opponent_average = avg_b if player.side == "A" else avg_a
            constant = (
                self.config.winner_expected_score_constant
                if won
                else self.config.loser_expected_score_constant
            )
            expected_rate = self._expected_rate(own_score, opponent_average, constant)
            after_score = self._after_score_for_player(
                player=player,
                won=won,
                current_score=own_score,
                expected_rate=expected_rate,
                score_factor=score_factor,
            )

            results.append(
                PlayerRatingResult(
                    player_id=player.player_id,
                    side=player.side,
                    before_score=player.rating,
                    after_score=after_score,
                    delta=after_score - player.rating,
                    expected_rate=expected_rate,
                    placement_completed=(
                        player.wins + player.losses + 1 == self.config.placement_game_count
                    ),
                )
            )

        return results

    def _after_score_for_player(
        self,
        player: PlayerRatingInput,
        won: bool,
        current_score: int,
        expected_rate: float,
        score_factor: float,
    ) -> int:
        games_after = player.wins + player.losses + 1
        if games_after < self.config.placement_game_count:
            return 0

        if games_after == self.config.placement_game_count:
            wins_after = player.wins + (1 if won else 0)
            all_character_count_after = player.all_character_count
            if won and player.is_all_character_bonus:
                all_character_count_after += 1
            placement_score = (
                self.config.initial_score
                + wins_after * self.config.placement_win_points
                + (
                    all_character_count_after
                    * self.config.placement_win_points
                    * self.config.all_character_bonus_ratio
                )
            )
            return self._google_round(placement_score)

        if won:
            base_delta = self.config.winner_k * (1 - expected_rate)
            bonus_delta = (
                base_delta * self.config.all_character_bonus_ratio
                if player.is_all_character_bonus
                else 0
            )
            return ceil(current_score + base_delta + bonus_delta)

        return self._google_round(
            current_score
            + self.config.loser_k * (0 - expected_rate) * self.config.loss_scale * score_factor
        )

    def _sheet_current_score(self, player: PlayerRatingInput) -> int:
        games_played = player.wins + player.losses
        if games_played == 0:
            return 0
        if player.rating == 0:
            return self.config.initial_score + player.wins * self.config.placement_win_points
        return player.rating

    def _expected_rate(self, own_score: float, opponent_average: float, constant: float) -> float:
        exponent = (opponent_average - own_score) / constant
        return 1 / (1 + 10**exponent)

    def _team_average(self, ratings: list[int | float]) -> float:
        positive_ratings = [rating for rating in ratings if rating > 0]
        if not positive_ratings:
            return float(self.config.initial_score)
        return sum(positive_ratings) / len(positive_ratings)

    def _google_round(self, value: float) -> int:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
