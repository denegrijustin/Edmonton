"""Scoped live-refresh utilities.

Provides helpers to detect live games and determine appropriate refresh
intervals for the UI layer.
"""

from typing import Any, Dict, Optional

from api.nhl_api import fetch_scoreboard


def get_live_game_state(team: str) -> Optional[Dict[str, Any]]:
    """Check if *team* has a game currently in progress.

    Parameters
    ----------
    team : str
        Team abbreviation (e.g. ``"EDM"``).

    Returns
    -------
    dict or None
        ``{"game_id", "score", "period", "clock", "status", "opponent",
        "is_home", "shots"}`` if a live game exists, otherwise ``None``.
    """
    try:
        data = fetch_scoreboard()
        if not data:
            return None

        games = data.get("games") or data.get("gamesByDate") or []
        # Handle nested structure where games are under date groups
        if isinstance(games, list) and games and isinstance(games[0], dict) and "games" in games[0]:
            flat: list = []
            for group in games:
                flat.extend(group.get("games", []))
            games = flat

        for game in games:
            if not isinstance(game, dict):
                continue

            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}
            home_abbrev = home.get("abbrev") or home.get("triCode") or ""
            away_abbrev = away.get("abbrev") or away.get("triCode") or ""

            if team not in (home_abbrev, away_abbrev):
                continue

            is_home = team == home_abbrev
            opponent = away_abbrev if is_home else home_abbrev
            home_score = int(home.get("score", 0))
            away_score = int(away.get("score", 0))
            score = f"{home_score}-{away_score}"

            # Period / clock info
            period_desc = game.get("periodDescriptor") or {}
            period = int(period_desc.get("number", 0) or game.get("period", 0))
            clock_obj = game.get("clock") or {}
            clock = str(clock_obj.get("timeRemaining", "") or clock_obj.get("currentTime", ""))

            # Game status
            game_state = str(
                game.get("gameState")
                or game.get("gameScheduleState")
                or "",
            ).upper()
            status = _normalise_status(game_state, game)

            # Shots
            shots = {
                "home": int(home.get("sog", 0)),
                "away": int(away.get("sog", 0)),
            }

            return {
                "game_id": int(game.get("id", 0)),
                "score": score,
                "period": period,
                "clock": clock,
                "status": status,
                "opponent": opponent,
                "is_home": is_home,
                "shots": shots,
            }

        return None

    except Exception:
        return None


def should_auto_refresh(game_state: Optional[Dict[str, Any]]) -> bool:
    """Return ``True`` if the UI should auto-refresh.

    Auto-refresh is enabled when a game is actively in progress (not
    ``"Final"`` and not ``"Scheduled"``).

    Parameters
    ----------
    game_state : dict or None
        Output of :func:`get_live_game_state`.
    """
    if game_state is None:
        return False
    status = game_state.get("status", "")
    return status not in ("Final", "Scheduled", "")


def get_refresh_interval(game_state: Optional[Dict[str, Any]]) -> int:
    """Determine the appropriate auto-refresh interval in seconds.

    Intervals
    ---------
    - No game: ``0`` (disabled)
    - Normal play: ``30``
    - Intermission: ``60``
    - Late 3rd / OT with close score: ``15``
    - Final: ``0``

    Parameters
    ----------
    game_state : dict or None
        Output of :func:`get_live_game_state`.

    Returns
    -------
    int
        Refresh interval in seconds.
    """
    if game_state is None:
        return 0

    status = game_state.get("status", "")
    if status in ("Final", "Scheduled", ""):
        return 0

    if status == "Intermission":
        return 60

    period = game_state.get("period", 0)
    score = game_state.get("score", "0-0")

    # Parse score to check if game is close
    try:
        parts = score.split("-")
        diff = abs(int(parts[0]) - int(parts[1]))
    except (ValueError, IndexError):
        diff = 99

    # Late 3rd or OT with close score
    if (period >= 3 and diff <= 1) or period >= 4:
        return 15

    return 30


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------

def _normalise_status(game_state: str, game: Dict[str, Any]) -> str:
    """Convert raw game state codes to a human-friendly status."""
    state_map = {
        "FINAL": "Final",
        "OFF": "Final",
        "LIVE": "Live",
        "CRIT": "Live",
        "FUT": "Scheduled",
        "PRE": "Scheduled",
    }

    for key, label in state_map.items():
        if key in game_state:
            return label

    # Check for intermission
    clock = game.get("clock") or {}
    if clock.get("inIntermission"):
        return "Intermission"

    if game_state:
        return "Live"

    return ""
