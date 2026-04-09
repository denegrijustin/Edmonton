"""Fail-safe season mode detection with safe fallback.

Extends :class:`utils.state_detection.SeasonState` with finer-grained
application modes such as ``PLAYOFF_RACE`` and ``SAFE_FALLBACK``.
"""

from enum import Enum
from typing import Any, Dict

import pandas as pd

from config.settings import GAMES_IN_SEASON
from providers.playoff_provider import is_playoff_active


class AppMode(Enum):
    """Application-level season mode (superset of SeasonState)."""

    REGULAR_SEASON = "REGULAR_SEASON"
    PLAYOFF_RACE = "PLAYOFF_RACE"
    PLAYOFFS = "PLAYOFFS"
    OFFSEASON = "OFFSEASON"
    SAFE_FALLBACK = "SAFE_FALLBACK"


_SESSION_KEY = "last_confirmed_app_mode"


def detect_app_mode(season: str, standings_df: pd.DataFrame) -> AppMode:
    """Detect current application mode from live data.

    Detection order
    ---------------
    1. Playoff series active → ``PLAYOFFS``
    2. Any team > 75 GP but < 82 and playoffs not confirmed → ``PLAYOFF_RACE``
    3. Any team < 82 GP → ``REGULAR_SEASON``
    4. All teams at 82 GP → ``OFFSEASON``

    Falls back to ``SAFE_FALLBACK`` on any exception.

    Parameters
    ----------
    season : str
        Season string like ``"20252026"``.
    standings_df : pd.DataFrame
        Current standings from the NHL API.

    Returns
    -------
    AppMode
    """
    try:
        # 1. Check for active playoffs
        if is_playoff_active(season):
            return AppMode.PLAYOFFS

        if standings_df.empty or "gamesPlayed" not in standings_df.columns:
            return AppMode.SAFE_FALLBACK

        gp_col = pd.to_numeric(standings_df["gamesPlayed"], errors="coerce")
        max_gp = gp_col.max()
        min_gp = gp_col.min()

        if pd.isna(max_gp) or pd.isna(min_gp):
            return AppMode.SAFE_FALLBACK

        max_gp = int(max_gp)
        min_gp = int(min_gp)

        # 2. Late regular season – playoff race
        if max_gp > 75 and min_gp < GAMES_IN_SEASON:
            return AppMode.PLAYOFF_RACE

        # 3. Regular season in progress
        if min_gp < GAMES_IN_SEASON:
            return AppMode.REGULAR_SEASON

        # 4. All teams completed 82 games
        return AppMode.OFFSEASON

    except Exception:
        return AppMode.SAFE_FALLBACK


def get_safe_mode(session_state: Dict[str, Any]) -> AppMode:
    """Return last confirmed mode from *session_state*, or ``SAFE_FALLBACK``.

    Parameters
    ----------
    session_state : dict
        Mutable session dictionary (e.g. ``st.session_state``).

    Returns
    -------
    AppMode
    """
    mode = session_state.get(_SESSION_KEY)
    if isinstance(mode, AppMode):
        return mode
    return AppMode.SAFE_FALLBACK


def update_mode_state(session_state: Dict[str, Any], new_mode: AppMode) -> None:
    """Persist *new_mode* into *session_state*.

    ``SAFE_FALLBACK`` is only stored when no prior mode exists, preventing
    a transient failure from overwriting a known-good mode.

    Parameters
    ----------
    session_state : dict
        Mutable session dictionary.
    new_mode : AppMode
        The newly detected mode.
    """
    if new_mode is AppMode.SAFE_FALLBACK:
        if _SESSION_KEY not in session_state:
            session_state[_SESSION_KEY] = new_mode
    else:
        session_state[_SESSION_KEY] = new_mode
