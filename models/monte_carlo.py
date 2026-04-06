"""Monte Carlo game simulation model."""

from typing import Any, Dict

import numpy as np

from config.settings import (
    LEAGUE_AVG_GPG,
    SIM_HOME_ADV,
    SIM_LAST10_WEIGHT,
    SIM_SEASON_WEIGHT,
)


def monte_carlo_sim(
    team_a_metrics: Dict,
    team_b_metrics: Dict,
    home_team: str = "A",
    n_sims: int = 10000,
) -> Dict[str, Any]:
    """Run *n_sims* Poisson-based game simulations between two teams."""
    a_attack = SIM_SEASON_WEIGHT * team_a_metrics["gf_per_game"] + SIM_LAST10_WEIGHT * team_a_metrics["last10_gf_per_game"]
    a_defense = SIM_SEASON_WEIGHT * team_a_metrics["ga_per_game"] + SIM_LAST10_WEIGHT * team_a_metrics["last10_ga_per_game"]
    b_attack = SIM_SEASON_WEIGHT * team_b_metrics["gf_per_game"] + SIM_LAST10_WEIGHT * team_b_metrics["last10_gf_per_game"]
    b_defense = SIM_SEASON_WEIGHT * team_b_metrics["ga_per_game"] + SIM_LAST10_WEIGHT * team_b_metrics["last10_ga_per_game"]

    # Expected goals per game via interaction model
    a_lambda = (a_attack / LEAGUE_AVG_GPG) * b_defense
    b_lambda = (b_attack / LEAGUE_AVG_GPG) * a_defense

    # Apply home ice
    if home_team == "A":
        a_lambda = a_lambda + SIM_HOME_ADV
        b_lambda = max(b_lambda - SIM_HOME_ADV, 0.5)
    else:
        b_lambda = b_lambda + SIM_HOME_ADV
        a_lambda = max(a_lambda - SIM_HOME_ADV, 0.5)

    a_lambda = max(float(a_lambda), 0.5)
    b_lambda = max(float(b_lambda), 0.5)

    rng = np.random.default_rng()
    a_goals = rng.poisson(a_lambda, n_sims)
    b_goals = rng.poisson(b_lambda, n_sims)

    ties = a_goals == b_goals
    a_wins_reg = a_goals > b_goals
    b_wins_reg = b_goals > a_goals
    ot_a = ties & (rng.random(n_sims) > 0.5)
    ot_b = ties & ~ot_a

    return {
        "a_win_pct": (a_wins_reg.sum() + ot_a.sum()) / n_sims * 100,
        "b_win_pct": (b_wins_reg.sum() + ot_b.sum()) / n_sims * 100,
        "a_reg_win_pct": a_wins_reg.sum() / n_sims * 100,
        "b_reg_win_pct": b_wins_reg.sum() / n_sims * 100,
        "ot_pct": ties.sum() / n_sims * 100,
        "a_avg_goals": float(a_goals.mean()),
        "b_avg_goals": float(b_goals.mean()),
        "a_goals_arr": a_goals,
        "b_goals_arr": b_goals,
        "a_lambda": a_lambda,
        "b_lambda": b_lambda,
    }
