"""Team name / abbreviation mapping helpers."""

from typing import Dict

import pandas as pd


def build_team_name_map(standings_df: pd.DataFrame) -> Dict[str, str]:
    """Build ``{abbrev: full_name}`` lookup from standings data."""
    team_name_map: Dict[str, str] = {}
    if standings_df.empty:
        return team_name_map
    for _, row in standings_df.iterrows():
        ab = row.get("teamAbbrev")
        nm = row.get("teamName")
        if ab:
            team_name_map[str(ab)] = str(nm) if nm else str(ab)
    return team_name_map
