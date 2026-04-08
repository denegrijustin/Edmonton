"""On-demand simulation wrapper.

Provides simulation functions that are triggered only by explicit user
action, never on startup. Results are cached in session state.
"""

from typing import Any, Dict, List, Optional

import streamlit as st


def run_matchup_sim(
    team_a: str,
    team_b: str,
    team_metrics_dict: Dict[str, Dict],
    home_team: str = "A",
    n_sims: int = 10000,
) -> Dict[str, Any]:
    """Run a single-game Monte Carlo simulation (on demand only)."""
    from models.monte_carlo import monte_carlo_sim  # noqa: PLC0415
    from providers.metrics_provider import compute_team_metrics  # noqa: PLC0415

    ma = team_metrics_dict.get(team_a, {})
    mb = team_metrics_dict.get(team_b, {})
    return monte_carlo_sim(ma, mb, home_team=home_team, n_sims=n_sims)


def run_series_sim(
    team_a: str,
    team_b: str,
    team_metrics_dict: Dict[str, Dict],
    wins_a: int = 0,
    wins_b: int = 0,
    n_sims: int = 250,
) -> Dict[str, Any]:
    """Run a best-of-7 series simulation (on demand only).

    If wins_a/wins_b > 0, starts from current series state.
    """
    from models.playoff_series_sim import simulate_series  # noqa: PLC0415

    return simulate_series(
        team_a, team_b,
        {team_a: team_metrics_dict.get(team_a, {}),
         team_b: team_metrics_dict.get(team_b, {})},
        wins_a=wins_a,
        wins_b=wins_b,
        n_sims=n_sims,
    )


def run_bracket_sim(
    series_list: List[Dict[str, Any]],
    team_metrics_dict: Dict[str, Dict],
    n_sims: int = 250,
) -> Dict[str, Dict[str, float]]:
    """Run a full bracket simulation (on demand only).

    Respects completed series — they are locked and not re-simulated.
    """
    from models.playoff_series_sim import simulate_full_bracket  # noqa: PLC0415

    # Lock completed series by setting wins to 4
    locked_series = []
    for s in series_list:
        entry = dict(s)
        if s.get("is_complete") and s.get("winner"):
            winner = s["winner"]
            if winner == s["topSeed"]:
                entry["topSeedWins"] = 4
                entry["bottomSeedWins"] = min(s.get("bottomSeedWins", 0), 3)
            else:
                entry["bottomSeedWins"] = 4
                entry["topSeedWins"] = min(s.get("topSeedWins", 0), 3)
        locked_series.append(entry)

    return simulate_full_bracket(locked_series, team_metrics_dict, n_sims=n_sims)


def run_season_sim_on_demand(
    standings_df,
    team_metrics_dict: Dict[str, Dict],
    n_sims: int = 250,
) -> Optional[Dict[str, Any]]:
    """Run season simulation on demand only (never at startup)."""
    from models.season_sim import (  # noqa: PLC0415
        get_all_remaining_games,
        run_season_simulation,
    )

    remaining = get_all_remaining_games(standings_df)
    if not remaining:
        return None
    return run_season_simulation(
        standings_df, remaining, team_metrics_dict, n_sims=n_sims
    )


SIM_DEPTHS = {
    "Quick (100)": 100,
    "Standard (250)": 250,
    "Deep (1000)": 1000,
}

DEFAULT_SIM_DEPTH = "Standard (250)"
