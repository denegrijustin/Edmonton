"""Monte Carlo season and playoff simulation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config.settings import MC_SIMULATIONS, TOTAL_GAMES


def simulate_season(
    standings: pd.DataFrame,
    n_sims: int = MC_SIMULATIONS,
) -> dict[str, dict[str, Any]]:
    """Simulate the remainder of the season for all teams.

    Returns dict keyed by teamAbbrev with simulation results.
    """
    if standings.empty:
        return {}

    rng = np.random.default_rng(42)
    results: dict[str, dict[str, Any]] = {}

    for _, row in standings.iterrows():
        abbrev = row["teamAbbrev"]
        gp = int(row.get("gamesPlayed", 0))
        current_pts = int(row.get("points", 0))
        remaining = max(TOTAL_GAMES - gp, 0)
        pts_pct = float(row.get("pointPctg", 0.5))

        if remaining == 0:
            results[abbrev] = {
                "finalPointsDist": [current_pts] * n_sims,
                "meanFinalPts": current_pts,
                "medianFinalPts": current_pts,
                "p10FinalPts": current_pts,
                "p90FinalPts": current_pts,
                "makePlayoffsPct": 0.0,  # filled later
            }
            continue

        # Simulate remaining games
        # Each game: win (2 pts) with prob win_pct, OTL (1 pt) with prob otl_pct, loss (0 pts)
        win_pct = pts_pct * 0.85  # approximate W probability from pts%
        otl_pct = pts_pct * 0.15  # approximate OTL probability
        loss_pct = 1 - win_pct - otl_pct

        sim_pts = np.zeros(n_sims, dtype=int)
        for _ in range(remaining):
            rolls = rng.random(n_sims)
            sim_pts += np.where(rolls < win_pct, 2, np.where(rolls < win_pct + otl_pct, 1, 0))

        final_pts = current_pts + sim_pts

        results[abbrev] = {
            "finalPointsDist": final_pts.tolist(),
            "meanFinalPts": round(float(np.mean(final_pts)), 1),
            "medianFinalPts": int(np.median(final_pts)),
            "p10FinalPts": int(np.percentile(final_pts, 10)),
            "p90FinalPts": int(np.percentile(final_pts, 90)),
            "makePlayoffsPct": 0.0,  # filled in the next step
        }

    # Determine playoff probability by comparing to 8th seed in each conference
    for conf in ["Eastern", "Western"]:
        conf_mask = standings["conference"].astype(str).str.contains(conf, case=False, na=False)
        conf_abbrevs = standings[conf_mask]["teamAbbrev"].tolist()
        if not conf_abbrevs:
            continue

        # For each simulation, rank teams in conference
        conf_results = {a: results[a]["finalPointsDist"] for a in conf_abbrevs if a in results}
        if not conf_results:
            continue

        n = min(len(v) for v in conf_results.values())
        make_counts = {a: 0 for a in conf_abbrevs}

        for sim_i in range(n):
            sim_standings = [(a, conf_results[a][sim_i]) for a in conf_abbrevs]
            sim_standings.sort(key=lambda x: x[1], reverse=True)
            for rank, (a, _) in enumerate(sim_standings):
                if rank < 8:
                    make_counts[a] += 1

        for a in conf_abbrevs:
            if a in results:
                results[a]["makePlayoffsPct"] = round(make_counts.get(a, 0) / n * 100, 1)

    return results
