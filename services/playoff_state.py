"""Track playoff state from existing NHL API data.

Provides helpers to query the current playoff bracket and determine a
team's standing within the postseason.
"""

from typing import Any, Dict, List, Optional

from providers.playoff_provider import get_playoff_bracket, get_playoff_series_list


def get_playoff_context(season: str) -> Dict[str, Any]:
    """Build a consolidated playoff context dictionary.

    Parameters
    ----------
    season : str
        Season string like ``"20252026"``.

    Returns
    -------
    dict
        ``{"active": bool, "series": list, "rounds": dict, "bracket_raw": dict}``
        On failure returns safe defaults with ``active=False``.
    """
    try:
        series = get_playoff_series_list(season)
        bracket = get_playoff_bracket(season)
        active = any(s.get("round", 0) >= 1 for s in series)

        rounds: Dict[int, List[Dict[str, Any]]] = {}
        for s in series:
            rnd = s.get("round", 0)
            rounds.setdefault(rnd, []).append(s)

        return {
            "active": active,
            "series": series,
            "rounds": rounds,
            "bracket_raw": bracket,
        }
    except Exception:
        return {"active": False, "series": [], "rounds": {}, "bracket_raw": {}}


def is_team_in_playoffs(team: str, series_list: List[Dict[str, Any]]) -> bool:
    """Return ``True`` if *team* appears in any series.

    Parameters
    ----------
    team : str
        Team abbreviation (e.g. ``"EDM"``).
    series_list : list of dict
        Series list from :func:`get_playoff_context` or
        :func:`providers.playoff_provider.get_playoff_series_list`.
    """
    for s in series_list:
        if team in (s.get("topSeed"), s.get("bottomSeed")):
            return True
    return False


def get_team_series(team: str, series_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the current active series for *team*.

    An active series is one where neither team has reached 4 wins.
    If multiple active series exist (shouldn't normally happen), the
    highest round is returned.

    Parameters
    ----------
    team : str
        Team abbreviation.
    series_list : list of dict
        Series list from the playoff provider.

    Returns
    -------
    dict or None
    """
    active: List[Dict[str, Any]] = []
    for s in series_list:
        if team not in (s.get("topSeed"), s.get("bottomSeed")):
            continue
        top_w = int(s.get("topSeedWins", 0))
        bot_w = int(s.get("bottomSeedWins", 0))
        if top_w < 4 and bot_w < 4:
            active.append(s)

    if not active:
        return None

    # Return the highest-round active series
    return max(active, key=lambda x: x.get("round", 0))


def get_team_playoff_record(team: str, series_list: List[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate series wins and losses for *team* across all rounds.

    Parameters
    ----------
    team : str
        Team abbreviation.
    series_list : list of dict
        Series list from the playoff provider.

    Returns
    -------
    dict
        ``{"wins": int, "losses": int}``
    """
    wins = 0
    losses = 0
    for s in series_list:
        top_seed = s.get("topSeed")
        bot_seed = s.get("bottomSeed")
        top_w = int(s.get("topSeedWins", 0))
        bot_w = int(s.get("bottomSeedWins", 0))

        if team == top_seed:
            wins += top_w
            losses += bot_w
        elif team == bot_seed:
            wins += bot_w
            losses += top_w

    return {"wins": wins, "losses": losses}
