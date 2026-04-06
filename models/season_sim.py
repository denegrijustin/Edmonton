"""Full regular-season Monte Carlo simulator.

Runs N simulations of remaining regular-season games, applies NHL tiebreak
and wild-card logic, and returns comprehensive playoff-probability statistics.
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import GAMES_IN_SEASON


# ---------------------------------------------------------------------------
# Win-probability model
# ---------------------------------------------------------------------------

def compute_win_probability(
    metrics_a: Dict[str, Any],
    metrics_b: Dict[str, Any],
    home: str = "a",
) -> float:
    """Logistic win probability for team A hosting (or visiting) team B.

    Parameters
    ----------
    metrics_a, metrics_b : dict
        Team metrics with keys: ``points``, ``gamesPlayed``,
        ``goalDifferential``, ``momentum`` (0-100 scale).
    home : str
        ``"a"`` if team A is the home team, ``"b"`` otherwise.

    Returns
    -------
    float in [0.05, 0.95]
    """
    gp_a = max(float(metrics_a.get("gamesPlayed", 1)), 1)
    gp_b = max(float(metrics_b.get("gamesPlayed", 1)), 1)

    pts_pct_a = float(metrics_a.get("points", 0)) / max(gp_a * 2, 1)
    pts_pct_b = float(metrics_b.get("points", 0)) / max(gp_b * 2, 1)

    gd_pg_a = float(metrics_a.get("goalDifferential", 0)) / gp_a
    gd_pg_b = float(metrics_b.get("goalDifferential", 0)) / gp_b

    l10_a = float(metrics_a.get("momentum", 50)) / 100.0
    l10_b = float(metrics_b.get("momentum", 50)) / 100.0

    strength_a = 0.50 * pts_pct_a + 0.30 * (gd_pg_a / 10.0) + 0.20 * l10_a
    strength_b = 0.50 * pts_pct_b + 0.30 * (gd_pg_b / 10.0) + 0.20 * l10_b

    home_adv = 0.05
    if home == "a":
        strength_a += home_adv
    else:
        strength_b += home_adv

    diff = strength_a - strength_b
    win_prob = 1.0 / (1.0 + math.exp(-10.0 * diff))
    return max(0.05, min(0.95, win_prob))


# ---------------------------------------------------------------------------
# NHL tiebreak & seeding helpers
# ---------------------------------------------------------------------------

def _sort_by_tiebreaks(df: pd.DataFrame) -> pd.DataFrame:
    """Sort a team DataFrame by NHL tiebreak order (descending points)."""
    df = df.copy()
    df["_gp_neg"] = -df["gp"].astype(float)  # fewer GP = better
    return df.sort_values(
        ["points", "row", "rw", "_gp_neg", "goal_diff", "goals_for"],
        ascending=False,
    ).drop(columns=["_gp_neg"]).reset_index(drop=True)


def _assign_conference_seeds(conf_df: pd.DataFrame) -> pd.DataFrame:
    """Apply NHL wild-card seeding within a single conference DataFrame.

    Adds columns: ``div_rank``, ``conf_seed`` (1-8 for playoff teams, 0 otherwise),
    ``playoff_qualifier``, ``is_wildcard``.
    """
    conf_df = conf_df.copy()
    divisions = conf_df["division"].dropna().unique().tolist()

    if len(divisions) != 2:
        # Fallback: straight points ranking
        conf_df = _sort_by_tiebreaks(conf_df)
        conf_df["div_rank"] = 0
        conf_df["conf_seed"] = [i + 1 for i in range(len(conf_df))]
        conf_df["playoff_qualifier"] = conf_df["conf_seed"] <= 8
        conf_df["is_wildcard"] = False
        return conf_df

    div_a_name, div_b_name = divisions[0], divisions[1]
    div_a = _sort_by_tiebreaks(conf_df[conf_df["division"] == div_a_name].copy())
    div_b = _sort_by_tiebreaks(conf_df[conf_df["division"] == div_b_name].copy())

    div_a["div_rank"] = div_a.index + 1
    div_b["div_rank"] = div_b.index + 1

    top3_a = div_a[div_a["div_rank"] <= 3].copy()
    top3_b = div_b[div_b["div_rank"] <= 3].copy()
    top3_a["is_wildcard"] = False
    top3_b["is_wildcard"] = False

    # Wild card pool: 4th+ from each division
    wc_pool = pd.concat(
        [div_a[div_a["div_rank"] > 3], div_b[div_b["div_rank"] > 3]]
    )
    wc_pool = _sort_by_tiebreaks(wc_pool).reset_index(drop=True)
    wc_top2 = wc_pool.head(2).copy()
    wc_top2["is_wildcard"] = True
    wc_top2["div_rank"] = 0
    non_playoff = wc_pool.iloc[2:].copy()
    non_playoff["is_wildcard"] = False
    non_playoff["conf_seed"] = 0

    # Determine which division winner has more points for seed 1
    winner_a_pts = float(top3_a[top3_a["div_rank"] == 1]["points"].values[0]) if len(top3_a) else 0
    winner_b_pts = float(top3_b[top3_b["div_rank"] == 1]["points"].values[0]) if len(top3_b) else 0

    # Convention: stronger div winner → seeds 1, 3, 5; weaker → seeds 2, 4, 6
    if winner_a_pts >= winner_b_pts:
        strong_div, weak_div = top3_a, top3_b
    else:
        strong_div, weak_div = top3_b, top3_a

    seed_map: Dict[str, int] = {}
    for _, row in strong_div.iterrows():
        seed_map[row["teamAbbrev"]] = row["div_rank"] * 2 - 1  # 1, 3, 5
    for _, row in weak_div.iterrows():
        seed_map[row["teamAbbrev"]] = row["div_rank"] * 2  # 2, 4, 6
    for i, (_, row) in enumerate(wc_top2.iterrows()):
        seed_map[row["teamAbbrev"]] = 7 + i  # 7, 8

    all_playoff = pd.concat([top3_a, top3_b, wc_top2])
    all_playoff["conf_seed"] = all_playoff["teamAbbrev"].map(seed_map).fillna(0).astype(int)
    non_playoff["conf_seed"] = 0

    result = pd.concat([all_playoff, non_playoff]).reset_index(drop=True)
    result["playoff_qualifier"] = result["conf_seed"].between(1, 8)
    return result


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def get_all_remaining_games(standings_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Fetch remaining regular-season games for all teams in standings.

    Returns a deduplicated list of game dicts:
    ``[{"gameId": int, "homeTeam": str, "awayTeam": str}, ...]``
    """
    from providers.schedule_provider import get_schedule  # noqa: PLC0415

    if standings_df.empty:
        return []

    teams = standings_df["teamAbbrev"].dropna().unique().tolist()
    seen_ids: set = set()
    remaining: List[Dict[str, Any]] = []

    for team in teams:
        try:
            sched = get_schedule(team)
            if sched is None or sched.empty:
                continue
            # Filter to incomplete regular-season games
            mask_type = True
            if "gameType" in sched.columns:
                mask_type = pd.to_numeric(sched["gameType"], errors="coerce") == 2
            mask_inc = True
            if "isCompleted" in sched.columns:
                mask_inc = ~sched["isCompleted"]
            incomplete = sched[mask_type & mask_inc]
            for _, g in incomplete.iterrows():
                gid = g.get("gameId")
                if gid and gid not in seen_ids:
                    seen_ids.add(gid)
                    remaining.append(
                        {
                            "gameId": int(gid),
                            "homeTeam": str(g.get("homeTeam") or ""),
                            "awayTeam": str(g.get("awayTeam") or ""),
                        }
                    )
        except Exception:
            continue

    return remaining


# ---------------------------------------------------------------------------
# Main simulator
# ---------------------------------------------------------------------------

def run_season_simulation(
    standings_df: pd.DataFrame,
    remaining_games: List[Dict[str, Any]],
    team_metrics_dict: Dict[str, Dict[str, Any]],
    n_sims: int = 1000,
) -> Dict[str, Any]:
    """Simulate the remaining regular season N times.

    Parameters
    ----------
    standings_df : pd.DataFrame
        Current standings with at least: teamAbbrev, conference, division,
        points, wins, gamesPlayed, goalDifferential, goalFor.
    remaining_games : list of dict
        Each game: ``{"gameId": int, "homeTeam": str, "awayTeam": str}``.
    team_metrics_dict : dict
        Keyed by team abbreviation; each value has momentum, etc.
    n_sims : int
        Number of simulation iterations (default 1,000).

    Returns
    -------
    dict with keys:
        playoff_odds, division_title_odds, wild_card_odds, seed_odds,
        projected_final_standings, likely_final_ranking, most_likely_finish
    """
    if standings_df.empty:
        return _empty_results()

    # Build baseline team state
    teams: List[str] = []
    baseline: Dict[str, Dict[str, Any]] = {}

    for _, row in standings_df.iterrows():
        abbrev = str(row.get("teamAbbrev") or "")
        if not abbrev:
            continue
        teams.append(abbrev)
        baseline[abbrev] = {
            "teamAbbrev": abbrev,
            "conference": str(row.get("conference") or ""),
            "division": str(row.get("division") or ""),
            "points": int(float(row.get("points") or 0)),
            "wins": int(float(row.get("wins") or 0)),
            "gp": int(float(row.get("gamesPlayed") or 0)),
            "goal_diff": float(row.get("goalDifferential") or 0),
            "goals_for": float(row.get("goalFor") or 0),
            # row = regulation + OT wins (approximated as total wins initially)
            "row": int(float(row.get("wins") or 0)),
            # rw = regulation wins only (approx 90% of wins)
            "rw": int(round(float(row.get("wins") or 0) * 0.90)),
        }

    if not teams:
        return _empty_results()

    # Filter remaining games to teams in standings
    valid_teams = set(teams)
    games = [
        g for g in remaining_games
        if g.get("homeTeam") in valid_teams and g.get("awayTeam") in valid_teams
    ]

    # Pre-compute win probabilities to speed up simulation
    prob_cache: Dict[Tuple[str, str], float] = {}
    for g in games:
        key = (g["homeTeam"], g["awayTeam"])
        if key not in prob_cache:
            ma = team_metrics_dict.get(g["homeTeam"], baseline.get(g["homeTeam"], {}))
            mb = team_metrics_dict.get(g["awayTeam"], baseline.get(g["awayTeam"], {}))
            prob_cache[key] = compute_win_probability(ma, mb, home="a")

    # Accumulate simulation results
    playoff_counts: Dict[str, int] = {t: 0 for t in teams}
    div_title_counts: Dict[str, int] = {t: 0 for t in teams}
    wild_card_counts: Dict[str, int] = {t: 0 for t in teams}
    seed_counts: Dict[str, Dict[int, int]] = {t: {s: 0 for s in range(1, 9)} for t in teams}
    pts_records: Dict[str, List[float]] = {t: [] for t in teams}
    conf_rank_records: Dict[str, List[int]] = {t: [] for t in teams}
    div_rank_records: Dict[str, List[int]] = {t: [] for t in teams}
    league_rank_records: Dict[str, List[int]] = {t: [] for t in teams}

    rng = random.Random()

    for _ in range(n_sims):
        # Clone baseline for this simulation run
        sim: Dict[str, Dict[str, Any]] = {
            t: {k: v for k, v in d.items()} for t, d in baseline.items()
        }

        for g in games:
            home = g["homeTeam"]
            away = g["awayTeam"]
            wp_home = prob_cache[(home, away)]
            home_wins = rng.random() < wp_home
            is_ot = rng.random() < 0.10  # 10% chance of OT

            if home_wins:
                sim[home]["points"] += 2
                sim[home]["wins"] += 1
                sim[home]["row"] += 1
                sim[home]["goal_diff"] += 1
                sim[away]["goal_diff"] -= 1
                if not is_ot:
                    sim[home]["rw"] += 1
                else:
                    sim[away]["points"] += 1  # OT loser point
            else:
                sim[away]["points"] += 2
                sim[away]["wins"] += 1
                sim[away]["row"] += 1
                sim[away]["goal_diff"] += 1
                sim[home]["goal_diff"] -= 1
                if not is_ot:
                    sim[away]["rw"] += 1
                else:
                    sim[home]["points"] += 1  # OT loser point

            sim[home]["gp"] += 1
            sim[away]["gp"] += 1

        # Build DataFrame for this simulation and assign seeds
        sim_df = pd.DataFrame(list(sim.values()))
        sim_df["points"] = sim_df["points"].astype(float)

        # Assign league rank by points
        sim_df = sim_df.sort_values("points", ascending=False).reset_index(drop=True)
        sim_df["league_rank"] = sim_df.index + 1

        # Process each conference
        for conf_name, conf_df in sim_df.groupby("conference"):
            conf_df = conf_df.copy()
            conf_seeded = _assign_conference_seeds(conf_df)

            for _, row in conf_seeded.iterrows():
                t = row["teamAbbrev"]
                if t not in teams:
                    continue
                seed = int(row.get("conf_seed", 0))
                div_rank = int(row.get("div_rank", 0))
                is_playoff = bool(row.get("playoff_qualifier", False))
                is_wc = bool(row.get("is_wildcard", False))
                is_div1 = (div_rank == 1)

                if is_playoff:
                    playoff_counts[t] += 1
                if is_div1:
                    div_title_counts[t] += 1
                if is_wc:
                    wild_card_counts[t] += 1
                if 1 <= seed <= 8:
                    seed_counts[t][seed] += 1
                conf_rank_records[t].append(seed if seed > 0 else 16)
                div_rank_records[t].append(div_rank if div_rank > 0 else 8)

        for _, row in sim_df.iterrows():
            t = row["teamAbbrev"]
            if t in teams:
                pts_records[t].append(float(row["points"]))
                league_rank_records[t].append(int(row["league_rank"]))

    # Build output dictionaries
    scale = 100.0 / n_sims

    playoff_odds = {t: round(playoff_counts[t] * scale, 1) for t in teams}
    division_title_odds = {t: round(div_title_counts[t] * scale, 1) for t in teams}
    wild_card_odds = {t: round(wild_card_counts[t] * scale, 1) for t in teams}
    seed_odds = {
        t: {s: round(seed_counts[t][s] * scale, 1) for s in range(1, 9)}
        for t in teams
    }

    # Projected final standings (median)
    proj_rows = []
    for t in teams:
        pts_arr = pts_records[t]
        if pts_arr:
            proj_rows.append(
                {
                    "teamAbbrev": t,
                    "proj_pts": round(float(np.median(pts_arr)), 1),
                    "proj_pts_p10": round(float(np.percentile(pts_arr, 10)), 1),
                    "proj_pts_p90": round(float(np.percentile(pts_arr, 90)), 1),
                    "proj_league_rank": round(float(np.median(league_rank_records[t])), 0),
                    "playoff_odds": playoff_odds[t],
                    "conference": baseline[t]["conference"],
                    "division": baseline[t]["division"],
                }
            )
    projected_final_standings = (
        pd.DataFrame(proj_rows).sort_values("proj_pts", ascending=False).reset_index(drop=True)
        if proj_rows
        else pd.DataFrame()
    )

    # Likely final ranking (median per team)
    likely_final_ranking: Dict[str, Dict[str, Any]] = {}
    most_likely_finish: Dict[str, Dict[str, Any]] = {}

    for t in teams:
        pts_arr = pts_records[t]
        cr_arr = conf_rank_records[t]
        dr_arr = div_rank_records[t]
        lr_arr = league_rank_records[t]

        med_pts = round(float(np.median(pts_arr)), 1) if pts_arr else 0.0
        med_cr = int(round(np.median(cr_arr))) if cr_arr else 0
        med_dr = int(round(np.median(dr_arr))) if dr_arr else 0
        med_lr = int(round(np.median(lr_arr))) if lr_arr else 0
        p10 = round(float(np.percentile(pts_arr, 10)), 1) if pts_arr else 0.0
        p90 = round(float(np.percentile(pts_arr, 90)), 1) if pts_arr else 0.0

        # Most likely seed: the seed with max count
        best_seed = max(range(1, 9), key=lambda s: seed_counts[t][s])
        proj_seed = best_seed if seed_counts[t][best_seed] > 0 else None

        likely_final_ranking[t] = {
            "league_rank": med_lr,
            "conf_rank": med_cr,
            "div_rank": med_dr,
            "playoff_seed": proj_seed,
            "proj_pts": med_pts,
            "proj_pts_p10": p10,
            "proj_pts_p90": p90,
        }
        most_likely_finish[t] = {
            "league_rank": med_lr,
            "conf_rank": med_cr,
            "div_rank": med_dr,
        }

    return {
        "playoff_odds": playoff_odds,
        "division_title_odds": division_title_odds,
        "wild_card_odds": wild_card_odds,
        "seed_odds": seed_odds,
        "projected_final_standings": projected_final_standings,
        "likely_final_ranking": likely_final_ranking,
        "most_likely_finish": most_likely_finish,
    }


def _empty_results() -> Dict[str, Any]:
    return {
        "playoff_odds": {},
        "division_title_odds": {},
        "wild_card_odds": {},
        "seed_odds": {},
        "projected_final_standings": pd.DataFrame(),
        "likely_final_ranking": {},
        "most_likely_finish": {},
    }
