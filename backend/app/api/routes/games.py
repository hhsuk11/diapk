from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.core.time import utcnow
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enums import GameSide, GameStatus, Permission, SeasonStatus
from app.models.game import Game, GamePlayer
from app.models.player import Player
from app.models.season import Season
from app.schemas.games import (
    GameCreate,
    GameRead,
    GameResultUpdate,
    GameStart,
    GameStateChange,
    TeamPlayerIn,
)
from app.services.names import normalize_player_name
from app.services.response_cache import clear_public_response_cache
from app.services.season_stats import recompute_season_stats

router = APIRouter(prefix="/admin/games", tags=["admin-games"])


@router.post("", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def create_game(
    payload: GameCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.GAME_CREATE)),
) -> Game:
    season = db.get(Season, payload.season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    if season.disabled_at is not None or season.status != SeasonStatus.OPEN.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Season is not open")

    players_by_name = get_registered_players(db, [*payload.team_a, *payload.team_b])
    ensure_players_not_in_progress(db, list(players_by_name.values()))

    game = Game(
        id=str(uuid4()),
        season_id=season.id,
        legacy_game_id=payload.legacy_game_id,
        played_at=payload.played_at or utcnow(),
        source=payload.source,
        status=GameStatus.ACTIVE.value,
        winner_side=payload.winner_side,
        score_a=payload.score_a,
        score_b=payload.score_b,
        scoring_rule_version_id=season.scoring_rule_version_id,
        created_by_admin_id=principal.admin_user_id,
    )
    db.add(game)
    db.flush()

    add_game_players(db, game, payload.team_a, payload.team_b)
    db.flush()

    db.add(
        AuditLog(
            actor_email=principal.email,
            action="game.create",
            entity_type="game",
            entity_id=game.id,
            details={"season_id": season.id, "source": payload.source},
        )
    )
    recompute_season_stats(db, season.id)
    db.commit()
    clear_public_response_cache()
    db.refresh(game)
    return game


@router.post("/start", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def start_game(
    payload: GameStart,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.GAME_CREATE)),
) -> Game:
    season = db.get(Season, payload.season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    if season.disabled_at is not None or season.status != SeasonStatus.OPEN.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Season is not open")

    game = Game(
        id=str(uuid4()),
        season_id=season.id,
        played_at=payload.played_at or utcnow(),
        source=payload.source,
        status=GameStatus.IN_PROGRESS.value,
        winner_side=None,
        score_a=None,
        score_b=None,
        scoring_rule_version_id=season.scoring_rule_version_id,
        created_by_admin_id=principal.admin_user_id,
    )
    db.add(game)
    db.flush()
    add_game_players(db, game, payload.team_a, payload.team_b, players_by_name)

    db.add(
        AuditLog(
            actor_email=principal.email,
            action="game.start",
            entity_type="game",
            entity_id=game.id,
            details={"season_id": season.id, "source": payload.source},
        )
    )
    db.commit()
    clear_public_response_cache()
    db.refresh(game)
    return game


@router.get("/{game_id}", response_model=GameRead)
def get_game(
    game_id: str,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.GAME_CREATE)),
) -> Game:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return game


@router.post("/{game_id}/result", response_model=GameRead)
def submit_game_result(
    game_id: str,
    payload: GameResultUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.GAME_CREATE)),
) -> Game:
    game = load_mutable_game(db, game_id)
    if game.status == GameStatus.CANCELED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Game is canceled")

    old_status = game.status
    old_result = {
        "winner_side": game.winner_side,
        "score_a": game.score_a,
        "score_b": game.score_b,
    }
    game.status = GameStatus.ACTIVE.value
    game.winner_side = payload.winner_side
    game.score_a = payload.score_a
    game.score_b = payload.score_b
    game.canceled_at = None
    game.cancel_reason = None
    game.restored_at = None
    db.flush()
    db.add(
        AuditLog(
            actor_email=principal.email,
            action="game.result.update" if old_status == GameStatus.ACTIVE.value else "game.result",
            entity_type="game",
            entity_id=game.id,
            details={
                "old_status": old_status,
                "old_result": old_result,
                "winner_side": payload.winner_side,
                "score_a": payload.score_a,
                "score_b": payload.score_b,
            },
        )
    )
    db.flush()
    recompute_season_stats(db, game.season_id)
    db.commit()
    clear_public_response_cache()
    db.refresh(game)
    return game


@router.post("/{game_id}/cancel", response_model=GameRead)
def cancel_game(
    game_id: str,
    payload: GameStateChange,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.GAME_CANCEL)),
) -> Game:
    game = load_mutable_game(db, game_id)
    if game.status == GameStatus.CANCELED.value:
        return game

    game.status = GameStatus.CANCELED.value
    game.canceled_at = utcnow()
    game.cancel_reason = payload.reason
    game.restored_at = None
    db.flush()
    db.add(
        AuditLog(
            actor_email=principal.email,
            action="game.cancel",
            entity_type="game",
            entity_id=game.id,
            details={"reason": payload.reason},
        )
    )
    recompute_season_stats(db, game.season_id)
    db.commit()
    clear_public_response_cache()
    db.refresh(game)
    return game


@router.post("/{game_id}/restore", response_model=GameRead)
def restore_game(
    game_id: str,
    payload: GameStateChange,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.GAME_RESTORE)),
) -> Game:
    game = load_mutable_game(db, game_id)
    if game.status != GameStatus.CANCELED.value:
        return game

    game.status = (
        GameStatus.ACTIVE.value
        if game.winner_side is not None and game.score_a is not None and game.score_b is not None
        else GameStatus.IN_PROGRESS.value
    )
    game.restored_at = utcnow()
    game.cancel_reason = None
    db.flush()
    db.add(
        AuditLog(
            actor_email=principal.email,
            action="game.restore",
            entity_type="game",
            entity_id=game.id,
            details={"reason": payload.reason},
        )
    )
    recompute_season_stats(db, game.season_id)
    db.commit()
    clear_public_response_cache()
    db.refresh(game)
    return game


def add_game_players(
    db: Session,
    game: Game,
    team_a: list[TeamPlayerIn],
    team_b: list[TeamPlayerIn],
    registered_players: dict[str, Player] | None = None,
) -> None:
    if registered_players is None:
        registered_players = get_registered_players(db, [*team_a, *team_b])
    for side, players in ((GameSide.A.value, team_a), (GameSide.B.value, team_b)):
        for slot, player in enumerate(players, start=1):
            league_player = registered_players[normalize_player_name(player.name)]
            db.add(
                GamePlayer(
                    game_id=game.id,
                    player_id=league_player.id,
                    side=side,
                    slot=slot,
                    class_name_at_game=player.class_name,
                    is_all_character_bonus=player.is_all_character_bonus,
                )
            )


def load_mutable_game(db: Session, game_id: str) -> Game:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    season = db.get(Season, game.season_id)
    if season is None or season.disabled_at is not None or season.status != SeasonStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only games in an open season can be changed",
        )
    return game


def ensure_players_not_in_progress(db: Session, players: list[Player]) -> None:
    if not players:
        return
    busy_players = db.execute(
        select(Player.display_name, Game.id)
        .join(GamePlayer, GamePlayer.player_id == Player.id)
        .join(Game, Game.id == GamePlayer.game_id)
        .where(
            Player.id.in_([player.id for player in players]),
            Game.status == GameStatus.IN_PROGRESS.value,
        )
        .order_by(Player.display_name)
    ).all()
    if not busy_players:
        return
    busy_names = sorted({display_name for display_name, _game_id in busy_players})
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Players already in progress: {', '.join(busy_names)}",
    )


def get_registered_players(db: Session, players: list[TeamPlayerIn]) -> dict[str, Player]:
    requested_names = {
        normalize_player_name(player.name): player.name.strip()
        for player in players
        if player.name.strip()
    }
    registered_players = {
        player.normalized_name: player
        for player in db.scalars(
            select(Player).where(
                Player.normalized_name.in_(requested_names),
                Player.is_active.is_(True),
            )
        ).all()
    }
    missing_names = [
        display_name
        for normalized_name, display_name in requested_names.items()
        if normalized_name not in registered_players
    ]
    if missing_names:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"등록되지 않은 유저: {', '.join(missing_names)}",
        )
    return registered_players
