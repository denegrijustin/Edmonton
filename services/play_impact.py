"""Play impact engine for last-game top plays.

Ranks plays from the most recent completed game using API play-by-play
data only. Impact scores are model-derived from real event data.
All event existence, location, period, time, players, and score state
come directly from the API.
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from api.nhl_client import get_play_by_play
from config.settings import BASE


# Event types that are considered high-impact
HIGH_IMPACT_EVENTS = {"goal", "penalty", "shot", "blocked-shot", "missed-shot"}

# Base impact scores by event type
EVENT_BASE_IMPACT = {
    "goal": 8.0,
    "penalty": 3.0,
    "shot": 1.0,
    "blocked-shot": 1.5,
    "missed-shot": 0.5,
    "faceoff": 0.3,
    "hit": 0.8,
    "giveaway": -0.5,
    "takeaway": 1.0,
    "stoppage": 0.0,
}


def find_last_completed_game(
    schedule: pd.DataFrame,
    team: str,
) -> Optional[Dict[str, Any]]:
    """Find the most recent completed game from the schedule.

    Parameters
    ----------
    schedule : pd.DataFrame
        Team schedule with gameId, gameDate, isCompleted, etc.
    team : str
        Team abbreviation.

    Returns
    -------
    dict or None
        Game info dict or None if no completed game found.
    """
    if schedule.empty:
        return None

    completed = schedule[schedule["isCompleted"] == True].copy()  # noqa: E712
    if completed.empty:
        return None

    # Sort by date descending
    completed["_dt"] = pd.to_datetime(completed["gameDate"], errors="coerce")
    completed = completed.sort_values("_dt", ascending=False)

    row = completed.iloc[0]
    opponent = row["awayTeam"] if row["homeTeam"] == team else row["homeTeam"]

    return {
        "gameId": int(row["gameId"]),
        "gameDate": row["gameDate"],
        "homeTeam": row["homeTeam"],
        "awayTeam": row["awayTeam"],
        "homeScore": row.get("homeScore"),
        "awayScore": row.get("awayScore"),
        "opponent": opponent,
        "isHome": row["homeTeam"] == team,
    }


def get_top_plays(
    game_id: int,
    team: str,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Fetch and rank plays from a specific completed game.

    All play data comes from the NHL API play-by-play endpoint.
    Only the impact score is model-derived.

    Parameters
    ----------
    game_id : int
        API game ID for the completed game.
    team : str
        Team abbreviation to determine positive/negative impact.
    top_n : int
        Number of top plays to return.

    Returns
    -------
    dict with keys:
        plays: list of ranked play dicts
        has_coordinates: bool — whether coordinate data exists
        game_id: int — validated game ID
        model_label: str
    """
    pbp = get_play_by_play(game_id)
    if not pbp:
        return {
            "plays": [],
            "has_coordinates": False,
            "game_id": game_id,
            "model_label": "Play Impact Model based on API play-by-play data",
            "error": "Play-by-play data unavailable from API",
        }

    all_plays = pbp.get("plays", [])
    if not all_plays:
        return {
            "plays": [],
            "has_coordinates": False,
            "game_id": game_id,
            "model_label": "Play Impact Model based on API play-by-play data",
            "error": "No play events found in API response",
        }

    home_team = pbp.get("homeTeam", {}).get("abbrev", "")
    away_team = pbp.get("awayTeam", {}).get("abbrev", "")

    ranked_plays: List[Dict[str, Any]] = []
    has_coords = False

    for play in all_plays:
        if not isinstance(play, dict):
            continue

        event_type = play.get("typeDescKey", "").lower()
        period = play.get("periodDescriptor", {}).get("number", 0)
        time_in_period = play.get("timeInPeriod", "")
        time_remaining = play.get("timeRemaining", "")

        # Get coordinates
        details = play.get("details", {})
        x_coord = details.get("xCoord")
        y_coord = details.get("yCoord")
        if x_coord is not None and y_coord is not None:
            has_coords = True

        # Get score state
        home_score = details.get("homeScore", 0)
        away_score = details.get("awayScore", 0)

        # Get event owner team
        event_owner = details.get("eventOwnerTeamId")

        # Get players involved
        players = []
        for key in ["scoringPlayerId", "shootingPlayerId", "blockingPlayerId",
                     "hittingPlayerId", "hitteePlayerId", "committedByPlayerId",
                     "drawnByPlayerId", "playerId", "winningPlayerId",
                     "losingPlayerId"]:
            pid = details.get(key)
            if pid:
                players.append(str(pid))

        # Compute impact score
        base_impact = EVENT_BASE_IMPACT.get(event_type, 0.0)
        if base_impact == 0.0 and event_type not in EVENT_BASE_IMPACT:
            continue  # Skip unrecognized low-value events

        impact = _compute_play_impact(
            base_impact=base_impact,
            event_type=event_type,
            period=period,
            time_remaining=time_remaining,
            home_score=home_score,
            away_score=away_score,
            details=details,
        )

        # Determine positive/negative for the selected team
        is_positive = True
        if event_type == "goal":
            scoring_team_id = details.get("eventOwnerTeamId")
            home_id = pbp.get("homeTeam", {}).get("id")
            away_id = pbp.get("awayTeam", {}).get("id")
            if team == home_team:
                is_positive = scoring_team_id == home_id
            else:
                is_positive = scoring_team_id == away_id
        elif event_type == "penalty":
            # Penalty on our team is negative
            committed_team = details.get("eventOwnerTeamId")
            home_id = pbp.get("homeTeam", {}).get("id")
            if team == home_team:
                is_positive = committed_team != home_id
            else:
                is_positive = committed_team == home_id
        elif event_type in ("giveaway",):
            is_positive = False

        if not is_positive:
            impact = -abs(impact)

        # Validate this play belongs to the correct game
        play_entry = {
            "game_id": game_id,
            "event_type": event_type,
            "period": period,
            "time_in_period": time_in_period,
            "time_remaining": time_remaining,
            "x_coord": x_coord,
            "y_coord": y_coord,
            "home_score": home_score,
            "away_score": away_score,
            "impact_score": round(impact, 2),
            "is_positive": is_positive,
            "players": players,
            "description": play.get("typeDescKey", ""),
            "details": {
                k: v for k, v in details.items()
                if k in ("reason", "shotType", "descKey", "typeCode",
                         "duration", "situationCode")
            },
        }
        ranked_plays.append(play_entry)

    # Sort by absolute impact score
    ranked_plays.sort(key=lambda p: abs(p["impact_score"]), reverse=True)

    # Take top N
    top_plays = ranked_plays[:top_n]

    # Assign rank
    for i, p in enumerate(top_plays):
        p["rank"] = i + 1

    # Find special callouts
    _annotate_callouts(top_plays)

    return {
        "plays": top_plays,
        "has_coordinates": has_coords,
        "game_id": game_id,
        "model_label": "Play Impact Model based on API play-by-play data",
    }


def _compute_play_impact(
    base_impact: float,
    event_type: str,
    period: int,
    time_remaining: str,
    home_score: int,
    away_score: int,
    details: Dict[str, Any],
) -> float:
    """Compute impact score for a single play.

    Factors:
    - Base event importance
    - Score differential context (close games matter more)
    - Period (later periods matter more)
    - Time remaining (late-game plays matter more)
    - Special situations (PP/SH goals get bonus)
    """
    impact = base_impact

    # Period multiplier
    period_mult = {1: 1.0, 2: 1.1, 3: 1.3, 4: 1.5, 5: 1.5}
    impact *= period_mult.get(period, 1.0)

    # Score closeness bonus
    score_diff = abs(home_score - away_score)
    if score_diff <= 1:
        impact *= 1.5  # Close game
    elif score_diff == 0:
        impact *= 1.8  # Tied game

    # Late game bonus
    minutes_remaining = _parse_time_remaining(time_remaining)
    if period >= 3 and minutes_remaining is not None and minutes_remaining <= 5:
        impact *= 1.4

    # Goal-specific bonuses
    if event_type == "goal":
        # Go-ahead goal
        if home_score == away_score:
            impact *= 1.3
        # Tying goal
        if abs(home_score - away_score) == 1:
            impact *= 1.2
        # Power play / short handed
        situation = details.get("situationCode", "")
        if "PP" in str(situation).upper() or details.get("goalType") == "power-play":
            impact *= 1.1
        if "SH" in str(situation).upper() or details.get("goalType") == "short-handed":
            impact *= 1.3

    return impact


def _parse_time_remaining(time_str: str) -> Optional[float]:
    """Parse MM:SS to minutes remaining."""
    if not time_str:
        return None
    try:
        parts = str(time_str).split(":")
        return int(parts[0]) + int(parts[1]) / 60
    except (ValueError, IndexError):
        return None


def _annotate_callouts(plays: List[Dict[str, Any]]) -> None:
    """Add callout annotations for special plays."""
    if not plays:
        return

    # Turning point: highest absolute impact
    if plays:
        plays[0]["callout"] = "Turning Point"

    # Winning play: highest positive impact goal
    positive_goals = [p for p in plays if p["is_positive"] and p["event_type"] == "goal"]
    if positive_goals:
        positive_goals[0].setdefault("callout", "Winning Play")

    # Most damaging: lowest (most negative) impact
    negative_plays = [p for p in plays if not p["is_positive"]]
    if negative_plays:
        most_negative = min(negative_plays, key=lambda p: p["impact_score"])
        most_negative.setdefault("callout", "Most Damaging Negative Play")
