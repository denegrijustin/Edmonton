"""NHL API playoff bracket and series data provider."""

from typing import Any, Dict, List

import streamlit as st

from config.settings import BASE, SEASON
from data.loaders import get_json


@st.cache_data(ttl=3600, show_spinner=False)
def get_playoff_bracket(season: str = SEASON) -> Dict[str, Any]:
    """Fetch playoff bracket carousel data for the given season.

    Parameters
    ----------
    season : str
        Season string like ``"20252026"``.

    Returns
    -------
    dict
        Raw bracket data, or empty dict on failure / not-yet-started.
    """
    try:
        data = get_json(f"{BASE}/playoffs/carousel/{season}")
        if isinstance(data, dict) and data:
            return data
    except Exception:
        pass
    return {}


@st.cache_data(ttl=3600, show_spinner=False)
def get_playoff_series_list(season: str = SEASON) -> List[Dict[str, Any]]:
    """Return a normalised list of playoff series for the season.

    Each entry contains::

        {
            "seriesLetter": "A",
            "round": 1,
            "topSeed": "EDM",
            "bottomSeed": "CGY",
            "topSeedWins": 3,
            "bottomSeedWins": 1,
            "seriesStatus": "EDM leads 3-1",
            "nextGameDate": "2025-04-20",
        }

    Returns empty list on failure or before playoffs begin.
    """
    bracket = get_playoff_bracket(season)
    if not bracket:
        return []

    series_out: List[Dict[str, Any]] = []

    # The carousel endpoint may use different shapes; try common keys.
    rounds_data = bracket.get("rounds") or bracket.get("series") or []
    if not rounds_data and isinstance(bracket.get("0"), dict):
        # Some seasons use numeric round keys at the root
        rounds_data = list(bracket.values())

    for round_obj in rounds_data:
        if not isinstance(round_obj, dict):
            continue
        round_num = int(round_obj.get("roundNumber") or round_obj.get("round") or 0)
        series_list = round_obj.get("series") or []
        for s in series_list:
            if not isinstance(s, dict):
                continue
            top = s.get("topSeedTeam") or s.get("team1") or {}
            bot = s.get("bottomSeedTeam") or s.get("team2") or {}
            top_abbrev = top.get("abbrev") or top.get("triCode") or ""
            bot_abbrev = bot.get("abbrev") or bot.get("triCode") or ""
            series_out.append(
                {
                    "seriesLetter": s.get("seriesLetter") or s.get("letter") or "",
                    "round": round_num,
                    "topSeed": top_abbrev,
                    "bottomSeed": bot_abbrev,
                    "topSeedWins": int(s.get("topSeedWins") or s.get("team1Wins") or 0),
                    "bottomSeedWins": int(
                        s.get("bottomSeedWins") or s.get("team2Wins") or 0
                    ),
                    "seriesStatus": s.get("seriesStatus") or s.get("statusDescription") or "",
                    "nextGameDate": s.get("nextGameDate") or "",
                }
            )

    return series_out


@st.cache_data(ttl=3600, show_spinner=False)
def is_playoff_active(season: str = SEASON) -> bool:
    """Return True if playoff series data with round ≥ 1 exists for *season*."""
    try:
        series = get_playoff_series_list(season)
        return any(s.get("round", 0) >= 1 for s in series)
    except Exception:
        return False
