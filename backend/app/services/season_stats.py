from collections import defaultdict

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.enums import GameStatus
from app.models.game import Game, GamePlayer
from app.models.player import Player
from app.models.rating import RatingEvent, SeasonPlayerClassStats, SeasonPlayerStats
from app.models.scoring import ScoringRuleVersion
from app.models.season import Season
from app.services.scoring import LegacyMmrPolicy, PlayerRatingInput, ScoreConfig


def recompute_season_stats(db: Session, season_id: int) -> None:
    rule = active_rule_for_season(db, season_id)
    config = ScoreConfig.model_validate(rule.config if rule is not None else {})
    policy = LegacyMmrPolicy(config)

    db.execute(delete(RatingEvent).where(RatingEvent.season_id == season_id))
    db.execute(delete(SeasonPlayerClassStats).where(SeasonPlayerClassStats.season_id == season_id))
    db.execute(delete(SeasonPlayerStats).where(SeasonPlayerStats.season_id == season_id))

    ratings: dict[int, int] = defaultdict(int)
    totals: dict[int, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
    placement_all_character_counts: dict[int, int] = defaultdict(int)
    class_totals: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"wins": 0, "losses": 0}
    )

    games = db.scalars(
        select(Game)
        .where(Game.season_id == season_id, Game.status == GameStatus.ACTIVE.value)
        .order_by(Game.played_at, Game.created_at)
    ).all()

    for game in games:
        if game.winner_side is None or game.score_a is None or game.score_b is None:
            continue

        players_by_side = load_players_by_side(db, game.id)
        team_a = players_by_side.get("A", [])
        team_b = players_by_side.get("B", [])
        if not team_a or not team_b:
            continue

        rating_results = {
            result.player_id: result
            for result in policy.calculate_player_results(
                team_a=[
                    player_rating_input(
                        player,
                        ratings,
                        totals,
                        placement_all_character_counts,
                    )
                    for player in team_a
                ],
                team_b=[
                    player_rating_input(
                        player,
                        ratings,
                        totals,
                        placement_all_character_counts,
                    )
                    for player in team_b
                ],
                winner_side=game.winner_side,
                score_a=game.score_a,
                score_b=game.score_b,
            )
        }

        for side, game_players in players_by_side.items():
            won = side == game.winner_side
            for game_player in game_players:
                rating_result = rating_results[game_player.player_id]
                before_score = rating_result.before_score
                after_score = rating_result.after_score
                ratings[game_player.player_id] = after_score
                db.add(
                    RatingEvent(
                        game_id=game.id,
                        season_id=season_id,
                        player_id=game_player.player_id,
                        before_score=before_score,
                        after_score=after_score,
                        delta=rating_result.delta,
                        reason="game.result",
                    )
                )

                totals[game_player.player_id]["wins" if won else "losses"] += 1
                if (
                    won
                    and game_player.is_all_character_bonus
                    and totals[game_player.player_id]["wins"]
                    + totals[game_player.player_id]["losses"]
                    <= config.placement_game_count
                ):
                    placement_all_character_counts[game_player.player_id] += 1
                if game_player.class_name_at_game:
                    class_totals[
                        (game_player.player_id, game_player.class_name_at_game)
                    ]["wins" if won else "losses"] += 1

    ranked_player_ids = sorted(
        totals,
        key=lambda player_id: (
            ratings[player_id],
            totals[player_id]["wins"],
            -(totals[player_id]["losses"]),
        ),
        reverse=True,
    )
    for rank, player_id in enumerate(ranked_player_ids, start=1):
        wins = totals[player_id]["wins"]
        losses = totals[player_id]["losses"]
        db.add(
            SeasonPlayerStats(
                season_id=season_id,
                player_id=player_id,
                rank=rank,
                rating=ratings[player_id],
                games_played=wins + losses,
                wins=wins,
                losses=losses,
                win_rate=win_rate(wins, losses),
                tier=tier_for_rating(ratings[player_id], config),
                is_snapshot=False,
            )
        )

    for (player_id, class_name), record in class_totals.items():
        wins = record["wins"]
        losses = record["losses"]
        db.add(
            SeasonPlayerClassStats(
                season_id=season_id,
                player_id=player_id,
                class_name=class_name,
                wins=wins,
                losses=losses,
                win_rate=win_rate(wins, losses),
                is_snapshot=False,
            )
        )


def active_rule_for_season(db: Session, season_id: int) -> ScoringRuleVersion | None:
    season = db.get(Season, season_id)
    if season is not None and season.scoring_rule_version_id is not None:
        rule = db.get(ScoringRuleVersion, season.scoring_rule_version_id)
        if rule is not None:
            return rule

    return db.scalar(
        select(ScoringRuleVersion)
        .join(Game, Game.scoring_rule_version_id == ScoringRuleVersion.id)
        .where(Game.season_id == season_id)
        .order_by(desc(Game.played_at))
        .limit(1)
    )


def load_players_by_side(db: Session, game_id: str) -> dict[str, list[GamePlayer]]:
    rows = db.scalars(
        select(GamePlayer)
        .join(Player, Player.id == GamePlayer.player_id)
        .where(GamePlayer.game_id == game_id, Player.is_active.is_(True))
        .order_by(GamePlayer.side, GamePlayer.slot)
    ).all()
    grouped: dict[str, list[GamePlayer]] = defaultdict(list)
    for row in rows:
        grouped[row.side].append(row)
    return dict(grouped)


def player_rating_input(
    game_player: GamePlayer,
    ratings: dict[int, int],
    totals: dict[int, dict[str, int]],
    placement_all_character_counts: dict[int, int],
) -> PlayerRatingInput:
    total = totals[game_player.player_id]
    return PlayerRatingInput(
        player_id=game_player.player_id,
        side=game_player.side,
        rating=ratings[game_player.player_id],
        wins=total["wins"],
        losses=total["losses"],
        all_character_count=placement_all_character_counts[game_player.player_id],
        is_all_character_bonus=game_player.is_all_character_bonus,
    )


def win_rate(wins: int, losses: int) -> float | None:
    total = wins + losses
    if total == 0:
        return None
    return round(wins / total * 100, 1)


def tier_for_rating(rating: int, config: ScoreConfig) -> str:
    thresholds = config.tier_thresholds
    if rating >= thresholds.get("마스터", 1600):
        return "마스터"
    if rating >= thresholds.get("다이아", 1400):
        return "다이아"
    if rating >= thresholds.get("플래티넘", 1250):
        return "플래티넘"
    if rating >= thresholds.get("골드", 1100):
        return "골드"
    if rating >= thresholds.get("실버", 950):
        return "실버"
    return "아이언"
