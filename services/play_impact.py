"""Play-by-play impact scoring for top plays.

Computes context-aware impact scores for scoring events in a game using
real play-by-play data from the NHL API.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from api.nhl_api import fetch_play_by_play


def get_last_completed_game(
    team: str,
    schedule_df: pd.DataFrame,
) -> Optional[Dict[str, Any]]:
    """Find the most recently completed game for *team*.

    Parameters
    ----------
    team : str
        Team abbreviation.
    schedule_df : pd.DataFrame
        Team schedule DataFrame with at least ``gameDate``, ``gameId``,
        and game-outcome columns.

    Returns
    -------
    dict or None
        ``{"gameId", "gameDate", "opponent", "score", "is_home"}`` or
        ``None`` if no completed game is found.
    """
    if schedule_df.empty:
        return None

    try:
        df = schedule_df.copy()

        # Detect outcome column
        outcome_col = None
        for col in ("gameOutcome", "outcome", "result"):
            if col in df.columns:
                outcome_col = col
                break

        if outcome_col is not None:
            completed = df[df[outcome_col].notna() & (df[outcome_col] != "")]
        else:
            # Fallback: if there's a score column with values it's completed
            score_col = None
            for col in ("score", "homeScore", "awayScore"):
                if col in df.columns:
                    score_col = col
                    break
            if score_col:
                completed = df[df[score_col].notna()]
            else:
                return None

        if completed.empty:
            return None

        # Sort by date descending
        if "gameDate" in completed.columns:
            completed = completed.sort_values("gameDate", ascending=False)

        latest = completed.iloc[0]

        game_id = int(latest.get("gameId") or latest.get("id") or 0)
        if game_id == 0:
            return None

        # Determine opponent and home/away
        opponent = ""
        is_home = False
        for col in ("opponentAbbrev", "opponent", "opposingTeam"):
            if col in latest.index and latest.get(col):
                opponent = str(latest[col])
                break

        if "homeTeam" in latest.index:
            is_home = str(latest.get("homeTeam", "")) == team
        elif "teamAbbrev" in latest.index:
            is_home = str(latest.get("teamAbbrev", "")) == team

        # Build score string
        score = ""
        if "homeScore" in latest.index and "awayScore" in latest.index:
            score = f"{latest.get('homeScore', 0)}-{latest.get('awayScore', 0)}"

        return {
            "gameId": game_id,
            "gameDate": str(latest.get("gameDate", "")),
            "opponent": opponent,
            "score": score,
            "is_home": is_home,
        }

    except Exception:
        return None


def compute_play_impacts(game_id: int, team: str) -> List[Dict[str, Any]]:
    """Compute context-aware impact scores for scoring events.

    Impact scoring heuristics:

    - **Tying goal** → high impact (base 8)
    - **Go-ahead goal** → high impact (base 7)
    - **Insurance goal (2+ lead)** → moderate (base 4)
    - **Other goals** → base 5
    - **3rd-period / OT goals** weighted higher (×1.5 / ×2.0)
    - Goals *for* the team are positive; goals *against* are negative.

    Parameters
    ----------
    game_id : int
        NHL game ID.
    team : str
        Team abbreviation.

    Returns
    -------
    list of dict
        Each entry: ``{"period", "time", "event_type", "player",
        "impact_score", "positive", "x", "y", "description", "label"}``.
        Returns empty list if play-by-play is unavailable.
    """
    try:
        pbp = fetch_play_by_play(game_id)
        if not pbp:
            return []

        plays = pbp.get("plays") or []
        if not plays:
            return []

        results: List[Dict[str, Any]] = []
        running_home = 0
        running_away = 0
        home_abbrev = _get_team_abbrev(pbp, "homeTeam")
        away_abbrev = _get_team_abbrev(pbp, "awayTeam")

        for play in plays:
            event_type = (
                play.get("typeDescKey")
                or play.get("typeCode")
                or play.get("type")
                or ""
            )
            if str(event_type).lower() not in ("goal", "509", "505"):
                continue

            period = int(play.get("periodDescriptor", {}).get("number", 0)
                         or play.get("period", 0))
            time_str = play.get("timeInPeriod", "") or play.get("time", "")

            # Determine scoring team
            details = play.get("details") or {}
            scoring_team = str(
                details.get("eventOwnerTeamId")
                or details.get("teamId")
                or "",
            )
            # Map team ID → abbreviation
            score_diff_before = running_home - running_away
            is_home_goal = _is_home_team_goal(pbp, scoring_team)
            if is_home_goal is None:
                # Try to match by abbreviation embedded in details
                scoring_abbrev = str(details.get("teamAbbrev") or "")
                positive = scoring_abbrev == team
            else:
                if is_home_goal:
                    running_home += 1
                    positive = home_abbrev == team
                else:
                    running_away += 1
                    positive = away_abbrev == team

            impact = _compute_goal_impact(score_diff_before, period, is_home_goal, home_abbrev == team)

            if not positive:
                impact = -abs(impact)

            # Player name
            player = ""
            scoring_player = details.get("scoringPlayerId") or details.get("playerId")
            if scoring_player:
                player = str(scoring_player)
            # Try to get a display name
            player_name = (
                details.get("scoringPlayerName")
                or details.get("firstName", {}).get("default", "")
            )
            if player_name:
                last = details.get("lastName", {}).get("default", "")
                player = f"{player_name} {last}".strip() if last else str(player_name)

            # Coordinates
            x = details.get("xCoord")
            y = details.get("yCoord")

            description = play.get("description") or details.get("description") or f"Goal in P{period}"

            results.append({
                "period": period,
                "time": str(time_str),
                "event_type": "goal",
                "player": player,
                "impact_score": round(impact, 2),
                "positive": positive,
                "x": float(x) if x is not None else None,
                "y": float(y) if y is not None else None,
                "description": str(description),
                "label": "Estimated",
            })

        return results

    except Exception:
        return []


def rank_top_plays(
    plays: List[Dict[str, Any]],
    n: int = 10,
) -> List[Dict[str, Any]]:
    """Sort plays by absolute impact and return top *n*.

    Parameters
    ----------
    plays : list of dict
        Output of :func:`compute_play_impacts`.
    n : int
        Number of top plays to return.
    """
    sorted_plays = sorted(plays, key=lambda p: abs(p.get("impact_score", 0)), reverse=True)
    return sorted_plays[:n]


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------

def _get_team_abbrev(pbp: Dict[str, Any], key: str) -> str:
    """Extract a team abbreviation from the play-by-play root."""
    team_obj = pbp.get(key) or {}
    return str(team_obj.get("abbrev") or team_obj.get("triCode") or "")


def _is_home_team_goal(pbp: Dict[str, Any], team_id_str: str) -> Optional[bool]:
    """Return ``True`` if the goal was by the home team, ``False`` if away."""
    if not team_id_str:
        return None
    home_id = str((pbp.get("homeTeam") or {}).get("id", ""))
    away_id = str((pbp.get("awayTeam") or {}).get("id", ""))
    if team_id_str == home_id:
        return True
    if team_id_str == away_id:
        return False
    return None


def _compute_goal_impact(
    score_diff_before: int,
    period: int,
    is_home_goal: Optional[bool],
    team_is_home: bool,
) -> float:
    """Compute raw impact for a goal based on game context."""
    # Base impact by context
    if score_diff_before == 0:
        base = 8.0  # tying → could be go-ahead
    elif abs(score_diff_before) == 1:
        base = 7.0  # go-ahead or tying
    elif abs(score_diff_before) >= 3:
        base = 3.0  # blowout goal
    else:
        base = 5.0  # standard

    # Period multiplier
    if period >= 5:  # multi-OT
        multiplier = 2.5
    elif period == 4:  # OT
        multiplier = 2.0
    elif period == 3:
        multiplier = 1.5
    else:
        multiplier = 1.0

    return base * multiplier
