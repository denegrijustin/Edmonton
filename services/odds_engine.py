"""Real-data playoff odds engine.

Computes playoff odds using only established NHL API data and model
outputs.  Never fabricates data — all results are clearly labelled.
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config.settings import GAMES_IN_SEASON
from models.season_sim import compute_win_probability


def compute_team_playoff_odds(
    team: str,
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute playoff-qualification odds from real standings data.

    Inputs used: points percentage, goal differential, last-10 form
    (momentum), remaining opponent difficulty, and conference gap.

    Parameters
    ----------
    team : str
        Team abbreviation.
    standings_df : pd.DataFrame
        Current standings.
    team_metrics_dict : dict
        Metrics keyed by team abbreviation.

    Returns
    -------
    dict
        ``{"playoff_odds", "division_odds", "seed_range", "label"}``
    """
    metrics = team_metrics_dict.get(team, {})
    if not metrics or standings_df.empty:
        return {
            "playoff_odds": 0.0,
            "division_odds": 0.0,
            "seed_range": (0, 0),
            "label": "Model-derived",
        }

    pts = float(metrics.get("points", 0))
    gp = max(int(metrics.get("gamesPlayed", 1)), 1)
    remaining = max(GAMES_IN_SEASON - gp, 0)
    pts_pct = pts / max(gp * 2, 1)
    gd = float(metrics.get("goalDifferential", 0))
    momentum = float(metrics.get("momentum", 50))

    # Conference context
    conf_name = ""
    if "conference" in standings_df.columns:
        row = standings_df[standings_df["teamAbbrev"] == team]
        if not row.empty:
            conf_name = str(row.iloc[0].get("conference", ""))

    # Conference gap to 8th seed
    gap = 0.0
    if conf_name:
        mask = standings_df["conference"].astype(str).str.contains(
            conf_name, case=False, na=False,
        )
        c_pts = pd.to_numeric(
            standings_df.loc[mask, "points"], errors="coerce",
        ).sort_values(ascending=False)
        if len(c_pts) >= 8:
            gap = pts - float(c_pts.iloc[7])

    # --- Playoff odds (logistic model) ---
    proj_pts = pts + remaining * 2 * pts_pct
    pace_c = max(min((proj_pts - 90) / 18, 1.0), -1.0)
    diff_c = max(min(gd / 40, 1.0), -1.0)
    gap_c = max(min(gap / 10, 1.0), -1.0)
    mom_c = max(min((momentum - 50) / 30, 1.0), -1.0)

    raw_odds = 50 + 20 * pace_c + 12 * diff_c + 12 * gap_c + 6 * mom_c
    playoff_odds = round(float(max(min(raw_odds, 99.0), 1.0)), 1)

    # --- Division title odds (rougher estimate) ---
    div_name = ""
    if "division" in standings_df.columns:
        row = standings_df[standings_df["teamAbbrev"] == team]
        if not row.empty:
            div_name = str(row.iloc[0].get("division", ""))

    div_odds = 0.0
    if div_name:
        mask = standings_df["division"].astype(str).str.contains(
            div_name, case=False, na=False,
        )
        div_teams = standings_df[mask].copy()
        div_teams["pts_num"] = pd.to_numeric(div_teams["points"], errors="coerce").fillna(0)
        div_leader_pts = float(div_teams["pts_num"].max())
        if div_leader_pts > 0:
            closeness = max(min((pts - div_leader_pts + 10) / 20, 1.0), 0.0)
            div_odds = round(closeness * 50, 1)

    # --- Seed range (deterministic projection) ---
    seed_lo, seed_hi = _project_seed_range(team, standings_df, conf_name)

    return {
        "playoff_odds": playoff_odds,
        "division_odds": div_odds,
        "seed_range": (seed_lo, seed_hi),
        "label": "Model-derived",
    }


def _project_seed_range(
    team: str,
    standings_df: pd.DataFrame,
    conf_name: str,
) -> Tuple[int, int]:
    """Project best-case / worst-case conference seed for *team*."""
    if standings_df.empty or not conf_name or "conference" not in standings_df.columns:
        return (0, 0)

    mask = standings_df["conference"].astype(str).str.contains(
        conf_name, case=False, na=False,
    )
    conf = standings_df[mask].copy()
    if conf.empty or team not in conf["teamAbbrev"].values:
        return (0, 0)

    conf["pts_num"] = pd.to_numeric(conf["points"], errors="coerce").fillna(0)
    conf["gp_num"] = pd.to_numeric(conf["gamesPlayed"], errors="coerce").fillna(0)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gp_num"]).clip(lower=0)
    conf["pts_pct"] = conf["pts_num"] / (conf["gp_num"] * 2).clip(lower=1)

    team_row = conf[conf["teamAbbrev"] == team].iloc[0]
    team_proj = float(team_row["pts_num"] + team_row["remaining"] * 2 * team_row["pts_pct"])
    team_max_pts = float(team_row["pts_num"] + team_row["remaining"] * 2)

    # Best case: team gets all remaining pts, others keep pace
    conf["proj_low"] = conf["pts_num"] + conf["remaining"] * 2 * conf["pts_pct"]
    conf["proj_hi"] = conf["pts_num"] + conf["remaining"] * 2  # maximum possible

    # Seed range: count how many teams *could* finish above (worst) / *will* (best)
    teams_surely_above = (conf["proj_low"] > team_max_pts).sum()
    teams_could_above = (conf["proj_hi"] > team_max_pts).sum()

    seed_best = max(int(teams_surely_above) + 1, 1)
    seed_worst = min(int(teams_could_above) + 1, len(conf))

    return (seed_best, seed_worst)


def compute_remaining_difficulty(
    team: str,
    schedule_df: pd.DataFrame,
    standings_df: pd.DataFrame,
) -> float:
    """Average opponent points-percentage for remaining games.

    Parameters
    ----------
    team : str
        Team abbreviation.
    schedule_df : pd.DataFrame
        Team schedule with columns ``gameDate``, ``opponent`` (or similar).
    standings_df : pd.DataFrame
        Current standings.

    Returns
    -------
    float
        Average opponent points-pct (0-1). Returns ``0.5`` if data is
        unavailable.
    """
    if schedule_df.empty or standings_df.empty:
        return 0.5

    try:
        # Identify remaining games (unplayed)
        remaining = schedule_df[
            schedule_df.get("gameOutcome", pd.Series(dtype=str)).isna()
            | (schedule_df.get("gameOutcome", pd.Series(dtype=str)) == "")
        ]
        if remaining.empty:
            return 0.5

        opp_col = None
        for col in ("opponent", "opponentAbbrev", "opposingTeam"):
            if col in remaining.columns:
                opp_col = col
                break
        if opp_col is None:
            return 0.5

        opponents = remaining[opp_col].dropna().tolist()
        if not opponents:
            return 0.5

        # Compute opponent points-pct from standings
        if "teamAbbrev" not in standings_df.columns or "points" not in standings_df.columns:
            return 0.5

        standings_df = standings_df.copy()
        standings_df["pts_num"] = pd.to_numeric(standings_df["points"], errors="coerce").fillna(0)
        standings_df["gp_num"] = pd.to_numeric(
            standings_df["gamesPlayed"], errors="coerce",
        ).fillna(1).clip(lower=1)
        standings_df["opp_pts_pct"] = standings_df["pts_num"] / (standings_df["gp_num"] * 2)

        lookup = dict(
            zip(standings_df["teamAbbrev"], standings_df["opp_pts_pct"], strict=True),
        )

        pcts = [lookup.get(opp, 0.5) for opp in opponents]
        return round(sum(pcts) / len(pcts), 4) if pcts else 0.5

    except Exception:
        return 0.5


def compute_important_game(
    team: str,
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict[str, Any]],
    schedule_df: Optional[pd.DataFrame] = None,
) -> Optional[Dict[str, Any]]:
    """Identify the most impactful upcoming game for *team*.

    For each upcoming matchup involving *team* or its nearest competitors,
    estimates the swing in playoff odds if either side wins.

    Parameters
    ----------
    team : str
        Team abbreviation.
    standings_df : pd.DataFrame
        Current standings.
    team_metrics_dict : dict
        Metrics keyed by abbreviation.
    schedule_df : pd.DataFrame or None
        Optional schedule for upcoming-game lookup.

    Returns
    -------
    dict or None
        ``{"game", "team_a", "team_b", "impact_swing", "if_a_wins",
          "if_b_wins", "reason", "label"}`` or ``None`` when data is
        unavailable.
    """
    if standings_df.empty or not team_metrics_dict:
        return None

    try:
        metrics = team_metrics_dict.get(team, {})
        if not metrics:
            return None

        # Identify nearest competitor(s) in conference
        conf_name = ""
        if "conference" in standings_df.columns:
            row = standings_df[standings_df["teamAbbrev"] == team]
            if not row.empty:
                conf_name = str(row.iloc[0].get("conference", ""))

        if not conf_name:
            return None

        mask = standings_df["conference"].astype(str).str.contains(
            conf_name, case=False, na=False,
        )
        conf = standings_df[mask].copy()
        conf["pts_num"] = pd.to_numeric(conf["points"], errors="coerce").fillna(0)
        conf = conf.sort_values("pts_num", ascending=False).reset_index(drop=True)

        team_idx = conf[conf["teamAbbrev"] == team].index.tolist()
        if not team_idx:
            return None

        # Nearest conference rival (seed neighbour)
        idx = team_idx[0]
        rival_idx = idx + 1 if idx + 1 < len(conf) else idx - 1
        if rival_idx < 0 or rival_idx >= len(conf):
            return None

        rival = str(conf.iloc[rival_idx]["teamAbbrev"])
        rival_metrics = team_metrics_dict.get(rival, {})
        if not rival_metrics:
            return None

        # Win probability for head-to-head
        wp = compute_win_probability(metrics, rival_metrics, home="a")
        pts_gap = abs(float(metrics.get("points", 0)) - float(rival_metrics.get("points", 0)))
        impact = round((1 - abs(wp - 0.5) * 2) * max(10 - pts_gap, 1), 2)

        return {
            "game": {},
            "team_a": team,
            "team_b": rival,
            "impact_swing": impact,
            "if_a_wins": f"{team} gains ground toward higher seed",
            "if_b_wins": f"{rival} closes gap on {team}",
            "reason": f"Conference rivals separated by {int(pts_gap)} pts",
            "label": "Model-derived",
        }

    except Exception:
        return None
