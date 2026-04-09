"""Unified NHL API client.

Thin wrapper that consolidates all NHL API access into one module.
Re-exports common helpers from ``data.loaders`` for convenience.
"""

from typing import Any, Dict

import streamlit as st

from config.settings import BASE, SEASON, TIMEOUT
from data.loaders import first_non_null, flatten_dict, get_json, safe_get

# Re-export helpers so callers can do ``from api.nhl_api import get_json, …``
__all__ = [
    "get_json",
    "flatten_dict",
    "first_non_null",
    "safe_get",
    "fetch_standings",
    "fetch_schedule",
    "fetch_boxscore",
    "fetch_play_by_play",
    "fetch_roster",
    "fetch_playoff_bracket",
    "fetch_scoreboard",
    "LIVE_TTL",
    "STATIC_TTL",
]

# Cache durations (seconds)
LIVE_TTL: int = 300      # 5 min – scoreboard, boxscore, play-by-play
STATIC_TTL: int = 3600   # 1 hr  – standings, schedule, roster, bracket


# ---------------------------------------------------------------------------
# Live-data endpoints (TTL = LIVE_TTL)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=LIVE_TTL, show_spinner=False)
def fetch_scoreboard() -> Dict[str, Any]:
    """Return the current live scoreboard from ``/score/now``."""
    try:
        return get_json(f"{BASE}/score/now")
    except Exception:
        return {}


@st.cache_data(ttl=LIVE_TTL, show_spinner=False)
def fetch_boxscore(game_id: int) -> Dict[str, Any]:
    """Return boxscore data for *game_id* from ``/gamecenter/{id}/boxscore``."""
    try:
        return get_json(f"{BASE}/gamecenter/{game_id}/boxscore")
    except Exception:
        return {}


@st.cache_data(ttl=LIVE_TTL, show_spinner=False)
def fetch_play_by_play(game_id: int) -> Dict[str, Any]:
    """Return play-by-play data for *game_id* from ``/gamecenter/{id}/play-by-play``."""
    try:
        return get_json(f"{BASE}/gamecenter/{game_id}/play-by-play")
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Static-data endpoints (TTL = STATIC_TTL)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=STATIC_TTL, show_spinner=False)
def fetch_standings() -> Dict[str, Any]:
    """Return current NHL standings from ``/standings/now``."""
    try:
        return get_json(f"{BASE}/standings/now")
    except Exception:
        return {}


@st.cache_data(ttl=STATIC_TTL, show_spinner=False)
def fetch_schedule(team: str, season: str = SEASON) -> Dict[str, Any]:
    """Return club schedule for *team* and *season* from ``/club-schedule-season``."""
    try:
        return get_json(f"{BASE}/club-schedule-season/{team}/{season}")
    except Exception:
        return {}


@st.cache_data(ttl=STATIC_TTL, show_spinner=False)
def fetch_roster(team: str, season: str = SEASON) -> Dict[str, Any]:
    """Return roster for *team* and *season* from ``/roster/{team}/{season}``."""
    try:
        return get_json(f"{BASE}/roster/{team}/{season}")
    except Exception:
        return {}


@st.cache_data(ttl=STATIC_TTL, show_spinner=False)
def fetch_playoff_bracket(season: str = SEASON) -> Dict[str, Any]:
    """Return playoff bracket/carousel for *season* from ``/playoffs/carousel``."""
    try:
        return get_json(f"{BASE}/playoffs/carousel/{season}")
    except Exception:
        return {}
