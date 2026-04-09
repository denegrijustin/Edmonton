"""On-demand Monte Carlo simulation wrapper.

Provides labelled wrappers around the lower-level simulation models so
that every result clearly indicates it is simulated output.
"""

from typing import Any, Dict, List

from models.monte_carlo import monte_carlo_sim
from models.playoff_series_sim import simulate_full_bracket, simulate_series

SIM_DEPTHS: Dict[str, int] = {"Quick": 100, "Standard": 250, "Deep": 1000}


def get_sim_depth(choice: str) -> int:
    """Map a human-readable depth label to an iteration count.

    Parameters
    ----------
    choice : str
        One of ``"Quick"``, ``"Standard"``, or ``"Deep"``.

    Returns
    -------
    int
    """
    return SIM_DEPTHS.get(choice, SIM_DEPTHS["Standard"])


def simulate_single_game(
    team_a: str,
    team_b: str,
    metrics_dict: Dict[str, Dict[str, Any]],
    home: str = "A",
    n_sims: int = 10_000,
) -> Dict[str, Any]:
    """Run a Monte Carlo game simulation with proper labels.

    Parameters
    ----------
    team_a, team_b : str
        Team abbreviations.
    metrics_dict : dict
        Metrics keyed by abbreviation.
    home : str
        ``"A"`` or ``"B"`` indicating the home team.
    n_sims : int
        Number of simulation iterations.

    Returns
    -------
    dict
        Monte Carlo result dict enriched with ``team_a``, ``team_b``, and
        ``label`` keys.
    """
    ma = metrics_dict.get(team_a, {})
    mb = metrics_dict.get(team_b, {})

    home_team = "A" if home.upper() == "A" else "B"
    result = monte_carlo_sim(ma, mb, home_team=home_team, n_sims=n_sims)

    result["team_a"] = team_a
    result["team_b"] = team_b
    result["label"] = "Simulated"
    return result


def simulate_playoff_series(
    team_a: str,
    team_b: str,
    metrics_dict: Dict[str, Dict[str, Any]],
    wins_a: int = 0,
    wins_b: int = 0,
    n_sims: int = 1_000,
) -> Dict[str, Any]:
    """Run a playoff-series simulation with proper labels.

    Parameters
    ----------
    team_a, team_b : str
        Team abbreviations (``team_a`` is the higher seed).
    metrics_dict : dict
        Metrics keyed by abbreviation.
    wins_a, wins_b : int
        Current series win counts.
    n_sims : int
        Number of simulation iterations.

    Returns
    -------
    dict
        Series simulation result enriched with ``team_a``, ``team_b``, and
        ``label`` keys.
    """
    result = simulate_series(
        team_a,
        team_b,
        metrics_dict,
        wins_a=wins_a,
        wins_b=wins_b,
        n_sims=n_sims,
    )
    result["team_a"] = team_a
    result["team_b"] = team_b
    result["label"] = "Simulated"
    return result


def simulate_full_playoffs(
    series_list: List[Dict[str, Any]],
    metrics_dict: Dict[str, Dict[str, Any]],
    n_sims: int = 1_000,
) -> Dict[str, Any]:
    """Simulate the full playoff bracket with proper labels.

    Parameters
    ----------
    series_list : list of dict
        Active series from the playoff provider.
    metrics_dict : dict
        Metrics keyed by abbreviation.
    n_sims : int
        Number of simulation iterations.

    Returns
    -------
    dict
        Full bracket results enriched with a ``label`` key.
    """
    result = simulate_full_bracket(series_list, metrics_dict, n_sims=n_sims)
    return {"teams": result, "label": "Simulated"}
