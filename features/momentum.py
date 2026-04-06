"""Momentum rate computation — measurable, data-driven momentum scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.helpers import zscore, clamp


def compute_momentum(team_games: pd.DataFrame, standings: pd.DataFrame | None = None, team_abbrev: str = "") -> pd.DataFrame:
    """Add momentum columns to team_games DataFrame.

    Returns the DataFrame with added columns:
    - momentumScore: 0-100 composite
    - momentumDirection: Hot / Steady / Slipping / Cold
    - momentumSupported: whether underlying metrics support the momentum signal
    """
    if team_games.empty:
        return team_games

    df = team_games.copy()

    # Rolling metrics
    df["rolling3GoalDiff"] = df["goalDiff"].rolling(3, min_periods=1).mean()
    df["rolling5GoalDiff"] = df["goalDiff"].rolling(5, min_periods=1).mean()
    df["rolling10GoalDiff"] = df["goalDiff"].rolling(10, min_periods=1).mean()
    df["rolling3ShotDiff"] = df["shotDiff"].rolling(3, min_periods=1).mean()
    df["rolling5ShotDiff"] = df["shotDiff"].rolling(5, min_periods=1).mean()
    df["rolling3GoalsFor"] = df["teamScore"].rolling(3, min_periods=1).mean()
    df["rolling3GoalsAgainst"] = df["oppScore"].rolling(3, min_periods=1).mean()
    df["rolling5GoalsFor"] = df["teamScore"].rolling(5, min_periods=1).mean()
    df["rolling5GoalsAgainst"] = df["oppScore"].rolling(5, min_periods=1).mean()

    # Points earned
    df["pointsEarned"] = df["result"].map({"W": 2, "OTL": 1, "L": 0}).fillna(0).astype(int)
    df["cumulativePoints"] = df["pointsEarned"].cumsum()

    # Points percentage trends
    df["last5PtsPct"] = df["pointsEarned"].rolling(5, min_periods=1).mean() / 2
    df["last10PtsPct"] = df["pointsEarned"].rolling(10, min_periods=1).mean() / 2
    df["seasonPtsPct"] = df["cumulativePoints"] / (2 * np.arange(1, len(df) + 1))

    # Clutch index
    df["clutchIndex"] = np.where(
        (df["goalDiff"].abs() == 1) & (df["result"] == "W"), 1,
        np.where((df["goalDiff"].abs() == 1) & (df["result"] == "L"), -1, 0),
    )

    # Momentum composite
    components = {
        "last5_pts": 0.20 * zscore(df["last5PtsPct"]).fillna(0),
        "last10_pts": 0.10 * zscore(df["last10PtsPct"]).fillna(0),
        "goal_diff": 0.15 * zscore(df["rolling5GoalDiff"]).fillna(0),
        "shot_diff": 0.10 * zscore(df["rolling5ShotDiff"]).fillna(0),
        "gf_trend": 0.10 * zscore(df["rolling3GoalsFor"] - df["rolling3GoalsAgainst"]).fillna(0),
        "clutch": 0.10 * zscore(df["clutchIndex"].rolling(5, min_periods=1).mean()).fillna(0),
        "pts_pct_trend": 0.10 * zscore(df["seasonPtsPct"]).fillna(0),
        "consistency": 0.15 * zscore(df["goalDiff"].rolling(10, min_periods=3).std().fillna(0) * -1).fillna(0),
    }
    raw_momentum = sum(components.values())
    df["momentumScore"] = (raw_momentum * 10 + 50).clip(0, 100)

    # Direction classification
    df["momentumDirection"] = pd.cut(
        df["momentumScore"],
        bins=[-1, 30, 45, 55, 70, 101],
        labels=["Cold", "Slipping", "Steady", "Hot", "Hot"],
        ordered=False,
    ).astype(str)

    # Supported vs unsustainable: check if shot metrics support the results
    result_momentum = zscore(df["last5PtsPct"]).fillna(0)
    process_momentum = zscore(df["rolling5ShotDiff"]).fillna(0) + zscore(df["rolling5GoalDiff"]).fillna(0)
    df["momentumSupported"] = np.where(
        (result_momentum > 0.5) & (process_momentum < -0.5), "Unsustainable",
        np.where((result_momentum < -0.5) & (process_momentum > 0.5), "Unlucky", "Supported"),
    )

    return df
