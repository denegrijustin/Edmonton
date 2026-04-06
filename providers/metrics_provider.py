"""Team metrics computation from standings data."""

from typing import Any, Dict, Tuple

import pandas as pd
import streamlit as st

from config.settings import DEFAULT_TEAM, LEAGUE_AVG_GPG
from providers.standings_provider import get_standings


def compute_team_metrics(abbrev: str, standings_df: pd.DataFrame) -> Dict[str, Any]:
    """Derive all team metrics from standings data (no schedule load needed)."""
    defaults: Dict[str, Any] = {
        "abbrev": abbrev,
        "wins": 0, "losses": 0, "otl": 0,
        "points": 0, "gamesPlayed": 1,
        "goalFor": 0, "goalAgainst": 0, "goalDifferential": 0,
        "gf_per_game": LEAGUE_AVG_GPG, "ga_per_game": LEAGUE_AVG_GPG,
        "last10_gf_per_game": LEAGUE_AVG_GPG, "last10_ga_per_game": LEAGUE_AVG_GPG,
        "l10W": 0, "l10L": 0, "l10OTL": 0, "momentum": 50.0,
    }
    if standings_df.empty:
        return defaults

    row = standings_df[standings_df["teamAbbrev"] == abbrev]
    if row.empty:
        return defaults

    r = row.iloc[0]
    gp = max(int(r.get("gamesPlayed") or 1), 1)
    gf = float(r.get("goalFor") or 0)
    ga = float(r.get("goalAgainst") or 0)
    gf_pg = gf / gp if gf > 0 else LEAGUE_AVG_GPG
    ga_pg = ga / gp if ga > 0 else LEAGUE_AVG_GPG

    l10w = int(r.get("l10Wins") or 0)
    l10l = int(r.get("l10Losses") or 0)
    l10otl = int(r.get("l10OtLosses") or 0)
    l10_games = l10w + l10l + l10otl
    l10_pts = l10w * 2 + l10otl

    # Proxy last-10 GF/GA from win rate relative to season
    if l10_games >= 5:
        l10_win_rate = l10w / l10_games
    elif gp > 0:
        l10_win_rate = int(r.get("wins") or 0) / gp
    else:
        l10_win_rate = 0.5

    season_win_rate = int(r.get("wins") or 0) / gp
    relative_form = (l10_win_rate - season_win_rate) if season_win_rate > 0 else 0

    last10_gf_pg = max(gf_pg * (1 + relative_form * 0.4), 0.5)
    last10_ga_pg = max(ga_pg * (1 - relative_form * 0.4), 0.5)

    # Momentum from last-10 points pace vs expected (10 pts = average)
    expected_l10_pts = 10.0
    momentum = 50.0 + (l10_pts - expected_l10_pts) * 3.0
    momentum = float(max(20.0, min(80.0, momentum)))

    return {
        "abbrev": abbrev,
        "wins": int(r.get("wins") or 0),
        "losses": int(r.get("losses") or 0),
        "otl": int(r.get("otLosses") or 0),
        "points": int(r.get("points") or 0),
        "gamesPlayed": gp,
        "goalFor": gf,
        "goalAgainst": ga,
        "goalDifferential": float(r.get("goalDifferential") or 0),
        "gf_per_game": round(gf_pg, 3),
        "ga_per_game": round(ga_pg, 3),
        "last10_gf_per_game": round(last10_gf_pg, 3),
        "last10_ga_per_game": round(last10_ga_pg, 3),
        "l10W": l10w,
        "l10L": l10l,
        "l10OTL": l10otl,
        "momentum": round(momentum, 1),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def build_league_data() -> Tuple[pd.DataFrame, Dict[str, Dict]]:
    """Load standings and compute metrics for every team."""
    standings = get_standings()
    if standings.empty:
        return standings, {}
    metrics: Dict[str, Dict] = {}
    for _, row in standings.iterrows():
        abbrev = row.get("teamAbbrev")
        if abbrev:
            metrics[str(abbrev)] = compute_team_metrics(str(abbrev), standings)
    return standings, metrics
