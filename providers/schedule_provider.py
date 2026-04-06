"""NHL schedule and game data provider."""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from config.settings import BASE, DEFAULT_TEAM, SEASON
from data.loaders import (
    flatten_dict,
    first_non_null,
    get_json,
    points_from_result,
    zscore,
)


@st.cache_data(ttl=3600, show_spinner=False)
def get_schedule(team: str = DEFAULT_TEAM, season: str = SEASON) -> pd.DataFrame:
    """Fetch the full-season schedule for a single team."""
    data = get_json(f"{BASE}/club-schedule-season/{team}/{season}")
    games: List[Dict[str, Any]] = []
    containers: List[list] = []
    if isinstance(data, dict):
        if isinstance(data.get("games"), list):
            containers.append(data["games"])
        if isinstance(data.get("gameWeek"), list):
            for wk in data["gameWeek"]:
                if isinstance(wk, dict) and isinstance(wk.get("games"), list):
                    containers.append(wk["games"])
    for game_list in containers:
        for g in game_list:
            flat = flatten_dict(g)
            game_id = first_non_null(flat, ["id", "gameId"])
            game_date = first_non_null(flat, ["gameDate", "startTimeUTC", "startTime"])
            away = first_non_null(flat, ["awayTeam.abbrev"])
            home = first_non_null(flat, ["homeTeam.abbrev"])
            away_score = first_non_null(flat, ["awayTeam.score", "awayScore"])
            home_score = first_non_null(flat, ["homeTeam.score", "homeScore"])
            game_state = str(first_non_null(flat, ["gameState", "gameScheduleState"], "")).upper()
            game_type = first_non_null(flat, ["gameType"])
            if game_id:
                games.append(
                    {
                        "gameId": int(game_id),
                        "gameDate": pd.to_datetime(game_date, errors="coerce"),
                        "awayTeam": away,
                        "homeTeam": home,
                        "awayScore": away_score,
                        "homeScore": home_score,
                        "gameState": game_state,
                        "gameType": game_type,
                        "isCompleted": game_state in {"OFF", "FINAL", "OVER", "DONE"}
                        or (away_score is not None and home_score is not None),
                    }
                )
    df = pd.DataFrame(games).drop_duplicates(subset=["gameId"])
    if df.empty:
        return df
    return df.sort_values(["gameDate", "gameId"]).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def get_boxscore(game_id: int) -> Dict[str, Any]:
    """Fetch boxscore data for a single game."""
    return get_json(f"{BASE}/gamecenter/{game_id}/boxscore")


def extract_team_game(game_row: pd.Series, box: Dict[str, Any], team_abbrev: str) -> Dict[str, Any]:
    """Extract a single team's game stats from a boxscore."""
    flat = flatten_dict(box)
    away_score = first_non_null(flat, ["awayTeam.score"], game_row.get("awayScore"))
    home_score = first_non_null(flat, ["homeTeam.score"], game_row.get("homeScore"))
    away_shots = first_non_null(flat, ["awayTeam.sog", "awayTeam.shotsOnGoal"])
    home_shots = first_non_null(flat, ["homeTeam.sog", "homeTeam.shotsOnGoal"])

    is_home = game_row["homeTeam"] == team_abbrev
    team_score = home_score if is_home else away_score
    opp_score = away_score if is_home else home_score
    opponent = game_row["awayTeam"] if is_home else game_row["homeTeam"]

    ts = pd.to_numeric(team_score, errors="coerce")
    os_ = pd.to_numeric(opp_score, errors="coerce")

    if pd.isna(ts) or pd.isna(os_):
        result = "?"
    elif ts > os_:
        result = "W"
    elif ts < os_:
        result = "L"
    else:
        result = "OTL"

    return {
        "gameId": int(game_row["gameId"]),
        "gameDate": game_row["gameDate"],
        "venue": "Home" if is_home else "Away",
        "opponent": opponent,
        "teamScore": ts,
        "oppScore": os_,
        "result": result,
        "goalDiff": float((ts or 0) - (os_ or 0)),
        "teamShots": pd.to_numeric(home_shots if is_home else away_shots, errors="coerce"),
        "oppShots": pd.to_numeric(away_shots if is_home else home_shots, errors="coerce"),
    }


@st.cache_data(ttl=3600, show_spinner=True)
def build_team_games(team: str = DEFAULT_TEAM) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load schedule + boxscores for a single team; return (schedule, team_games)."""
    schedule = get_schedule(team)
    if schedule.empty:
        return schedule, pd.DataFrame()

    completed = schedule[schedule["isCompleted"]]
    rows: List[Dict[str, Any]] = []
    for _, g in completed.iterrows():
        try:
            box = get_boxscore(int(g["gameId"]))
            rows.append(extract_team_game(g, box, team))
        except Exception:
            continue

    if not rows:
        return schedule, pd.DataFrame()

    tg = pd.DataFrame(rows).sort_values(["gameDate", "gameId"]).reset_index(drop=True)
    tg["gameNumber"] = np.arange(1, len(tg) + 1)
    tg["pointsEarned"] = tg.apply(points_from_result, axis=1)
    tg["cumulativePoints"] = tg["pointsEarned"].cumsum()
    tg["rolling3GoalDiff"] = tg["goalDiff"].rolling(3, min_periods=1).mean()
    tg["rolling5GoalDiff"] = tg["goalDiff"].rolling(5, min_periods=1).mean()
    tg["rolling10GoalDiff"] = tg["goalDiff"].rolling(10, min_periods=1).mean()
    tg["rolling5GoalsFor"] = tg["teamScore"].rolling(5, min_periods=1).mean()
    tg["rolling5GoalsAgainst"] = tg["oppScore"].rolling(5, min_periods=1).mean()
    tg["rolling10GoalsFor"] = tg["teamScore"].rolling(10, min_periods=1).mean()
    tg["rolling10GoalsAgainst"] = tg["oppScore"].rolling(10, min_periods=1).mean()
    tg["rolling5Points"] = tg["pointsEarned"].rolling(5, min_periods=1).sum()
    tg["rolling10Points"] = tg["pointsEarned"].rolling(10, min_periods=1).sum()

    # Momentum composite
    rolling_gd = tg["rolling3GoalDiff"].fillna(0)
    diff5 = (tg["rolling5GoalsFor"] - tg["rolling5GoalsAgainst"]).fillna(0)
    shot_diff = (tg["teamShots"] - tg["oppShots"]).rolling(3, min_periods=1).mean().fillna(0)
    tg["momentumScore"] = (
        0.45 * zscore(rolling_gd).fillna(0)
        + 0.30 * zscore(diff5).fillna(0)
        + 0.25 * zscore(shot_diff).fillna(0)
    ) * 10 + 50

    return schedule, tg
