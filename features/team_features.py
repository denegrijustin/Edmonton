"""Team-level feature engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import TOTAL_GAMES


def compute_team_features(standings: pd.DataFrame) -> pd.DataFrame:
    """Enrich standings with projected final record, projected points, and rankings."""
    if standings.empty:
        return standings

    df = standings.copy()
    for col in ["points", "wins", "losses", "otLosses", "gamesPlayed", "goalDifferential",
                 "goalsFor", "goalsAgainst", "regulationWins"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["pointPctg"] = pd.to_numeric(df["pointPctg"], errors="coerce").fillna(0.0)

    # Remaining games
    df["remainingGames"] = (TOTAL_GAMES - df["gamesPlayed"]).clip(lower=0)

    # Points pace
    df["pointsPace"] = np.where(
        df["gamesPlayed"] > 0,
        df["points"] / df["gamesPlayed"] * TOTAL_GAMES,
        0,
    )

    # Goal differential per game
    df["goalDiffPerGame"] = np.where(
        df["gamesPlayed"] > 0,
        df["goalDifferential"] / df["gamesPlayed"],
        0,
    )

    # Projected final record (blended: pace + regression)
    df["winPct"] = np.where(df["gamesPlayed"] > 0, df["wins"] / df["gamesPlayed"], 0)
    df["lossPct"] = np.where(df["gamesPlayed"] > 0, df["losses"] / df["gamesPlayed"], 0)
    df["otlPct"] = np.where(df["gamesPlayed"] > 0, df["otLosses"] / df["gamesPlayed"], 0)

    # Blend current rate with slight regression to mean (0.5 win pct)
    regression_weight = np.where(df["gamesPlayed"] > 40, 0.05, 0.10)
    adj_win_pct = df["winPct"] * (1 - regression_weight) + 0.5 * regression_weight

    df["projectedWins"] = (df["wins"] + df["remainingGames"] * adj_win_pct).round().astype(int)
    df["projectedLosses"] = (df["losses"] + df["remainingGames"] * df["lossPct"]).round().astype(int)
    df["projectedOTL"] = (df["otLosses"] + df["remainingGames"] * df["otlPct"]).round().astype(int)

    # Ensure projected totals don't exceed 82
    total = df["projectedWins"] + df["projectedLosses"] + df["projectedOTL"]
    excess = (total - TOTAL_GAMES).clip(lower=0)
    df["projectedLosses"] = (df["projectedLosses"] - excess).clip(lower=df["losses"])

    df["projectedPoints"] = (df["projectedWins"] * 2 + df["projectedOTL"]).astype(int)
    df["projectedRecord"] = df.apply(
        lambda r: f"{r['projectedWins']}-{r['projectedLosses']}-{r['projectedOTL']}", axis=1,
    )

    # Home / Away records
    df["homeRecord"] = df.apply(lambda r: f"{r.get('homeWins', 0)}-{r.get('homeLosses', 0)}-{r.get('homeOtLosses', 0)}", axis=1)
    df["awayRecord"] = df.apply(lambda r: f"{r.get('roadWins', 0)}-{r.get('roadLosses', 0)}-{r.get('roadOtLosses', 0)}", axis=1)
    df["last10Record"] = df.apply(lambda r: f"{r.get('l10Wins', 0)}-{r.get('l10Losses', 0)}-{r.get('l10OtLosses', 0)}", axis=1)

    # Division / conference ranks
    for col in ["conferenceSequence", "divisionSequence", "wildcardSequence"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Conference rank (projected)
    for conf in df["conference"].dropna().unique():
        mask = df["conference"] == conf
        df.loc[mask, "projectedConfRank"] = df.loc[mask, "projectedPoints"].rank(ascending=False, method="min").astype(int)

    # Division rank (projected)
    for div in df["division"].dropna().unique():
        mask = df["division"] == div
        df.loc[mask, "projectedDivRank"] = df.loc[mask, "projectedPoints"].rank(ascending=False, method="min").astype(int)

    return df
