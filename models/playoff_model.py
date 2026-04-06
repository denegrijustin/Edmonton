"""Playoff probability and projection model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import TOTAL_GAMES
from utils.helpers import clamp


class PlayoffModel:
    """Compute playoff odds, projected seeds, and projected opponents."""

    def __init__(self, standings: pd.DataFrame) -> None:
        self.standings = standings.copy()
        self._ensure_numeric()

    def _ensure_numeric(self) -> None:
        for col in ["points", "gamesPlayed", "wins", "losses", "otLosses",
                     "goalDifferential", "regulationWins", "projectedPoints"]:
            if col in self.standings.columns:
                self.standings[col] = pd.to_numeric(self.standings[col], errors="coerce").fillna(0)

    def compute_playoff_odds(self) -> pd.DataFrame:
        """Add playoffOdds column to standings."""
        df = self.standings.copy()
        if df.empty:
            return df

        for conf in ["Eastern", "Western"]:
            conf_mask = df["conference"].astype(str).str.contains(conf, case=False, na=False)
            conf_teams = df[conf_mask].copy()
            if conf_teams.empty:
                continue

            # Cutoff = 8th place projected points
            proj_sorted = conf_teams.sort_values("projectedPoints", ascending=False)
            if len(proj_sorted) >= 8:
                cutoff = proj_sorted.iloc[7]["projectedPoints"]
            else:
                cutoff = proj_sorted["projectedPoints"].min()

            for idx in conf_teams.index:
                row = df.loc[idx]
                gp = max(int(row["gamesPlayed"]), 1)
                remaining = max(TOTAL_GAMES - gp, 0)
                proj_pts = float(row.get("projectedPoints", row["points"]))
                pts = int(row["points"])
                goal_diff = int(row.get("goalDifferential", 0))

                # Pace component
                pace_margin = proj_pts - cutoff
                pace_component = clamp(pace_margin / 15 * 50, -50, 50)

                # Goal differential signal
                diff_component = clamp(goal_diff / 40 * 15, -15, 15)

                # Games remaining uncertainty
                remaining_factor = remaining / TOTAL_GAMES
                uncertainty_adj = remaining_factor * 10  # more remaining = more regression to ~50

                # Current position bonus
                conf_rank = row.get("conferenceSequence")
                if pd.notna(conf_rank) and int(conf_rank) <= 8:
                    position_bonus = 8
                else:
                    position_bonus = -5

                odds = clamp(50 + pace_component + diff_component + position_bonus - uncertainty_adj, 1, 99)
                df.loc[idx, "playoffOdds"] = round(odds, 1)

        # Fill any teams without odds
        df["playoffOdds"] = df["playoffOdds"].fillna(50.0)
        return df

    def compute_seeds(self) -> pd.DataFrame:
        """Add projected seed columns."""
        df = self.standings.copy()
        if df.empty:
            return df

        for conf in ["Eastern", "Western"]:
            conf_mask = df["conference"].astype(str).str.contains(conf, case=False, na=False)
            conf_teams = df[conf_mask].sort_values(
                ["projectedPoints", "regulationWins", "wins"],
                ascending=[False, False, False],
            )
            for i, idx in enumerate(conf_teams.index):
                seed = i + 1
                df.loc[idx, "projectedSeed"] = seed
                if seed <= 8:
                    df.loc[idx, "projectedPlayoffStatus"] = "In"
                else:
                    df.loc[idx, "projectedPlayoffStatus"] = "Out"

        df["projectedSeed"] = pd.to_numeric(df["projectedSeed"], errors="coerce").fillna(16).astype(int)
        return df
