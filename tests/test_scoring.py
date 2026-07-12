from app.services.scoring import LegacyMmrPolicy, PlayerRatingInput, TeamRatingInput


def test_legacy_policy_rewards_winner_and_penalizes_loser() -> None:
    policy = LegacyMmrPolicy()

    deltas = policy.calculate_team_delta(
        team_a=TeamRatingInput(side="A", ratings=[1000, 1000, 1000, 1000]),
        team_b=TeamRatingInput(side="B", ratings=[1000, 1000, 1000, 1000]),
        winner_side="A",
        score_a=5,
        score_b=2,
    )

    by_side = {delta.side: delta for delta in deltas}
    assert by_side["A"].delta > 0
    assert by_side["B"].delta < 0
    assert by_side["A"].expected_rate == 0.5


def test_legacy_policy_holds_score_until_placement_completion() -> None:
    policy = LegacyMmrPolicy()

    results = policy.calculate_player_results(
        team_a=[
            PlayerRatingInput(player_id=1, side="A", rating=0, wins=9, losses=10),
            PlayerRatingInput(player_id=2, side="A", rating=0, wins=0, losses=0),
            PlayerRatingInput(player_id=3, side="A", rating=0, wins=0, losses=0),
            PlayerRatingInput(player_id=4, side="A", rating=0, wins=0, losses=0),
        ],
        team_b=[
            PlayerRatingInput(player_id=5, side="B", rating=0, wins=0, losses=0),
            PlayerRatingInput(player_id=6, side="B", rating=0, wins=0, losses=0),
            PlayerRatingInput(player_id=7, side="B", rating=0, wins=0, losses=0),
            PlayerRatingInput(player_id=8, side="B", rating=0, wins=0, losses=0),
        ],
        winner_side="A",
        score_a=5,
        score_b=2,
    )

    by_player = {result.player_id: result for result in results}
    assert by_player[1].after_score == 1200
    assert by_player[2].after_score == 0


def test_legacy_policy_applies_placement_all_character_bonus_on_completion() -> None:
    policy = LegacyMmrPolicy()

    results = policy.calculate_player_results(
        team_a=[
            PlayerRatingInput(
                player_id=1,
                side="A",
                rating=0,
                wins=9,
                losses=10,
                all_character_count=2,
                is_all_character_bonus=True,
            )
        ],
        team_b=[
            PlayerRatingInput(player_id=2, side="B", rating=0, wins=0, losses=0),
        ],
        winner_side="A",
        score_a=5,
        score_b=2,
    )

    assert results[0].after_score == 1212
