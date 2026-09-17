from collections import defaultdict
from itertools import combinations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import GameStatus, Permission, SeasonStatus
from app.models.game import Game, GamePlayer
from app.models.player import Player, PlayerCharacter
from app.models.rating import RatingEvent, SeasonPlayerClassStats, SeasonPlayerStats
from app.models.season import Season
from app.schemas.public import (
    ClassHeadToHeadRead,
    ClassStatsRead,
    DuoMatchupRead,
    DuoStatsRead,
    GamePlayerRead,
    GameSummaryRead,
    HistoryPageRead,
    PairRecordRead,
    PlayerDetailRead,
    PlayerStatsRead,
    RankingRead,
    RecentGameRead,
    SummaryRead,
    TeamBuilderPlayerRead,
)
from app.services.names import normalize_player_name
from app.services.response_cache import public_response_cache

router = APIRouter(tags=["public"])

CLASS_ORDER = ["드루", "어쎄", "네크", "슴딘"]
DEFAULT_CLASS_RANK = "C"


@router.get("/summary", response_model=SummaryRead)
def summary(
    season_id: int | None = None,
    db: Session = Depends(get_db),
) -> SummaryRead:
    return public_response_cache.get_or_set(
        ("summary", season_id),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_summary(db, season_id),
    )


def build_summary(db: Session, season_id: int | None) -> SummaryRead:
    season_id = season_id or latest_season_id(db)
    season = db.get(Season, season_id) if season_id is not None else None

    total_players = db.scalar(
        select(func.count(Player.id)).where(Player.is_active.is_(True))
    ) or 0
    total_seasons = db.scalar(
        select(func.count(Season.id)).where(Season.disabled_at.is_(None))
    ) or 0
    total_games = db.scalar(
        select(func.count(Game.id))
        .join(Season, Season.id == Game.season_id)
        .where(Game.status == GameStatus.ACTIVE.value, Season.disabled_at.is_(None))
    ) or 0

    season_games = 0
    ranked_players = 0
    top_rating = None
    if season_id is not None:
        season_games = (
            db.scalar(
                select(func.count(Game.id)).where(
                    Game.season_id == season_id,
                    Game.status == GameStatus.ACTIVE.value,
                )
            )
            or 0
        )
        ranked_players = (
            db.scalar(
                select(func.count(SeasonPlayerStats.id))
                .join(Player, Player.id == SeasonPlayerStats.player_id)
                .where(
                    SeasonPlayerStats.season_id == season_id,
                    Player.is_active.is_(True),
                )
            )
            or 0
        )
        top_rating = db.scalar(
            select(func.max(SeasonPlayerStats.rating))
            .join(Player, Player.id == SeasonPlayerStats.player_id)
            .where(
                SeasonPlayerStats.season_id == season_id,
                Player.is_active.is_(True),
            )
        )

    return SummaryRead(
        season_id=season_id,
        season_name=season.name if season is not None else None,
        season_status=season.status if season is not None else None,
        total_seasons=total_seasons,
        total_players=total_players,
        total_games=total_games,
        season_games=season_games,
        ranked_players=ranked_players,
        top_rating=top_rating,
    )


@router.get("/team-builder/players", response_model=list[TeamBuilderPlayerRead])
def team_builder_players(db: Session = Depends(get_db)) -> list[TeamBuilderPlayerRead]:
    return public_response_cache.get_or_set(
        ("team_builder_players",),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_team_builder_players(db),
    )


def build_team_builder_players(db: Session) -> list[TeamBuilderPlayerRead]:
    players = db.scalars(
        select(Player).where(Player.is_active.is_(True)).order_by(Player.display_name)
    ).all()
    character_rows = db.scalars(
        select(PlayerCharacter).where(PlayerCharacter.player_id.in_([player.id for player in players]))
    ).all()
    ranks_by_player: dict[int, dict[str, str | None]] = defaultdict(dict)
    for character in character_rows:
        ranks_by_player[character.player_id][character.class_name] = (
            character.class_rank or DEFAULT_CLASS_RANK
        )
    return [
        TeamBuilderPlayerRead(
            player_id=player.id,
            player_name=player.display_name,
            current_tier=player.current_tier,
            class_ranks={
                class_name: ranks_by_player.get(player.id, {}).get(
                    class_name,
                    DEFAULT_CLASS_RANK,
                )
                for class_name in CLASS_ORDER
            },
        )
        for player in players
    ]


@router.get("/current-games", response_model=list[GameSummaryRead])
def current_games(
    season_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[GameSummaryRead]:
    stmt = select(Game).where(Game.status == GameStatus.IN_PROGRESS.value)
    if season_id is not None:
        stmt = stmt.where(Game.season_id == season_id)
    else:
        open_season_ids = select(Season.id).where(
            Season.status == SeasonStatus.OPEN.value,
            Season.disabled_at.is_(None),
        )
        stmt = stmt.where(Game.season_id.in_(open_season_ids))

    games = list(
        db.scalars(stmt.order_by(desc(Game.played_at), desc(Game.created_at)).limit(5)).all()
    )
    return game_summaries_for_games(db, games)


@router.get("/player-stats", response_model=list[PlayerStatsRead])
def player_stats(
    season_id: int | None = None,
    all_seasons: bool = False,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[PlayerStatsRead]:
    return public_response_cache.get_or_set(
        ("player_stats", season_id, all_seasons, limit),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_player_stats(db, season_id, all_seasons, limit),
    )


def build_player_stats(
    db: Session,
    season_id: int | None,
    all_seasons: bool,
    limit: int,
) -> list[PlayerStatsRead]:
    if all_seasons:
        return all_time_player_stats(db, limit)

    season_id = season_id or latest_season_id(db)
    if season_id is None:
        return []

    stats_rows = db.execute(
        select(SeasonPlayerStats, Player)
        .join(Player, Player.id == SeasonPlayerStats.player_id)
        .where(SeasonPlayerStats.season_id == season_id, Player.is_active.is_(True))
        .order_by(
            SeasonPlayerStats.rank.is_(None),
            SeasonPlayerStats.rank,
            desc(SeasonPlayerStats.rating),
        )
        .limit(limit)
    ).all()
    class_stats = class_stats_by_player(db, season_id)
    podiums = podiums_by_player(db)

    return [
        PlayerStatsRead(
            player_id=player.id,
            player_name=player.display_name,
            rank=stats.rank,
            trophy=format_trophy(podiums.get(player.id)),
            trophy_score=podiums.get(player.id, {}).get("score", 0),
            gold=podiums.get(player.id, {}).get("gold", 0),
            silver=podiums.get(player.id, {}).get("silver", 0),
            bronze=podiums.get(player.id, {}).get("bronze", 0),
            rating=stats.rating,
            games_played=stats.games_played,
            wins=stats.wins,
            losses=stats.losses,
            win_rate=stats.win_rate,
            class_stats=render_class_stats(class_stats.get(player.id, {})),
        )
        for stats, player in stats_rows
    ]


def all_time_player_stats(db: Session, limit: int) -> list[PlayerStatsRead]:
    podiums = podiums_by_player(db)
    player_totals: dict[int, dict] = {}
    stats_rows = db.execute(
        select(SeasonPlayerStats, Player).join(Player, Player.id == SeasonPlayerStats.player_id)
        .where(Player.is_active.is_(True))
    ).all()

    for stats, player in stats_rows:
        totals = player_totals.setdefault(
            player.id,
            {
                "player": player,
                "games_played": 0,
                "wins": 0,
                "losses": 0,
            },
        )
        totals["games_played"] += stats.games_played
        totals["wins"] += stats.wins
        totals["losses"] += stats.losses

    class_totals: dict[int, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"wins": 0, "losses": 0})
    )
    for row in db.scalars(select(SeasonPlayerClassStats)).all():
        class_total = class_totals[row.player_id][row.class_name]
        class_total["wins"] += row.wins
        class_total["losses"] += row.losses

    rows = []
    for player_id, totals in player_totals.items():
        podium = podiums.get(player_id, {})
        rows.append(
            {
                **totals,
                "podium": podium,
                "class_stats": render_class_total_stats(class_totals.get(player_id, {})),
            }
        )

    rows.sort(
        key=lambda row: (
            row["podium"].get("score", 0),
            row["podium"].get("gold", 0),
            row["podium"].get("silver", 0),
            row["podium"].get("bronze", 0),
            row["games_played"],
            row["wins"],
            row["player"].display_name,
        ),
        reverse=True,
    )

    return [
        PlayerStatsRead(
            player_id=row["player"].id,
            player_name=row["player"].display_name,
            rank=index,
            trophy=format_trophy(row["podium"]),
            trophy_score=row["podium"].get("score", 0),
            gold=row["podium"].get("gold", 0),
            silver=row["podium"].get("silver", 0),
            bronze=row["podium"].get("bronze", 0),
            rating=None,
            games_played=row["games_played"],
            wins=row["wins"],
            losses=row["losses"],
            win_rate=win_rate(row["wins"], row["losses"]),
            class_stats=row["class_stats"],
        )
        for index, row in enumerate(rows[:limit], start=1)
    ]


@router.get("/duos", response_model=list[DuoStatsRead])
def duo_stats(
    season_id: int | None = None,
    all_seasons: bool = False,
    min_games: int = Query(default=1, ge=1, le=1000),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[DuoStatsRead]:
    return public_response_cache.get_or_set(
        ("duos", season_id, all_seasons, min_games, limit),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_duo_stats(db, season_id, all_seasons, min_games, limit),
    )


def build_duo_stats(
    db: Session,
    season_id: int | None,
    all_seasons: bool,
    min_games: int,
    limit: int,
) -> list[DuoStatsRead]:
    if not all_seasons:
        season_id = season_id or latest_season_id(db)
        if season_id is None:
            return []

    rows = calculate_duo_stats(db, season_id=season_id, all_seasons=all_seasons)
    return [row for row in rows if row.total_games >= min_games][:limit]


@router.get("/players/{player_id}/detail", response_model=PlayerDetailRead)
def player_detail(
    player_id: int,
    season_id: int | None = None,
    db: Session = Depends(get_db),
) -> PlayerDetailRead:
    return public_response_cache.get_or_set(
        ("player_detail", player_id, season_id),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_player_detail(db, player_id, season_id),
    )


def build_player_detail(
    db: Session,
    player_id: int,
    season_id: int | None,
) -> PlayerDetailRead:
    season_id = season_id or latest_season_id(db)
    player = db.get(Player, player_id)
    if player is None or not player.is_active:
        raise HTTPException(status_code=404, detail="Player not found")

    season_stats = None
    detail_tier = player.current_tier
    if season_id is not None:
        stats = db.scalar(
            select(SeasonPlayerStats).where(
                SeasonPlayerStats.season_id == season_id,
                SeasonPlayerStats.player_id == player_id,
            )
        )
        if stats is not None:
            class_stats = class_stats_by_player(db, season_id).get(player_id, {})
            podium = podiums_by_player(db).get(player_id, {})
            season_stats = PlayerStatsRead(
                player_id=player.id,
                player_name=player.display_name,
                rank=stats.rank,
                trophy=format_trophy(podium),
                trophy_score=podium.get("score", 0),
                gold=podium.get("gold", 0),
                silver=podium.get("silver", 0),
                bronze=podium.get("bronze", 0),
                rating=stats.rating,
                games_played=stats.games_played,
                wins=stats.wins,
                losses=stats.losses,
                win_rate=stats.win_rate,
                class_stats=render_class_stats(class_stats),
            )
            detail_tier = display_tier(stats.rating, stats.tier)

    duos = calculate_duo_stats(db, season_id=season_id, all_seasons=False)
    player_duos = [
        duo
        for duo in duos
        if player.display_name in duo.players and duo.total_games >= 3
    ]
    player_duos.sort(
        key=lambda duo: (duo.win_rate or 0, duo.total_games, duo.wins),
        reverse=True,
    )
    worst_duos = sorted(
        player_duos,
        key=lambda duo: (duo.win_rate or 0, -duo.total_games, duo.losses),
    )

    return PlayerDetailRead(
        player_id=player.id,
        player_name=player.display_name,
        tier=detail_tier,
        season_stats=season_stats,
        recent_games=recent_games_for_player(db, player_id, limit=5),
        best_duos=player_duos[:3],
        worst_duos=worst_duos[:3],
    )


@router.get("/duo-matchup", response_model=DuoMatchupRead)
def duo_matchup(
    user1: str,
    user2: str,
    season_id: int | None = None,
    all_seasons: bool = False,
    db: Session = Depends(get_db),
) -> DuoMatchupRead:
    return public_response_cache.get_or_set(
        ("duo_matchup", user1, user2, season_id, all_seasons),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_duo_matchup(db, user1, user2, season_id, all_seasons),
    )


def build_duo_matchup(
    db: Session,
    user1: str,
    user2: str,
    season_id: int | None,
    all_seasons: bool,
) -> DuoMatchupRead:
    if not all_seasons:
        season_id = season_id or latest_season_id(db)
        if season_id is None:
            return DuoMatchupRead(
                user1=user1,
                user2=user2,
                team_up=record_read(0, 0),
                vs=record_read(0, 0),
                class_head_to_head=empty_class_head_to_head(),
            )

    player1 = resolve_player(db, user1)
    player2 = resolve_player(db, user2)
    if player1.id == player2.id:
        raise HTTPException(status_code=400, detail="두 플레이어는 서로 달라야 합니다.")

    team_wins = team_losses = vs_wins = vs_losses = 0
    matrix = empty_class_matrix()

    for bundle in load_game_bundles(db, season_id=season_id, all_seasons=all_seasons):
        entries = {entry["player"].id: entry for entry in bundle["players"]}
        entry1 = entries.get(player1.id)
        entry2 = entries.get(player2.id)
        if entry1 is None or entry2 is None:
            continue

        game = bundle["game"]
        game_player1 = entry1["game_player"]
        game_player2 = entry2["game_player"]
        user1_won = game_player1.side == game.winner_side

        if game_player1.side == game_player2.side:
            if user1_won:
                team_wins += 1
            else:
                team_losses += 1
            continue

        if user1_won:
            vs_wins += 1
        else:
            vs_losses += 1

        class1 = game_player1.class_name_at_game or "-"
        class2 = game_player2.class_name_at_game or "-"
        ensure_class_pair(matrix, class1, class2)
        record = matrix[class1][class2]
        if user1_won:
            record["wins"] += 1
        else:
            record["losses"] += 1

    return DuoMatchupRead(
        user1=player1.display_name,
        user2=player2.display_name,
        team_up=record_read(team_wins, team_losses),
        vs=record_read(vs_wins, vs_losses),
        class_head_to_head=matrix_read(matrix),
    )


@router.get("/rankings", response_model=list[RankingRead])
def rankings(
    season_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RankingRead]:
    return public_response_cache.get_or_set(
        ("rankings", season_id, limit),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_rankings(db, season_id, limit),
    )


def build_rankings(
    db: Session,
    season_id: int | None,
    limit: int,
) -> list[RankingRead]:
    season_id = season_id or latest_season_id(db)
    if season_id is None:
        return []

    rows = db.execute(
        select(SeasonPlayerStats, Player)
        .join(Player, Player.id == SeasonPlayerStats.player_id)
        .where(SeasonPlayerStats.season_id == season_id, Player.is_active.is_(True))
        .order_by(
            SeasonPlayerStats.rank.is_(None),
            SeasonPlayerStats.rank,
            desc(SeasonPlayerStats.rating),
        )
        .limit(limit)
    ).all()

    return [
        RankingRead(
            player_id=player.id,
            player_name=player.display_name,
            rank=stats.rank,
            rating=stats.rating,
            games_played=stats.games_played,
            wins=stats.wins,
            losses=stats.losses,
            win_rate=stats.win_rate,
            tier=display_tier(stats.rating, stats.tier),
        )
        for stats, player in rows
    ]


@router.get("/history", response_model=list[GameSummaryRead])
def history(
    season_id: int | None = None,
    include_canceled: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[GameSummaryRead]:
    season_id = season_id or latest_season_id(db)
    if season_id is None:
        return []

    stmt = select(Game).where(Game.season_id == season_id)
    show_canceled = include_canceled and principal.can(Permission.GAME_RESTORE)
    if not show_canceled:
        stmt = stmt.where(Game.status != GameStatus.CANCELED.value)
    games = list(
        db.scalars(
            stmt.order_by(desc(Game.played_at), desc(Game.legacy_row_number)).limit(limit)
        ).all()
    )
    if not games:
        return []

    return game_summaries_for_games(db, games)


@router.get("/history-page", response_model=HistoryPageRead)
def history_page(
    season_id: int | None = None,
    all_seasons: bool = False,
    include_canceled: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=10, le=100),
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> HistoryPageRead:
    season_id_for_key = None if all_seasons else season_id
    query_for_key = " ".join((q or "").split())
    show_canceled = include_canceled and principal.can(Permission.GAME_RESTORE)
    return public_response_cache.get_or_set(
        (
            "history_page",
            season_id_for_key,
            all_seasons,
            show_canceled,
            page,
            page_size,
            query_for_key,
        ),
        PUBLIC_CACHE_TTL_SECONDS,
        lambda: build_history_page(
            db,
            season_id,
            all_seasons,
            include_canceled,
            page,
            page_size,
            q,
            principal,
        ),
    )


def build_history_page(
    db: Session,
    season_id: int | None,
    all_seasons: bool,
    include_canceled: bool,
    page: int,
    page_size: int,
    q: str | None,
    principal: Principal,
) -> HistoryPageRead:
    season_id = None if all_seasons else season_id or latest_season_id(db)
    query = " ".join((q or "").split())
    if season_id is None and not all_seasons:
        return HistoryPageRead(
            season_id=None,
            query=query or None,
            all_seasons=all_seasons,
            total=0,
            page=1,
            page_size=page_size,
            total_pages=0,
            items=[],
        )

    show_canceled = include_canceled and principal.can(Permission.GAME_RESTORE)
    game_ids = matching_history_game_ids(db, season_id, query, show_canceled)
    total = len(game_ids)
    total_pages = (total + page_size - 1) // page_size if total else 0
    safe_page = min(page, total_pages) if total_pages else 1
    offset = (safe_page - 1) * page_size
    paged_game_ids = game_ids[offset : offset + page_size]

    games = list(
        db.scalars(
            select(Game)
            .where(Game.id.in_(paged_game_ids))
            .order_by(desc(Game.played_at), desc(Game.legacy_row_number))
        ).all()
    ) if paged_game_ids else []

    return HistoryPageRead(
        season_id=season_id,
        query=query or None,
        all_seasons=all_seasons,
        total=total,
        page=safe_page,
        page_size=page_size,
        total_pages=total_pages,
        items=game_summaries_for_games(db, games),
    )


PUBLIC_CACHE_TTL_SECONDS = settings.public_cache_ttl_seconds


def matching_history_game_ids(
    db: Session,
    season_id: int | None,
    query: str,
    include_canceled: bool,
) -> list[str]:
    stmt = (
        select(Game)
        .join(Season, Season.id == Game.season_id)
        .where(Season.disabled_at.is_(None))
        .order_by(desc(Game.played_at), desc(Game.legacy_row_number))
    )
    if season_id is not None:
        stmt = stmt.where(Game.season_id == season_id)
    if not include_canceled:
        stmt = stmt.where(Game.status != GameStatus.CANCELED.value)
    games = list(
        db.scalars(stmt).all()
    )
    if not query:
        return [game.id for game in games]

    normalized_query = query.casefold()
    game_map = {game.id: game for game in games}
    matched_ids = {
        game.id
        for game in games
        if normalized_query in (game.legacy_game_id or "").casefold()
        or normalized_query in game.id.casefold()
        or normalized_query in game.status.casefold()
    }

    player_rows = db.execute(
        select(GamePlayer, Player)
        .join(Player, Player.id == GamePlayer.player_id)
        .where(GamePlayer.game_id.in_(game_map.keys()))
    ).all()
    for game_player, player in player_rows:
        if (
            normalized_query in player.display_name.casefold()
            or normalized_query in (game_player.class_name_at_game or "").casefold()
        ):
            matched_ids.add(game_player.game_id)

    return [game.id for game in games if game.id in matched_ids]


def game_summaries_for_games(
    db: Session,
    games: list[Game],
) -> list[GameSummaryRead]:
    if not games:
        return []

    player_rows = db.execute(
        select(GamePlayer, Player)
        .join(Player, Player.id == GamePlayer.player_id)
        .where(
            GamePlayer.game_id.in_([game.id for game in games]),
            Player.is_active.is_(True),
        )
        .order_by(GamePlayer.game_id, GamePlayer.side, GamePlayer.slot)
    ).all()
    rating_rows = db.execute(
        select(
            RatingEvent.game_id,
            RatingEvent.player_id,
            RatingEvent.before_score,
            RatingEvent.delta,
        ).where(RatingEvent.game_id.in_([game.id for game in games]))
    ).all()
    ratings_by_game_player = {
        (game_id, player_id): (before_score, delta)
        for game_id, player_id, before_score, delta in rating_rows
    }

    players_by_game: dict[str, list[GamePlayerRead]] = {}
    for game_player, player in player_rows:
        rating_before, rating_delta = ratings_by_game_player.get(
            (game_player.game_id, player.id),
            (None, None),
        )
        players_by_game.setdefault(game_player.game_id, []).append(
            GamePlayerRead(
                player_id=player.id,
                player_name=player.display_name,
                side=game_player.side,
                slot=game_player.slot,
                class_name=game_player.class_name_at_game,
                rating_before=rating_before,
                rating_delta=rating_delta,
                rating_recorded=(game_player.game_id, player.id) in ratings_by_game_player,
            )
        )

    season_rows = db.scalars(
        select(Season).where(Season.id.in_({game.season_id for game in games}))
    ).all()
    season_names = {season.id: season.name for season in season_rows}

    return [game_summary_read(game, season_names, players_by_game) for game in games]


def game_summary_read(
    game: Game,
    season_names: dict[int, str],
    players_by_game: dict[str, list[GamePlayerRead]],
) -> GameSummaryRead:
    players = players_by_game.get(game.id, [])
    return GameSummaryRead(
        id=game.id,
        legacy_game_id=game.legacy_game_id,
        legacy_row_number=game.legacy_row_number,
        season_id=game.season_id,
        season_name=season_names.get(game.season_id),
        played_at=game.played_at,
        status=game.status,
        winner_side=game.winner_side,
        score_a=game.score_a,
        score_b=game.score_b,
        team_a_average_score=team_average_rating(players, "A"),
        team_b_average_score=team_average_rating(players, "B"),
        players=players,
    )


def team_average_rating(players: list[GamePlayerRead], side: str) -> int | None:
    ratings = [
        player.rating_before
        for player in players
        if player.side == side and player.rating_before is not None and player.rating_before > 0
    ]
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings))


def latest_season_id(db: Session) -> int | None:
    return db.scalar(
        select(Season.id)
        .where(Season.disabled_at.is_(None))
        .order_by(desc(Season.sort_order), desc(Season.id))
        .limit(1)
    )


def class_stats_by_player(
    db: Session,
    season_id: int,
) -> dict[int, dict[str, SeasonPlayerClassStats]]:
    rows = db.scalars(
        select(SeasonPlayerClassStats).where(SeasonPlayerClassStats.season_id == season_id)
    ).all()
    grouped: dict[int, dict[str, SeasonPlayerClassStats]] = defaultdict(dict)
    for row in rows:
        grouped[row.player_id][row.class_name] = row
    return grouped


def render_class_stats(rows: dict[str, SeasonPlayerClassStats]) -> list[ClassStatsRead]:
    rendered = []
    for class_name in CLASS_ORDER:
        row = rows.get(class_name)
        rendered.append(
            ClassStatsRead(
                class_name=class_name,
                wins=row.wins if row is not None else 0,
                losses=row.losses if row is not None else 0,
                win_rate=row.win_rate if row is not None else None,
            )
        )

    for class_name, row in sorted(rows.items()):
        if class_name in CLASS_ORDER:
            continue
        rendered.append(
            ClassStatsRead(
                class_name=class_name,
                wins=row.wins,
                losses=row.losses,
                win_rate=row.win_rate,
            )
        )
    return rendered


def render_class_total_stats(rows: dict[str, dict[str, int]]) -> list[ClassStatsRead]:
    rendered = []
    for class_name in CLASS_ORDER:
        row = rows.get(class_name, {"wins": 0, "losses": 0})
        rendered.append(
            ClassStatsRead(
                class_name=class_name,
                wins=row["wins"],
                losses=row["losses"],
                win_rate=win_rate(row["wins"], row["losses"]),
            )
        )

    for class_name, row in sorted(rows.items()):
        if class_name in CLASS_ORDER:
            continue
        rendered.append(
            ClassStatsRead(
                class_name=class_name,
                wins=row["wins"],
                losses=row["losses"],
                win_rate=win_rate(row["wins"], row["losses"]),
            )
        )
    return rendered


def podiums_by_player(db: Session) -> dict[int, dict[str, int]]:
    rows = db.execute(
        select(SeasonPlayerStats.player_id, SeasonPlayerStats.rank)
        .join(Season, Season.id == SeasonPlayerStats.season_id)
        .where(
            Season.status == SeasonStatus.CLOSED.value,
            SeasonPlayerStats.rank.in_([1, 2, 3]),
        )
    ).all()
    podiums: dict[int, dict[str, int]] = defaultdict(
        lambda: {"gold": 0, "silver": 0, "bronze": 0, "score": 0}
    )
    for player_id, rank in rows:
        if rank == 1:
            podiums[player_id]["gold"] += 1
            podiums[player_id]["score"] += 3
        elif rank == 2:
            podiums[player_id]["silver"] += 1
            podiums[player_id]["score"] += 2
        elif rank == 3:
            podiums[player_id]["bronze"] += 1
            podiums[player_id]["score"] += 1
    return dict(podiums)


def format_trophy(podium: dict[str, int] | None) -> str:
    if not podium or podium.get("score", 0) == 0:
        return "-"
    parts = []
    if podium.get("gold", 0):
        parts.append(f"🥇{podium['gold']}")
    if podium.get("silver", 0):
        parts.append(f"🥈{podium['silver']}")
    if podium.get("bronze", 0):
        parts.append(f"🥉{podium['bronze']}")
    return " ".join(parts)


def load_game_bundles(
    db: Session,
    season_id: int | None,
    all_seasons: bool,
) -> list[dict]:
    stmt = select(Game).where(Game.status == GameStatus.ACTIVE.value)
    if not all_seasons and season_id is not None:
        stmt = stmt.where(Game.season_id == season_id)
    games = list(
        db.scalars(
            stmt.order_by(desc(Game.played_at), desc(Game.legacy_row_number))
        ).all()
    )
    if not games:
        return []

    bundles = {game.id: {"game": game, "players": []} for game in games}
    player_rows = db.execute(
        select(GamePlayer, Player)
        .join(Player, Player.id == GamePlayer.player_id)
        .where(
            GamePlayer.game_id.in_([game.id for game in games]),
            Player.is_active.is_(True),
        )
        .order_by(GamePlayer.game_id, GamePlayer.side, GamePlayer.slot)
    ).all()
    for game_player, player in player_rows:
        bundles[game_player.game_id]["players"].append(
            {"game_player": game_player, "player": player}
        )
    return list(bundles.values())


def calculate_duo_stats(
    db: Session,
    season_id: int | None,
    all_seasons: bool,
) -> list[DuoStatsRead]:
    records: dict[tuple[int, int], dict] = {}

    for bundle in load_game_bundles(db, season_id=season_id, all_seasons=all_seasons):
        game = bundle["game"]
        sides: dict[str, list[dict]] = {"A": [], "B": []}
        for entry in bundle["players"]:
            sides.setdefault(entry["game_player"].side, []).append(entry)

        for side, side_players in sides.items():
            if len(side_players) < 2:
                continue
            won = side == game.winner_side
            for left, right in combinations(side_players, 2):
                left_player = left["player"]
                right_player = right["player"]
                player_ids = tuple(sorted([left_player.id, right_player.id]))
                player_names = sorted([left_player.display_name, right_player.display_name])
                record = records.setdefault(
                    player_ids,
                    {"players": player_names, "wins": 0, "losses": 0},
                )
                if won:
                    record["wins"] += 1
                else:
                    record["losses"] += 1

    rows = [
        DuoStatsRead(
            duo_name=" / ".join(record["players"]),
            players=record["players"],
            wins=record["wins"],
            losses=record["losses"],
            total_games=record["wins"] + record["losses"],
            win_rate=win_rate(record["wins"], record["losses"]),
        )
        for record in records.values()
    ]
    rows.sort(key=lambda row: (row.total_games, row.wins, row.win_rate or 0), reverse=True)
    return rows


def recent_games_for_player(
    db: Session,
    player_id: int,
    limit: int,
) -> list[RecentGameRead]:
    rows = db.execute(
        select(Game, GamePlayer)
        .join(GamePlayer, GamePlayer.game_id == Game.id)
        .where(GamePlayer.player_id == player_id, Game.status == GameStatus.ACTIVE.value)
        .order_by(desc(Game.played_at), desc(Game.legacy_row_number))
        .limit(limit)
    ).all()

    recent_games = []
    for game, game_player in rows:
        won = game_player.side == game.winner_side
        own_score = game.score_a if game_player.side == "A" else game.score_b
        other_score = game.score_b if game_player.side == "A" else game.score_a
        recent_games.append(
            RecentGameRead(
                game_id=game.id,
                legacy_game_id=game.legacy_game_id,
                played_at=game.played_at,
                class_name=game_player.class_name_at_game,
                score=f"{own_score}:{other_score}",
                result="승" if won else "패",
            )
        )
    return recent_games


def resolve_player(db: Session, name: str) -> Player:
    player = db.scalar(
        select(Player).where(
            Player.normalized_name == normalize_player_name(name),
            Player.is_active.is_(True),
        )
    )
    if player is None:
        raise HTTPException(status_code=404, detail=f"플레이어를 찾을 수 없습니다: {name}")
    return player


def win_rate(wins: int, losses: int) -> float | None:
    total = wins + losses
    if total == 0:
        return None
    return round(wins / total * 100, 1)


def display_tier(rating: int | None, tier: str | None) -> str | None:
    if rating is not None and rating <= 0:
        return "배치 중"
    return tier


def record_read(wins: int, losses: int) -> PairRecordRead:
    return PairRecordRead(wins=wins, losses=losses, win_rate=win_rate(wins, losses))


def empty_class_matrix() -> dict[str, dict[str, dict[str, int]]]:
    return {
        left_class: {
            right_class: {"wins": 0, "losses": 0}
            for right_class in CLASS_ORDER
        }
        for left_class in CLASS_ORDER
    }


def empty_class_head_to_head() -> ClassHeadToHeadRead:
    return matrix_read(empty_class_matrix())


def ensure_class_pair(
    matrix: dict[str, dict[str, dict[str, int]]],
    class1: str,
    class2: str,
) -> None:
    if class1 not in matrix:
        matrix[class1] = {
            right_class: {"wins": 0, "losses": 0}
            for right_class in matrix_classes(matrix)
        }
    if class2 not in matrix[class1]:
        matrix[class1][class2] = {"wins": 0, "losses": 0}
    for left_class in matrix:
        if class2 not in matrix[left_class]:
            matrix[left_class][class2] = {"wins": 0, "losses": 0}


def matrix_classes(matrix: dict[str, dict[str, dict[str, int]]]) -> list[str]:
    classes = set(matrix.keys())
    for row in matrix.values():
        classes.update(row.keys())
    return [class_name for class_name in CLASS_ORDER if class_name in classes] + sorted(
        classes.difference(CLASS_ORDER)
    )


def matrix_read(matrix: dict[str, dict[str, dict[str, int]]]) -> ClassHeadToHeadRead:
    classes = matrix_classes(matrix)
    return ClassHeadToHeadRead(
        classes=classes,
        matrix={
            left_class: {
                right_class: record_read(
                    matrix.get(left_class, {}).get(right_class, {}).get("wins", 0),
                    matrix.get(left_class, {}).get(right_class, {}).get("losses", 0),
                )
                for right_class in classes
            }
            for left_class in classes
        },
    )
