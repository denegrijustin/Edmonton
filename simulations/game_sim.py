"""Monte Carlo game simulation engine."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config.settings import MC_SIMULATIONS


def _team_strength(standings: pd.DataFrame, abbrev: str) -> dict[str, float]:
    """Extract team strength metrics from standings row."""
    row = standings[standings["teamAbbrev"] == abbrev]
    if row.empty:
        return {"gf_per_game": 3.0, "ga_per_game": 3.0, "pts_pct": 0.5,
                "home_pts_pct": 0.55, "away_pts_pct": 0.45}

    r = row.iloc[0]
    gp = max(int(r.get("gamesPlayed", 1)), 1)
    gf = float(r.get("goalsFor", 0)) or float(r.get("goalDifferential", 0)) / 2 + gp * 3
    ga = float(r.get("goalsAgainst", 0)) or gp * 3 - float(r.get("goalDifferential", 0)) / 2

    hw = int(r.get("homeWins", 0))
    hl = int(r.get("homeLosses", 0))
    ho = int(r.get("homeOtLosses", 0))
    home_gp = max(hw + hl + ho, 1)
    home_pts_pct = (hw * 2 + ho) / (home_gp * 2) if home_gp > 0 else 0.55

    rw = int(r.get("roadWins", 0))
    rl = int(r.get("roadLosses", 0))
    ro = int(r.get("roadOtLosses", 0))
    away_gp = max(rw + rl + ro, 1)
    away_pts_pct = (rw * 2 + ro) / (away_gp * 2) if away_gp > 0 else 0.45

    return {
        "gf_per_game": gf / gp,
        "ga_per_game": ga / gp,
        "pts_pct": float(r.get("pointPctg", 0.5)),
        "home_pts_pct": home_pts_pct,
        "away_pts_pct": away_pts_pct,
    }


def _momentum_adj(team_games: pd.DataFrame | None) -> float:
    """Return a small momentum adjustment factor."""
    if team_games is None or team_games.empty:
        return 0.0
    if "momentumScore" in team_games.columns:
        last_mom = team_games["momentumScore"].iloc[-1]
        return (last_mom - 50) / 200  # small adj: ±0.25 max
    return 0.0


def simulate_game(
    home_abbrev: str,
    away_abbrev: str,
    standings: pd.DataFrame,
    home_team_games: pd.DataFrame | None = None,
    away_team_games: pd.DataFrame | None = None,
    n_sims: int = MC_SIMULATIONS,
) -> dict[str, Any]:
    """Run Monte Carlo simulation for a single game.

    Returns dict with win probabilities, projected score, distributions.
    """
    home_str = _team_strength(standings, home_abbrev)
    away_str = _team_strength(standings, away_abbrev)

    # Home/away adjustments
    home_off = home_str["gf_per_game"] * 0.6 + home_str["home_pts_pct"] * 2
    home_def = home_str["ga_per_game"]
    away_off = away_str["gf_per_game"] * 0.4 + away_str["away_pts_pct"] * 2
    away_def = away_str["ga_per_game"]

    # Momentum adjustments
    home_mom = _momentum_adj(home_team_games)
    away_mom = _momentum_adj(away_team_games)

    # Expected goals
    home_xg = max(0.5, (home_off + away_def) / 2 * (1 + home_mom) + 0.15)  # slight home ice advantage
    away_xg = max(0.5, (away_off + home_def) / 2 * (1 + away_mom) - 0.10)

    rng = np.random.default_rng(42)

    home_goals = rng.poisson(home_xg, n_sims)
    away_goals = rng.poisson(away_xg, n_sims)

    # Regulation results
    home_reg_wins = np.sum(home_goals > away_goals)
    away_reg_wins = np.sum(away_goals > home_goals)
    ties = np.sum(home_goals == away_goals)

    # OT simulation for tied games
    ot_home_wins = int(ties * 0.52)  # slight home advantage in OT
    ot_away_wins = int(ties) - ot_home_wins

    total_home_wins = home_reg_wins + ot_home_wins
    total_away_wins = away_reg_wins + ot_away_wins

    home_win_pct = total_home_wins / n_sims * 100
    away_win_pct = total_away_wins / n_sims * 100
    ot_pct = ties / n_sims * 100

    # Score distribution
    home_goals_mean = np.mean(home_goals)
    away_goals_mean = np.mean(away_goals)

    # Most likely score
    from collections import Counter
    score_counts = Counter(zip(home_goals.tolist(), away_goals.tolist()))
    most_common_score = score_counts.most_common(1)[0][0]

    # Score range (10th-90th percentile)
    home_lo, home_hi = int(np.percentile(home_goals, 10)), int(np.percentile(home_goals, 90))
    away_lo, away_hi = int(np.percentile(away_goals, 10)), int(np.percentile(away_goals, 90))

    return {
        "homeTeam": home_abbrev,
        "awayTeam": away_abbrev,
        "homeWinPct": round(home_win_pct, 1),
        "awayWinPct": round(away_win_pct, 1),
        "homeRegWinPct": round(home_reg_wins / n_sims * 100, 1),
        "awayRegWinPct": round(away_reg_wins / n_sims * 100, 1),
        "otPct": round(ot_pct, 1),
        "projectedScore": f"{most_common_score[0]}-{most_common_score[1]}",
        "homeXG": round(home_xg, 2),
        "awayXG": round(away_xg, 2),
        "homeGoalsMean": round(home_goals_mean, 2),
        "awayGoalsMean": round(away_goals_mean, 2),
        "scoreRange": f"{home_lo}-{away_lo} to {home_hi}-{away_hi}",
        "homeGoalDist": np.bincount(home_goals, minlength=10)[:10].tolist(),
        "awayGoalDist": np.bincount(away_goals, minlength=10)[:10].tolist(),
        "nSims": n_sims,
        "confidence": "High" if n_sims >= 10000 else "Medium",
    }
