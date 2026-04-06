"""Player rating engine — position-specific, efficiency-based ratings."""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.helpers import zscore, clamp


def compute_player_ratings(player_games: pd.DataFrame) -> pd.DataFrame:
    """Add player rating columns based on position-specific models.

    Returns DataFrame with added columns:
    - gameGrade (0-100)
    - rollingGrade (5-game rolling)
    - consistencyScore
    - trendFlag (Heating Up / Stable / Cooling Off)
    - positionGroup (F / D / G)
    """
    if player_games.empty:
        return player_games

    df = player_games.copy()
    df = df.sort_values(["playerName", "gameDate", "gameId"]).reset_index(drop=True)
    df["gameNumberByPlayer"] = df.groupby("playerName").cumcount() + 1

    # Rolling stats
    df["rolling3Points"] = df.groupby("playerName")["points"].transform(lambda s: s.rolling(3, min_periods=1).mean())
    df["rolling5Points"] = df.groupby("playerName")["points"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    df["rolling5Toi"] = df.groupby("playerName")["toi_min"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    df["seasonAvgToi"] = df.groupby("playerName")["toi_min"].transform("mean")
    df["shootingPct"] = np.where(df["shots"] > 0, df["goals"] / df["shots"], 0)

    # Season averages for trend detection
    df["gamesPlayed"] = df.groupby("playerName")["gameId"].transform("count")
    df["seasonAvgPoints"] = df.groupby("playerName")["points"].transform("mean")
    df["recent5AvgPoints"] = df.groupby("playerName")["points"].transform(lambda s: s.rolling(5, min_periods=1).mean())

    # Faceoff percentage
    df["faceoffPct"] = np.where(
        df["faceoffTaken"] > 0,
        df["faceoffWins"] / df["faceoffTaken"],
        np.nan,
    )

    # Position group
    df["positionGroup"] = df["position"].map({"F": "F", "D": "D", "G": "G", "C": "F", "L": "F", "R": "F", "LW": "F", "RW": "F"}).fillna("F")

    # Forward grade
    fwd_mask = df["positionGroup"] == "F"
    fwd_raw = (
        0.22 * df["goals"]
        + 0.15 * df["assists"]
        + 0.08 * df["shots"]
        + 0.06 * df["takeaways"]
        + 0.04 * df["hits"]
        + 0.03 * df["blockedShots"]
        - 0.05 * df["giveaways"]
        + 0.035 * df["toi_min"].fillna(0)
        + 0.06 * df["plusMinus"]
        + 0.04 * df["faceoffPct"].fillna(0.5)
    )

    # Defenseman grade
    def_mask = df["positionGroup"] == "D"
    def_raw = (
        0.12 * df["goals"]
        + 0.10 * df["assists"]
        + 0.05 * df["shots"]
        + 0.12 * df["blockedShots"]
        + 0.06 * df["hits"]
        + 0.06 * df["takeaways"]
        - 0.06 * df["giveaways"]
        + 0.04 * df["toi_min"].fillna(0)
        + 0.08 * df["plusMinus"]
    )

    # Goalie grade
    goalie_mask = df["positionGroup"] == "G"
    save_pct = np.where(df["shotsAgainst"] > 0, df["saves"] / df["shotsAgainst"], 0)
    goalie_raw = (
        0.40 * save_pct * 100
        + 0.30 * np.where(df["goalsAgainst"] > 0, 1 / df["goalsAgainst"], 5)
        + 0.15 * df["saves"] * 0.1
        + 0.15 * df["toi_min"].fillna(0) * 0.05
    )

    # Combined grade
    grade_raw = pd.Series(np.zeros(len(df)), index=df.index)
    grade_raw[fwd_mask] = fwd_raw[fwd_mask]
    grade_raw[def_mask] = def_raw[def_mask]
    grade_raw[goalie_mask] = goalie_raw[goalie_mask]

    df["gameGrade"] = (50 + 12 * zscore(grade_raw)).clip(20, 99)
    df["rollingGrade"] = df.groupby("playerName")["gameGrade"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    df["rolling10Grade"] = df.groupby("playerName")["gameGrade"].transform(lambda s: s.rolling(10, min_periods=3).mean())
    df["consistencyScore"] = df.groupby("playerName")["gameGrade"].transform(
        lambda s: 100 - s.rolling(10, min_periods=3).std().fillna(0) * 4,
    ).clip(40, 100)

    # Trend flag
    df["trendFlag"] = np.select(
        [
            df["recent5AvgPoints"] >= 1.2 * df["seasonAvgPoints"],
            df["recent5AvgPoints"] <= 0.8 * df["seasonAvgPoints"],
        ],
        ["Heating Up", "Cooling Off"],
        default="Stable",
    )

    # TOI deviation flag
    df["toiDeviation"] = np.where(
        df["rolling5Toi"].notna() & df["seasonAvgToi"].notna(),
        (df["rolling5Toi"] - df["seasonAvgToi"]) / df["seasonAvgToi"].clip(lower=1),
        0,
    )
    df["toiFlag"] = np.where(
        df["toiDeviation"] > 0.15, "Above Baseline",
        np.where(df["toiDeviation"] < -0.15, "Below Baseline", "Normal"),
    )

    return df
