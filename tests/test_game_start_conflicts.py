from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.routes.games import ensure_players_not_in_progress
from app.db.base import Base
from app.models.enums import GameStatus
from app.models.game import Game, GamePlayer
from app.models.player import Player


def test_ensure_players_not_in_progress_blocks_busy_player() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        busy_player = Player(display_name="Busy", normalized_name="busy", is_active=True)
        free_player = Player(display_name="Free", normalized_name="free", is_active=True)
        in_progress_game = Game(
            id="game-1",
            season_id=1,
            status=GameStatus.IN_PROGRESS.value,
            played_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
        )
        db.add_all([busy_player, free_player, in_progress_game])
        db.flush()
        db.add(
            GamePlayer(
                game_id=in_progress_game.id,
                player_id=busy_player.id,
                side="A",
                slot=1,
            )
        )
        db.flush()

        with pytest.raises(HTTPException) as exc:
            ensure_players_not_in_progress(db, [busy_player, free_player])

        assert exc.value.status_code == 409
        assert "Busy" in exc.value.detail


def test_ensure_players_not_in_progress_allows_free_players() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        player = Player(display_name="Free", normalized_name="free", is_active=True)
        db.add(player)
        db.flush()

        ensure_players_not_in_progress(db, [player])
