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
    - If playoff series exist for this season → PLAYOFFS
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
    # Defer import to avoid circular dependency issues at module load time.
    try:
        from providers.playoff_provider import is_playoff_active  # noqa: PLC0415

        if is_playoff_active(season):
            return SeasonState.PLAYOFFS
    except Exception:
        pass

    if not standings_df.empty and "gamesPlayed" in standings_df.columns:
        min_gp = pd.to_numeric(standings_df["gamesPlayed"], errors="coerce").min()
        if pd.notna(min_gp) and min_gp < GAMES_IN_SEASON:
            return SeasonState.REGULAR_SEASON

    return SeasonState.OFFSEASON
