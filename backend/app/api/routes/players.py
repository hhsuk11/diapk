from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.models.game import GamePlayer
from app.models.player import Player, PlayerCharacter
from app.models.rating import RatingEvent, SeasonPlayerClassStats, SeasonPlayerStats
from app.schemas.players import PlayerAdminRead, PlayerCreate, PlayerDeleteRead, PlayerUpdate
from app.services.names import normalize_player_name
from app.services.response_cache import clear_public_response_cache

router = APIRouter(prefix="/admin/players", tags=["admin-players"])


@router.get("", response_model=list[PlayerAdminRead])
def list_players(
    include_inactive: bool = True,
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(Permission.PLAYER_MANAGE)),
) -> list[PlayerAdminRead]:
    stmt = select(Player).order_by(Player.is_active.desc(), Player.display_name)
    if not include_inactive:
        stmt = stmt.where(Player.is_active.is_(True))

    players = list(db.scalars(stmt).all())
    query = " ".join((q or "").split()).casefold()
    if query:
        players = [player for player in players if query in player.display_name.casefold()]

    return [read_player(db, player) for player in players]


@router.post("", response_model=PlayerAdminRead, status_code=status.HTTP_201_CREATED)
def create_player(
    payload: PlayerCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.PLAYER_MANAGE)),
) -> PlayerAdminRead:
    normalized_name = normalize_player_name(payload.display_name)
    existing = db.scalar(select(Player).where(Player.normalized_name == normalized_name))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 플레이어입니다: {existing.display_name}",
        )

    player = Player(
        display_name=payload.display_name.strip(),
        normalized_name=normalized_name,
        current_tier=None,
        is_active=True,
    )
    db.add(player)
    db.flush()

    seen_classes: set[str] = set()
    for character in payload.characters:
        class_name = character.class_name.strip()
        if not class_name or class_name in seen_classes:
            continue
        seen_classes.add(class_name)
        character_name = (character.character_name or "").strip() or None
        db.add(
            PlayerCharacter(
                player_id=player.id,
                class_name=class_name,
                character_name=character_name,
                normalized_character_name=normalize_player_name(character_name)
                if character_name
                else None,
            )
        )

    log_admin_action(
        db,
        principal,
        action="player:create",
        player=player,
        details={"display_name": player.display_name},
    )
    db.commit()
    clear_public_response_cache()
    db.refresh(player)
    return read_player(db, player)


@router.patch("/{player_id}", response_model=PlayerAdminRead)
def update_player(
    player_id: int,
    payload: PlayerUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.PLAYER_MANAGE)),
) -> PlayerAdminRead:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    display_name = payload.display_name.strip()
    normalized_name = normalize_player_name(display_name)
    existing = db.scalar(
        select(Player).where(
            Player.normalized_name == normalized_name,
            Player.id != player.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 플레이어입니다: {existing.display_name}",
        )

    old_display_name = player.display_name
    player.display_name = display_name
    player.normalized_name = normalized_name
    log_admin_action(
        db,
        principal,
        action="player:update",
        player=player,
        details={"old_display_name": old_display_name, "display_name": player.display_name},
    )
    db.commit()
    clear_public_response_cache()
    db.refresh(player)
    return read_player(db, player)


@router.delete("/{player_id}", response_model=PlayerDeleteRead)
def delete_player(
    player_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.PLAYER_MANAGE)),
) -> PlayerDeleteRead:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    game_refs, stats_refs = player_reference_counts(db, player.id)
    if game_refs or stats_refs:
        player.is_active = False
        log_admin_action(
            db,
            principal,
            action="player:deactivate",
            player=player,
            details={
                "reason": "referenced_player_delete",
                "game_refs": game_refs,
                "stats_refs": stats_refs,
            },
        )
        db.commit()
        clear_public_response_cache()
        return PlayerDeleteRead(player_id=player.id, deleted=False, deactivated=True)

    for character in list(player.characters):
        db.delete(character)
    log_admin_action(
        db,
        principal,
        action="player:delete",
        player=player,
        details={"display_name": player.display_name},
    )
    db.delete(player)
    db.commit()
    clear_public_response_cache()
    return PlayerDeleteRead(player_id=player_id, deleted=True, deactivated=False)


@router.post("/{player_id}/restore", response_model=PlayerAdminRead)
def restore_player(
    player_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(Permission.PLAYER_MANAGE)),
) -> PlayerAdminRead:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    player.is_active = True
    log_admin_action(
        db,
        principal,
        action="player:restore",
        player=player,
        details={"display_name": player.display_name},
    )
    db.commit()
    clear_public_response_cache()
    db.refresh(player)
    return read_player(db, player)


def read_player(db: Session, player: Player) -> PlayerAdminRead:
    game_refs, stats_refs = player_reference_counts(db, player.id)
    return PlayerAdminRead(
        player_id=player.id,
        player_name=player.display_name,
        current_tier=player.current_tier,
        is_active=player.is_active,
        total_games=total_games_for_player(db, player.id),
        game_refs=game_refs,
        stats_refs=stats_refs,
        character_count=character_count_for_player(db, player.id),
    )


def total_games_for_player(db: Session, player_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(SeasonPlayerStats.games_played), 0)).where(
                SeasonPlayerStats.player_id == player_id
            )
        )
        or 0
    )


def character_count_for_player(db: Session, player_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(PlayerCharacter.id)).where(PlayerCharacter.player_id == player_id)
        )
        or 0
    )


def player_reference_counts(db: Session, player_id: int) -> tuple[int, int]:
    game_refs = int(
        db.scalar(select(func.count(GamePlayer.id)).where(GamePlayer.player_id == player_id)) or 0
    )
    season_stats = int(
        db.scalar(
            select(func.count(SeasonPlayerStats.id)).where(
                SeasonPlayerStats.player_id == player_id
            )
        )
        or 0
    )
    class_stats = int(
        db.scalar(
            select(func.count(SeasonPlayerClassStats.id)).where(
                SeasonPlayerClassStats.player_id == player_id
            )
        )
        or 0
    )
    rating_events = int(
        db.scalar(select(func.count(RatingEvent.id)).where(RatingEvent.player_id == player_id))
        or 0
    )
    return game_refs, season_stats + class_stats + rating_events


def log_admin_action(
    db: Session,
    principal: Principal,
    action: str,
    player: Player,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            actor_email=principal.email,
            action=action,
            entity_type="player",
            entity_id=str(player.id),
            details=details,
        )
    )
