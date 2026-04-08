"""Series tracking logic for playoff matchups.

Parses playoff games, groups them into series, tracks scores,
identifies completed series, and locks results.
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def build_series_from_games(
    playoff_games: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group playoff games into series and compute current state.

    Each series is identified by the unique pair of teams in a matchup.
    Games are sorted by date to determine progression.

    Parameters
    ----------
    playoff_games : list of dict
        Each dict must have: gameId, gameDate, homeTeam, awayTeam,
        homeScore, awayScore, isCompleted.

    Returns
    -------
    list of dict
        Each series dict contains:
        - teams: tuple of (teamA, teamB)
        - topSeed / bottomSeed: team abbreviations
        - topSeedWins / bottomSeedWins: current series score
        - games: list of game dicts in this series
        - completed_games: list of completed game dicts
        - next_game: next scheduled game or None
        - is_complete: whether series is over (one team has 4 wins)
        - winner: winning team or None
        - round: playoff round
    """
    if not playoff_games:
        return []

    # Group games by matchup (frozenset of two teams)
    matchup_games: Dict[frozenset, List[Dict[str, Any]]] = {}
    for g in playoff_games:
        home = g.get("homeTeam", "")
        away = g.get("awayTeam", "")
        if not home or not away:
            continue
        key = frozenset([home, away])
        matchup_games.setdefault(key, []).append(g)

    series_list: List[Dict[str, Any]] = []
    for matchup_key, games in matchup_games.items():
        teams = sorted(matchup_key)
        if len(teams) != 2:
            continue

        team_a, team_b = teams[0], teams[1]

        # Sort games by date
        sorted_games = sorted(
            games,
            key=lambda g: (
                pd.to_datetime(g.get("gameDate"), errors="coerce") or pd.Timestamp.min,
                g.get("gameId", 0),
            ),
        )

        # Count wins from completed games
        wins: Dict[str, int] = {team_a: 0, team_b: 0}
        completed_games: List[Dict[str, Any]] = []
        next_game: Optional[Dict[str, Any]] = None

        for g in sorted_games:
            if g.get("isCompleted"):
                completed_games.append(g)
                home = g.get("homeTeam", "")
                away = g.get("awayTeam", "")
                hs = _safe_int(g.get("homeScore"))
                as_ = _safe_int(g.get("awayScore"))
                if hs is not None and as_ is not None:
                    if hs > as_:
                        if home in wins:
                            wins[home] += 1
                    elif as_ > hs:
                        if away in wins:
                            wins[away] += 1
            elif next_game is None:
                next_game = g

        is_complete = wins[team_a] >= 4 or wins[team_b] >= 4
        winner = None
        if wins[team_a] >= 4:
            winner = team_a
        elif wins[team_b] >= 4:
            winner = team_b

        # Determine top seed: team with home-ice in game 1
        top_seed = team_a
        bottom_seed = team_b
        if sorted_games:
            first_home = sorted_games[0].get("homeTeam", "")
            if first_home == team_b:
                top_seed, bottom_seed = team_b, team_a

        playoff_round = 1
        for g in sorted_games:
            r = g.get("round", 1)
            if isinstance(r, (int, float)) and r > 0:
                playoff_round = int(r)
                break

        series_list.append({
            "teams": (top_seed, bottom_seed),
            "topSeed": top_seed,
            "bottomSeed": bottom_seed,
            "topSeedWins": wins.get(top_seed, 0),
            "bottomSeedWins": wins.get(bottom_seed, 0),
            "games": sorted_games,
            "completed_games": completed_games,
            "next_game": next_game,
            "is_complete": is_complete,
            "winner": winner,
            "round": playoff_round,
            "seriesStatus": _build_status_string(
                top_seed, bottom_seed,
                wins.get(top_seed, 0), wins.get(bottom_seed, 0),
                is_complete, winner,
            ),
        })

    # Sort by round, then by teams
    series_list.sort(key=lambda s: (s["round"], s["topSeed"]))
    return series_list


def get_completed_series(
    series_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return only completed series (one team has 4 wins)."""
    return [s for s in series_list if s.get("is_complete")]


def get_active_series(
    series_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return only active (unresolved) series."""
    return [s for s in series_list if not s.get("is_complete")]


def _build_status_string(
    top: str,
    bottom: str,
    top_wins: int,
    bottom_wins: int,
    is_complete: bool,
    winner: Optional[str],
) -> str:
    """Build a human-readable series status string."""
    if is_complete and winner:
        return f"{winner} wins 4-{min(top_wins, bottom_wins)}"
    if top_wins == bottom_wins:
        if top_wins == 0:
            return "Series not started"
        return f"Series tied {top_wins}-{bottom_wins}"
    leader = top if top_wins > bottom_wins else bottom
    trail = bottom if leader == top else top
    return f"{leader} leads {max(top_wins, bottom_wins)}-{min(top_wins, bottom_wins)}"


def _safe_int(val: Any) -> Optional[int]:
    """Safely convert a value to int."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
