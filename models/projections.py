"""Playoff projection and seed models."""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import GAMES_IN_SEASON, PLAYOFF_BRACKET_MAP
from providers.metrics_provider import compute_team_metrics
from utils.formatters import fmt_record


def _project_playoff_seed(
    team_abbrev: str,
    standings_df: pd.DataFrame,
    conf_name: str,
    team_proj_pts: float,
) -> Tuple[Optional[int], Optional[str]]:
    """Project conference seed (1-8) and first-round opponent for a team."""
    if standings_df.empty or "conference" not in standings_df.columns or not conf_name:
        return None, None
    mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
    conf = standings_df[mask].copy()
    if conf.empty:
        return None, None

    conf["points"] = pd.to_numeric(conf["points"], errors="coerce").fillna(0)
    conf["gamesPlayed"] = pd.to_numeric(conf["gamesPlayed"], errors="coerce").fillna(0)
    conf["pts_pct"] = conf["points"] / (conf["gamesPlayed"] * 2).clip(lower=1)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gamesPlayed"]).clip(lower=0)
    conf["proj_pts"] = conf["points"] + conf["remaining"] * 2 * conf["pts_pct"]
    conf.loc[conf["teamAbbrev"] == team_abbrev, "proj_pts"] = team_proj_pts

    conf = conf.sort_values("proj_pts", ascending=False).reset_index(drop=True)
    playoff_8 = conf.head(8)["teamAbbrev"].tolist()

    if team_abbrev not in playoff_8:
        return None, None

    seed = playoff_8.index(team_abbrev) + 1
    opp_seed = PLAYOFF_BRACKET_MAP.get(seed)
    opp = playoff_8[opp_seed - 1] if opp_seed and opp_seed <= len(playoff_8) else None
    return seed, opp


def compute_outlook(
    team_abbrev: str,
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
) -> Dict[str, Any]:
    """Compute full outlook for a team: projected record, odds, seed, etc."""
    metrics = team_metrics_dict.get(team_abbrev, compute_team_metrics(team_abbrev, standings_df))
    cur_pts = metrics.get("points", 0)
    gp = metrics.get("gamesPlayed", 0)
    gd = metrics.get("goalDifferential", 0)

    remaining = max(GAMES_IN_SEASON - gp, 0)
    pts_pct = cur_pts / max(gp * 2, 1)
    proj_pts = cur_pts + remaining * 2 * pts_pct

    # Conference context
    conf_name = ""
    conf_rank_val: Optional[int] = None
    if not standings_df.empty:
        tr = standings_df[standings_df["teamAbbrev"] == team_abbrev]
        if not tr.empty:
            conf_name = str(tr.iloc[0].get("conference") or "")
            cr = tr.iloc[0].get("conferenceSequence")
            try:
                conf_rank_val = int(cr) if cr is not None and not pd.isna(cr) else None
            except Exception:
                conf_rank_val = None

    # Cutoff (8th seed in conference)
    cutoff = gap = np.nan
    if conf_name and not standings_df.empty and "conference" in standings_df.columns:
        mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
        c_pts = pd.to_numeric(standings_df.loc[mask, "points"], errors="coerce").sort_values(ascending=False)
        if len(c_pts) >= 8:
            cutoff = float(c_pts.iloc[7])
            gap = float(cur_pts - cutoff)

    # Proxy odds
    pace_c = max(min((proj_pts - 90) / 18, 1.0), -1.0)
    diff_c = max(min(gd / 40, 1.0), -1.0)
    gap_c = 0.0 if pd.isna(gap) else max(min(gap / 10, 1.0), -1.0)
    playoff_odds = round(float(max(min(50 + 22 * pace_c + 14 * diff_c + 14 * gap_c, 99), 1)), 1)

    # Projected record
    proj_wins_add = int(round(remaining * pts_pct * 0.88))
    proj_otl_add = int(round(remaining * pts_pct * 0.12))
    proj_l_add = max(remaining - proj_wins_add - proj_otl_add, 0)
    proj_w = metrics.get("wins", 0) + proj_wins_add
    proj_l = metrics.get("losses", 0) + proj_l_add
    proj_otl = metrics.get("otl", 0) + proj_otl_add

    # Projected seed + opponent
    proj_seed, proj_opp = _project_playoff_seed(team_abbrev, standings_df, conf_name, proj_pts)

    return {
        "current_points": cur_pts,
        "games_played": gp,
        "remaining": remaining,
        "projected_points": round(proj_pts, 1),
        "projected_record": fmt_record(proj_w, proj_l, proj_otl),
        "playoff_odds": playoff_odds,
        "gap_to_cutoff": None if pd.isna(gap) else int(gap),
        "west_cutoff_points": None if pd.isna(cutoff) else int(cutoff),
        "conference_rank": conf_rank_val,
        "projected_seed": proj_seed,
        "projected_opponent": proj_opp,
        "conference": conf_name,
    }


def build_playoff_projection_table(standings_df: pd.DataFrame, conf_name: str) -> pd.DataFrame:
    """Build a conference-wide projected standings table."""
    if standings_df.empty or "conference" not in standings_df.columns or not conf_name:
        return pd.DataFrame()
    mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
    conf = standings_df[mask].copy()
    if conf.empty:
        return pd.DataFrame()

    for col in ["points", "gamesPlayed", "wins", "losses", "otLosses"]:
        conf[col] = pd.to_numeric(conf[col], errors="coerce").fillna(0)

    conf["pts_pct"] = conf["points"] / (conf["gamesPlayed"] * 2).clip(lower=1)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gamesPlayed"]).clip(lower=0)
    conf["proj_pts"] = (conf["points"] + conf["remaining"] * 2 * conf["pts_pct"]).round(1)
    conf["Record"] = conf.apply(
        lambda r: fmt_record(int(r["wins"]), int(r["losses"]), int(r["otLosses"])), axis=1
    )
    conf = conf.sort_values("proj_pts", ascending=False).reset_index(drop=True)
    conf["conf_rank"] = conf.index + 1
    conf["in_playoffs"] = conf["conf_rank"] <= 8
    return conf[["teamAbbrev", "teamName", "Record", "points", "proj_pts", "conf_rank", "in_playoffs", "division"]]


def get_seed_prob_distribution(
    team_abbrev: str, standings_df: pd.DataFrame
) -> Dict[int, float]:
    """Return a simple seed probability distribution for a team."""
    if standings_df.empty or "teamAbbrev" not in standings_df.columns:
        return {}
    tr = standings_df[standings_df["teamAbbrev"] == team_abbrev]
    if tr.empty:
        return {}
    conf_name = str(tr.iloc[0].get("conference") or "")
    if not conf_name or "conference" not in standings_df.columns:
        return {}
    mask = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
    conf = standings_df[mask].copy()
    conf["points"] = pd.to_numeric(conf["points"], errors="coerce").fillna(0)
    conf["gamesPlayed"] = pd.to_numeric(conf["gamesPlayed"], errors="coerce").fillna(0)
    conf["pts_pct"] = conf["points"] / (conf["gamesPlayed"] * 2).clip(lower=1)
    conf["remaining"] = (GAMES_IN_SEASON - conf["gamesPlayed"]).clip(lower=0)
    conf["proj_pts"] = conf["points"] + conf["remaining"] * 2 * conf["pts_pct"]
    conf = conf.sort_values("proj_pts", ascending=False).reset_index(drop=True)

    team_rank_arr = conf[conf["teamAbbrev"] == team_abbrev].index.tolist()
    if not team_rank_arr:
        return {}
    rank = team_rank_arr[0] + 1

    probs = {seed: max(0.0, 40.0 - abs(seed - rank) * 11.0) for seed in range(1, 9)}
    total = sum(probs.values())
    if total > 0:
        probs = {k: round(v / total * 100, 1) for k, v in probs.items()}
    return probs
