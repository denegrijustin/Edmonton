"""Player impact ranking engine.

Computes player impact scores from real player/game data only.
Falls back to box-score-based model when advanced stats are unavailable.
All impact values are clearly labeled as estimated/model-derived.
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from data.loaders import get_json
from config.settings import BASE, SEASON


MODEL_LABEL = "Box Score Impact Model"
MODEL_DESCRIPTION = (
    "Impact scores are estimated from available box-score stats including "
    "goals, assists, shots, plus/minus, blocked shots, and save percentage. "
    "This is not an official NHL metric."
)


def compute_player_impact(
    team: str,
    team_games: pd.DataFrame,
    season: str = SEASON,
    last_n: Optional[int] = None,
    result_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compute player impact rankings from real game data.

    Parameters
    ----------
    team : str
        Team abbreviation.
    team_games : pd.DataFrame
        Team game log with gameId, result, etc.
    season : str
        Season string.
    last_n : int, optional
        If provided, only use last N games.
    result_filter : str, optional
        "W" for wins only, "L" for losses only, None for all.

    Returns
    -------
    list of dict
        Player impact entries sorted by impact score descending.
    """
    if team_games.empty:
        return []

    # Apply filters
    games = team_games.copy()
    if result_filter:
        games = games[games["result"] == result_filter]
    if last_n:
        games = games.tail(last_n)
    if games.empty:
        return []

    game_ids = games["gameId"].tolist()

    # Collect player stats from boxscores
    player_stats = _collect_player_stats(game_ids, team)
    if not player_stats:
        return []

    # Compute impact scores
    impact_list = _compute_box_score_impact(player_stats)
    return impact_list


def _collect_player_stats(
    game_ids: List[int],
    team: str,
) -> Dict[str, Dict[str, Any]]:
    """Collect aggregated player stats from boxscores."""
    player_agg: Dict[str, Dict[str, Any]] = {}

    for gid in game_ids:
        try:
            box = get_json(f"{BASE}/gamecenter/{gid}/boxscore")
            if not box:
                continue
            _extract_players_from_boxscore(box, team, player_agg)
        except Exception:
            continue

    return player_agg


def _extract_players_from_boxscore(
    box: Dict[str, Any],
    team: str,
    player_agg: Dict[str, Dict[str, Any]],
) -> None:
    """Extract player stats from a single boxscore."""
    player_by_game = box.get("playerByGameStats", {})
    if not player_by_game:
        return

    # Determine which side is our team
    home_team = box.get("homeTeam", {})
    away_team = box.get("awayTeam", {})
    home_abbrev = home_team.get("abbrev", "")
    away_abbrev = away_team.get("abbrev", "")

    if home_abbrev == team:
        team_key = "homeTeam"
    elif away_abbrev == team:
        team_key = "awayTeam"
    else:
        return

    team_stats = player_by_game.get(team_key, {})

    # Process forwards and defense
    for pos_group in ["forwards", "defense"]:
        players = team_stats.get(pos_group, [])
        if not isinstance(players, list):
            continue
        for p in players:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("playerId", ""))
            if not pid:
                continue
            name_obj = p.get("name", {})
            name = name_obj.get("default", "") if isinstance(name_obj, dict) else str(name_obj)

            if pid not in player_agg:
                player_agg[pid] = {
                    "playerId": pid,
                    "name": name,
                    "position": pos_group[:-1].title() if pos_group != "defense" else "Defense",
                    "headshot": p.get("headshot", ""),
                    "games": 0,
                    "goals": 0,
                    "assists": 0,
                    "shots": 0,
                    "plusMinus": 0,
                    "blockedShots": 0,
                    "hits": 0,
                    "pim": 0,
                    "toi_seconds": 0,
                }

            stats = player_agg[pid]
            stats["games"] += 1
            stats["goals"] += _safe_stat(p, "goals")
            stats["assists"] += _safe_stat(p, "assists")
            stats["shots"] += _safe_stat(p, "sog", "shots")
            stats["plusMinus"] += _safe_stat(p, "plusMinus")
            stats["blockedShots"] += _safe_stat(p, "blockedShots", "blocks")
            stats["hits"] += _safe_stat(p, "hits")
            stats["pim"] += _safe_stat(p, "pim", "penaltyMinutes")
            stats["toi_seconds"] += _parse_toi(p.get("toi", "0:00"))

    # Process goalies
    goalies = team_stats.get("goalies", [])
    if isinstance(goalies, list):
        for p in goalies:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("playerId", ""))
            if not pid:
                continue
            name_obj = p.get("name", {})
            name = name_obj.get("default", "") if isinstance(name_obj, dict) else str(name_obj)

            if pid not in player_agg:
                player_agg[pid] = {
                    "playerId": pid,
                    "name": name,
                    "position": "Goalie",
                    "headshot": p.get("headshot", ""),
                    "games": 0,
                    "saves": 0,
                    "goalsAgainst": 0,
                    "shotsAgainst": 0,
                    "savePct": 0.0,
                    "toi_seconds": 0,
                }

            stats = player_agg[pid]
            stats["games"] += 1
            saves = _safe_stat(p, "saveShotsAgainst", "saves")
            ga = _safe_stat(p, "goalsAgainst")
            sa = _safe_stat(p, "shotsAgainst", "saveShotsAgainst")
            stats["saves"] = stats.get("saves", 0) + saves
            stats["goalsAgainst"] = stats.get("goalsAgainst", 0) + ga
            stats["shotsAgainst"] = stats.get("shotsAgainst", 0) + (sa if sa > 0 else saves + ga)
            stats["toi_seconds"] += _parse_toi(p.get("toi", "0:00"))


def _compute_box_score_impact(
    player_stats: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compute impact scores from box-score stats.

    Skaters: goals×3 + assists×2 + shots×0.2 + plusMinus×1.5
             + blockedShots×0.5 - pim×0.3

    Goalies: saves×0.1 - goalsAgainst×2 + shutout_bonus(3)
             + (savePct - 0.900)×20
    """
    results: List[Dict[str, Any]] = []

    for pid, stats in player_stats.items():
        games = max(stats.get("games", 1), 1)
        position = stats.get("position", "")

        if position == "Goalie":
            saves = stats.get("saves", 0)
            ga = stats.get("goalsAgainst", 0)
            sa = stats.get("shotsAgainst", 0)
            sv_pct = saves / max(sa, 1) if sa > 0 else 0.0
            shutout_bonus = 3.0 if ga == 0 and games == 1 else 0.0

            raw_impact = (
                saves * 0.1
                - ga * 2.0
                + shutout_bonus
                + (sv_pct - 0.900) * 20.0
            )
            impact_per_game = raw_impact / games

            results.append({
                "playerId": pid,
                "name": stats.get("name", ""),
                "position": "G",
                "headshot": stats.get("headshot", ""),
                "games": games,
                "impact_score": round(impact_per_game, 2),
                "raw_impact": round(raw_impact, 2),
                "key_stats": f"SV%: {sv_pct:.3f}, GA: {ga}",
                "model": MODEL_LABEL,
            })
        else:
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            shots = stats.get("shots", 0)
            pm = stats.get("plusMinus", 0)
            blocks = stats.get("blockedShots", 0)
            pim = stats.get("pim", 0)

            raw_impact = (
                goals * 3.0
                + assists * 2.0
                + shots * 0.2
                + pm * 1.5
                + blocks * 0.5
                - pim * 0.3
            )
            impact_per_game = raw_impact / games

            pos_code = "F" if "forward" in position.lower() else "D"
            results.append({
                "playerId": pid,
                "name": stats.get("name", ""),
                "position": pos_code,
                "headshot": stats.get("headshot", ""),
                "games": games,
                "impact_score": round(impact_per_game, 2),
                "raw_impact": round(raw_impact, 2),
                "key_stats": f"G: {goals}, A: {assists}, +/-: {pm:+d}",
                "model": MODEL_LABEL,
            })

    results.sort(key=lambda x: x["impact_score"], reverse=True)
    return results


def get_top_bottom_players(
    impact_list: List[Dict[str, Any]],
    top_n: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return top N positive and bottom N negative impact players."""
    if not impact_list:
        return {"top": [], "bottom": []}
    return {
        "top": impact_list[:top_n],
        "bottom": impact_list[-top_n:][::-1] if len(impact_list) >= top_n else [],
    }


def _safe_stat(player: Dict, *keys: str) -> int:
    """Safely extract a numeric stat from a player dict."""
    for k in keys:
        val = player.get(k)
        if val is not None:
            try:
                return int(float(val))
            except (ValueError, TypeError):
                pass
    return 0


def _parse_toi(val: Any) -> int:
    """Parse TOI string 'MM:SS' to seconds."""
    if not val:
        return 0
    s = str(val)
    if ":" in s:
        try:
            parts = s.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0
