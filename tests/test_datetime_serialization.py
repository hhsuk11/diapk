from datetime import datetime

from app.schemas.public import GameSummaryRead, RecentGameRead


def test_game_summary_serializes_naive_played_at_as_utc() -> None:
    summary = GameSummaryRead(
        id="game-1",
        legacy_game_id=None,
        legacy_row_number=None,
        season_id=1,
        season_name="시즌1",
        played_at=datetime(2026, 9, 18, 14, 26, 0),
        status="IN_PROGRESS",
        winner_side=None,
        score_a=None,
        score_b=None,
        players=[],
    )

    assert summary.model_dump(mode="json")["played_at"] == "2026-09-18T14:26:00Z"


def test_recent_game_serializes_naive_played_at_as_utc() -> None:
    recent_game = RecentGameRead(
        game_id="game-1",
        legacy_game_id=None,
        played_at=datetime(2026, 9, 18, 14, 26, 0),
        class_name="드루",
        score="5:4",
        result="승",
    )

    assert recent_game.model_dump(mode="json")["played_at"] == "2026-09-18T14:26:00Z"
