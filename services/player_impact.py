"""Player impact analysis from real box-score data.

All impact scores are derived exclusively from actual game boxscores —
no fabricated or external data is used.
"""

from typing import Any, Dict, List

from api.nhl_api import fetch_boxscore

_LABEL = "Estimated Player Impact (box-score model)"


def compute_player_impact(game_ids: List[int], team: str) -> List[Dict[str, Any]]:
    """Compute impact scores for players on *team* from boxscore data.

    Impact formula per game::

        goals × 3 + assists × 2 + plusMinus + shots × 0.2

    Aggregated as total impact divided by games played.

    Parameters
    ----------
    game_ids : list of int
        Game IDs to analyse.
    team : str
        Team abbreviation.

    Returns
    -------
    list of dict
        Sorted by ``impact_score`` descending.  Each entry contains
        ``name``, ``position``, ``games``, ``impact_score``, ``goals``,
        ``assists``, ``plus_minus``, and ``label``.
        Returns empty list when no data is available.
    """
    if not game_ids:
        return []

    # Accumulate per-player stats across games
    players: Dict[str, Dict[str, Any]] = {}

    for gid in game_ids:
        try:
            box = fetch_boxscore(gid)
            if not box:
                continue

            _extract_team_players(box, team, players)
        except Exception:
            continue

    if not players:
        return []

    # Compute impact scores
    result: List[Dict[str, Any]] = []
    for pid, p in players.items():
        games = p.get("games", 1) or 1
        goals = p.get("goals", 0)
        assists = p.get("assists", 0)
        plus_minus = p.get("plusMinus", 0)
        shots = p.get("shots", 0)

        impact = (goals * 3 + assists * 2 + plus_minus + shots * 0.2) / games

        result.append({
            "name": p.get("name", pid),
            "position": p.get("position", ""),
            "games": games,
            "impact_score": round(impact, 2),
            "goals": goals,
            "assists": assists,
            "plus_minus": plus_minus,
            "label": _LABEL,
        })

    result.sort(key=lambda x: x["impact_score"], reverse=True)
    return result


def _extract_team_players(
    box: Dict[str, Any],
    team: str,
    players: Dict[str, Dict[str, Any]],
) -> None:
    """Extract player stats from a boxscore and accumulate into *players*.

    Supports the NHL API v1 boxscore shape where team data lives under
    ``playerByGameStats`` or ``boxscore`` → ``teams``.
    """
    # Try NHL API v1 shape: playerByGameStats → {awayTeam, homeTeam}
    pbgs = box.get("playerByGameStats") or {}
    for side in ("awayTeam", "homeTeam"):
        side_data = pbgs.get(side) or box.get(side) or {}
        side_abbrev = side_data.get("abbrev") or ""
        if side_abbrev != team:
            # Fallback: check nested team info
            team_info = side_data.get("teamAbbrev") or side_data.get("triCode") or ""
            if team_info != team:
                continue

        # Players may be grouped by position
        for category in ("forwards", "defense", "goalies"):
            for p in side_data.get(category, []):
                _accumulate_player(p, players)


def _accumulate_player(
    player_data: Dict[str, Any],
    players: Dict[str, Dict[str, Any]],
) -> None:
    """Add a single player's game stats to the accumulator."""
    pid = str(
        player_data.get("playerId")
        or player_data.get("id")
        or player_data.get("name", {}).get("default", "")
    )
    if not pid:
        return

    name_obj = player_data.get("name") or {}
    name = name_obj.get("default", "") if isinstance(name_obj, dict) else str(name_obj)
    position = player_data.get("position") or player_data.get("positionCode") or ""

    if pid not in players:
        players[pid] = {
            "name": name,
            "position": position,
            "games": 0,
            "goals": 0,
            "assists": 0,
            "plusMinus": 0,
            "shots": 0,
        }

    entry = players[pid]
    entry["games"] += 1
    entry["goals"] += int(player_data.get("goals", 0))
    entry["assists"] += int(player_data.get("assists", 0))
    entry["plusMinus"] += int(player_data.get("plusMinus", 0))
    entry["shots"] += int(player_data.get("shots") or player_data.get("sog", 0))


def get_top_impact_players(impact_list: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
    """Return the top *n* players by impact score.

    Parameters
    ----------
    impact_list : list of dict
        Output of :func:`compute_player_impact`.
    n : int
        Number of players to return.
    """
    return impact_list[:n]


def get_bottom_impact_players(
    impact_list: List[Dict[str, Any]],
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Return the bottom *n* players by impact score.

    Parameters
    ----------
    impact_list : list of dict
        Output of :func:`compute_player_impact`.
    n : int
        Number of players to return.
    """
    return impact_list[-n:] if len(impact_list) >= n else list(impact_list)
