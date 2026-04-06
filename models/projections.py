"""Seed and opponent projection logic."""

from __future__ import annotations

import pandas as pd


def project_seeds(standings: pd.DataFrame) -> pd.DataFrame:
    """Project playoff seeds for each conference based on NHL rules.

    NHL seeding: top 3 in each division get seeds 1-3, remaining qualify as wild cards.
    """
    if standings.empty or "projectedPoints" not in standings.columns:
        return standings

    df = standings.copy()
    df["projectedSeed"] = None
    df["projectedOpponent"] = None
    df["wcRank"] = None

    for conf in ["Eastern", "Western"]:
        conf_mask = df["conference"].astype(str).str.contains(conf, case=False, na=False)
        conf_df = df[conf_mask].copy()
        if conf_df.empty:
            continue

        divisions = conf_df["division"].dropna().unique()
        seed_assignments: list[tuple[int, int]] = []  # (idx, seed)
        wild_card_pool: list[tuple[int, float]] = []

        for div in divisions:
            div_mask = conf_df["division"] == div
            div_teams = conf_df[div_mask].sort_values(
                ["projectedPoints", "regulationWins", "wins"],
                ascending=[False, False, False],
            )
            for rank, (idx, _) in enumerate(div_teams.iterrows()):
                if rank < 3:
                    seed_assignments.append((idx, rank + 1))
                else:
                    proj_pts = float(div_teams.loc[idx, "projectedPoints"])
                    wild_card_pool.append((idx, proj_pts))

        # Sort wild card pool
        wild_card_pool.sort(key=lambda x: x[1], reverse=True)

        # Assign seeds: division leaders get 1, 2, 3 (top div leader = 1st seed, etc.)
        # Then wild cards fill 4th and beyond
        div_leaders = [(idx, seed) for idx, seed in seed_assignments if seed == 1]
        div_leaders.sort(key=lambda x: float(df.loc[x[0], "projectedPoints"]), reverse=True)

        # In each conf: seeds 1,2 = div winners; 3 = 2nd in stronger div, etc.
        all_div_ranked: list[tuple[int, int, str]] = []
        for idx, seed in seed_assignments:
            div = str(df.loc[idx, "division"])
            all_div_ranked.append((idx, seed, div))

        # Sort by projected points for final seeding
        all_div_sorted = sorted(all_div_ranked, key=lambda x: float(df.loc[x[0], "projectedPoints"]), reverse=True)

        # Assign final conference seeds
        conf_seed = 1
        for idx, _, _ in all_div_sorted:
            df.loc[idx, "projectedSeed"] = conf_seed
            conf_seed += 1

        for i, (idx, pts) in enumerate(wild_card_pool):
            df.loc[idx, "projectedSeed"] = conf_seed
            df.loc[idx, "wcRank"] = i + 1
            conf_seed += 1

    df["projectedSeed"] = pd.to_numeric(df["projectedSeed"], errors="coerce").fillna(16).astype(int)
    return df


def project_opponents(standings: pd.DataFrame) -> pd.DataFrame:
    """Project first-round playoff opponents based on projected seeds.

    NHL bracket: 1v8/WC2, 2v7/WC1, 3v6, (within division matchups take priority).
    Simplified: 1v8, 2v7, 3v6, 4v5 within conference.
    """
    if standings.empty or "projectedSeed" not in standings.columns:
        return standings

    df = standings.copy()
    df["projectedOpponent"] = None
    df["projectedOpponent2"] = None

    matchups = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}

    for conf in ["Eastern", "Western"]:
        conf_mask = df["conference"].astype(str).str.contains(conf, case=False, na=False)
        conf_df = df[conf_mask].copy()

        for idx in conf_df.index:
            seed = int(df.loc[idx, "projectedSeed"])
            if seed in matchups:
                opp_seed = matchups[seed]
                opp_row = conf_df[conf_df["projectedSeed"] == opp_seed]
                if not opp_row.empty:
                    df.loc[idx, "projectedOpponent"] = opp_row.iloc[0]["teamAbbrev"]
                # Second most likely opponent (adjacent seed)
                alt_seed = opp_seed - 1 if opp_seed > 1 else opp_seed + 1
                alt_row = conf_df[conf_df["projectedSeed"] == alt_seed]
                if not alt_row.empty:
                    df.loc[idx, "projectedOpponent2"] = alt_row.iloc[0]["teamAbbrev"]

    return df
