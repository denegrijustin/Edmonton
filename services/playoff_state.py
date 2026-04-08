"""Playoff state detection from schedule and game metadata.

Determines whether playoffs have started using real schedule data,
without depending on the unreliable playoffs/carousel API endpoint.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from config.settings import GAMES_IN_SEASON, SEASON


class PlayoffState:
    """Immutable snapshot of the current playoff state."""

    __slots__ = (
        "playoffs_started",
        "playoff_games",
        "completed_playoff_games",
        "unresolved_series",
        "current_round",
    )

    def __init__(
        self,
        playoffs_started: bool = False,
        playoff_games: Optional[List[Dict[str, Any]]] = None,
        completed_playoff_games: Optional[List[Dict[str, Any]]] = None,
        unresolved_series: Optional[List[Dict[str, Any]]] = None,
        current_round: int = 0,
    ):
        object.__setattr__(self, "playoffs_started", playoffs_started)
        object.__setattr__(self, "playoff_games", playoff_games or [])
        object.__setattr__(self, "completed_playoff_games", completed_playoff_games or [])
        object.__setattr__(self, "unresolved_series", unresolved_series or [])
        object.__setattr__(self, "current_round", current_round)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("PlayoffState is immutable")


def detect_playoff_state(
    standings_df: pd.DataFrame,
    team_schedules: Optional[Dict[str, pd.DataFrame]] = None,
    season: str = SEASON,
) -> PlayoffState:
    """Detect whether playoffs have started from schedule metadata.

    Detection strategy:
    1. Check if any team schedule contains gameType == 3 (playoff games).
    2. If not, check if all teams have completed 82 regular-season games
       (indicating offseason or playoffs about to start).
    3. Gather all playoff games and group into series.

    Parameters
    ----------
    standings_df : pd.DataFrame
        Current standings.
    team_schedules : dict, optional
        Pre-loaded schedules keyed by team abbreviation. If None, will
        attempt to load a sample team's schedule.
    season : str
        Season identifier.

    Returns
    -------
    PlayoffState
    """
    playoff_games: List[Dict[str, Any]] = []
    completed_playoff_games: List[Dict[str, Any]] = []
    seen_ids: set = set()

    if team_schedules:
        for _team, sched in team_schedules.items():
            _collect_playoff_games(sched, playoff_games, completed_playoff_games, seen_ids)
    else:
        # Try loading a few team schedules to check for playoff games
        try:
            from providers.schedule_provider import get_schedule  # noqa: PLC0415

            teams_to_check = []
            if not standings_df.empty and "teamAbbrev" in standings_df.columns:
                teams_to_check = standings_df["teamAbbrev"].dropna().unique().tolist()[:4]

            for team in teams_to_check:
                try:
                    sched = get_schedule(team, season)
                    if sched is not None and not sched.empty:
                        _collect_playoff_games(
                            sched, playoff_games, completed_playoff_games, seen_ids
                        )
                except Exception:
                    continue
        except Exception:
            pass

    playoffs_started = len(playoff_games) > 0

    if not playoffs_started:
        return PlayoffState(playoffs_started=False)

    # Determine current round from playoff games
    current_round = 0
    for g in playoff_games:
        r = g.get("round", 0)
        if r > current_round:
            current_round = r

    return PlayoffState(
        playoffs_started=True,
        playoff_games=playoff_games,
        completed_playoff_games=completed_playoff_games,
        current_round=current_round,
    )


def _collect_playoff_games(
    sched: pd.DataFrame,
    playoff_games: List[Dict[str, Any]],
    completed_playoff_games: List[Dict[str, Any]],
    seen_ids: set,
) -> None:
    """Extract playoff games from a schedule DataFrame."""
    if sched.empty or "gameType" not in sched.columns:
        return

    # gameType == 3 indicates playoff games in the NHL API
    mask = pd.to_numeric(sched["gameType"], errors="coerce") == 3
    playoff_rows = sched[mask]

    for _, row in playoff_rows.iterrows():
        gid = row.get("gameId")
        if gid is None or gid in seen_ids:
            continue
        seen_ids.add(gid)

        game_data = {
            "gameId": int(gid),
            "gameDate": row.get("gameDate"),
            "homeTeam": row.get("homeTeam"),
            "awayTeam": row.get("awayTeam"),
            "homeScore": row.get("homeScore"),
            "awayScore": row.get("awayScore"),
            "gameState": row.get("gameState"),
            "isCompleted": row.get("isCompleted", False),
            "round": _infer_round_from_game(row),
        }
        playoff_games.append(game_data)
        if game_data["isCompleted"]:
            completed_playoff_games.append(game_data)


def _infer_round_from_game(row: pd.Series) -> int:
    """Infer playoff round from game metadata if available.

    Many NHL schedule entries don't expose the round directly, so this
    returns 1 as a safe default when the information is absent.
    """
    # Some schedule formats include a seriesNumber or round hint
    for key in ["round", "seriesRound", "playoffRound"]:
        val = row.get(key)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return 1
