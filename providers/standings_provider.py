"""NHL standings data provider."""

from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from config.settings import BASE
from data.loaders import flatten_dict, first_non_null, get_json


@st.cache_data(ttl=3600, show_spinner=False)
def get_standings() -> pd.DataFrame:
    """Fetch current NHL standings and return a normalised DataFrame."""
    data = get_json(f"{BASE}/standings/now")
    raw = data.get("standings", data if isinstance(data, list) else [])
    rows: List[Dict[str, Any]] = []
    for team in raw:
        flat = flatten_dict(team)
        rows.append(
            {
                "teamName": first_non_null(flat, ["teamName.default", "teamCommonName.default", "teamName"]),
                "teamAbbrev": first_non_null(flat, ["teamAbbrev.default", "teamAbbrev", "abbrev"]),
                "conference": first_non_null(flat, ["conferenceName", "conferenceAbbrev"]),
                "division": first_non_null(flat, ["divisionName", "divisionAbbrev"]),
                "gamesPlayed": first_non_null(flat, ["gamesPlayed"]),
                "points": first_non_null(flat, ["points"]),
                "wins": first_non_null(flat, ["wins"]),
                "losses": first_non_null(flat, ["losses"]),
                "otLosses": first_non_null(flat, ["otLosses"]),
                "goalFor": first_non_null(flat, ["goalFor", "goalsFor"]),
                "goalAgainst": first_non_null(flat, ["goalAgainst", "goalsAgainst"]),
                "goalDifferential": first_non_null(flat, ["goalDifferential"]),
                "pointPctg": first_non_null(flat, ["pointPctg", "pointsPctg"]),
                "conferenceSequence": first_non_null(flat, ["conferenceSequence"]),
                "divisionSequence": first_non_null(flat, ["divisionSequence"]),
                "wildcardSequence": first_non_null(flat, ["wildcardSequence"]),
                "l10Wins": first_non_null(flat, ["l10Wins"]),
                "l10Losses": first_non_null(flat, ["l10Losses"]),
                "l10OtLosses": first_non_null(flat, ["l10OtLosses"]),
            }
        )
    df = pd.DataFrame(rows)
    numeric_cols = [
        "gamesPlayed", "points", "wins", "losses", "otLosses",
        "goalFor", "goalAgainst", "goalDifferential",
        "conferenceSequence", "divisionSequence", "wildcardSequence",
        "l10Wins", "l10Losses", "l10OtLosses",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
