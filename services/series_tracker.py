"""Track individual playoff series state.

Provides helpers to compute the current state of a series (leading team,
completion, etc.) and to enrich a list of series with computed metadata.
"""

from typing import Any, Dict, List, Optional

_WINS_TO_CLINCH = 4


def compute_series_state(series: Dict[str, Any]) -> Dict[str, Any]:
    """Compute derived state for a single playoff series.

    Parameters
    ----------
    series : dict
        Series dict with keys ``topSeed``, ``bottomSeed``,
        ``topSeedWins``, ``bottomSeedWins``.

    Returns
    -------
    dict
        ``{"leading", "tied", "completed", "winner", "wins_to_advance",
          "status_text"}``
    """
    top = series.get("topSeed", "")
    bot = series.get("bottomSeed", "")
    top_w = int(series.get("topSeedWins", 0))
    bot_w = int(series.get("bottomSeedWins", 0))

    completed = top_w >= _WINS_TO_CLINCH or bot_w >= _WINS_TO_CLINCH
    max_wins = max(top_w, bot_w)
    wins_to_advance = max(_WINS_TO_CLINCH - max_wins, 0)

    if completed:
        winner = top if top_w >= _WINS_TO_CLINCH else bot
        leading = winner
        tied = False
        status_text = f"{winner} wins {top_w}-{bot_w}"
    elif top_w == bot_w:
        winner = None
        leading = None
        tied = True
        status_text = f"Tied {top_w}-{bot_w}"
    else:
        winner = None
        tied = False
        leading = top if top_w > bot_w else bot
        lead_w = max(top_w, bot_w)
        trail_w = min(top_w, bot_w)
        status_text = f"{leading} leads {lead_w}-{trail_w}"

    return {
        "leading": leading,
        "tied": tied,
        "completed": completed,
        "winner": winner,
        "wins_to_advance": wins_to_advance,
        "status_text": status_text,
    }


def is_series_complete(series: Dict[str, Any]) -> bool:
    """Return ``True`` if the series has been clinched.

    Parameters
    ----------
    series : dict
        Series dict with win counts.
    """
    top_w = int(series.get("topSeedWins", 0))
    bot_w = int(series.get("bottomSeedWins", 0))
    return top_w >= _WINS_TO_CLINCH or bot_w >= _WINS_TO_CLINCH


def get_series_winner(series: Dict[str, Any]) -> Optional[str]:
    """Return the winner's abbreviation, or ``None`` if still in progress.

    Parameters
    ----------
    series : dict
        Series dict with win counts and seed abbreviations.
    """
    top_w = int(series.get("topSeedWins", 0))
    bot_w = int(series.get("bottomSeedWins", 0))
    if top_w >= _WINS_TO_CLINCH:
        return series.get("topSeed")
    if bot_w >= _WINS_TO_CLINCH:
        return series.get("bottomSeed")
    return None


def build_bracket_state(series_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich each series with computed state fields.

    Parameters
    ----------
    series_list : list of dict
        Raw series list from the playoff provider.

    Returns
    -------
    list of dict
        Each entry is the original series dict merged with
        :func:`compute_series_state` output.
    """
    enriched: List[Dict[str, Any]] = []
    for s in series_list:
        entry = dict(s)
        entry.update(compute_series_state(s))
        enriched.append(entry)
    return enriched
