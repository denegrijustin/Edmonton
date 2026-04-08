"""Season state detection utilities."""

from enum import Enum

import pandas as pd

from config.settings import GAMES_IN_SEASON


class SeasonState(Enum):
    REGULAR_SEASON = "REGULAR_SEASON"
    PLAYOFFS = "PLAYOFFS"
    OFFSEASON = "OFFSEASON"


def detect_season_state(season: str, standings_df: pd.DataFrame) -> SeasonState:
    """Detect the current phase of the NHL season.

    Detection logic:
    - If playoff games (gameType 3) detected in team schedules → PLAYOFFS
    - Elif any team has fewer than 82 gamesPlayed → REGULAR_SEASON
    - Else → OFFSEASON

    Parameters
    ----------
    season : str
        Season string like ``"20252026"``.
    standings_df : pd.DataFrame
        Current standings from the NHL API.

    Returns
    -------
    SeasonState
    """
    # Check for playoff games using schedule metadata (not the unreliable
    # playoffs/carousel endpoint).
    try:
        from services.playoff_state import detect_playoff_state  # noqa: PLC0415

        ps = detect_playoff_state(standings_df, season=season)
        if ps.playoffs_started:
            return SeasonState.PLAYOFFS
    except Exception:
        pass

    if not standings_df.empty and "gamesPlayed" in standings_df.columns:
        min_gp = pd.to_numeric(standings_df["gamesPlayed"], errors="coerce").min()
        if pd.notna(min_gp) and min_gp < GAMES_IN_SEASON:
            return SeasonState.REGULAR_SEASON

    return SeasonState.OFFSEASON
