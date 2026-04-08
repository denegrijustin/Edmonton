"""NHL API client for play-by-play and roster data."""

from typing import Any, Dict, List

import streamlit as st

from config.settings import BASE, SEASON
from data.loaders import get_json


@st.cache_data(ttl=3600, show_spinner=False)
def get_play_by_play(game_id: int) -> Dict[str, Any]:
    """Fetch play-by-play data for a single game."""
    return get_json(f"{BASE}/gamecenter/{game_id}/play-by-play")


@st.cache_data(ttl=3600, show_spinner=False)
def get_roster(team: str, season: str = SEASON) -> Dict[str, Any]:
    """Fetch roster data for a team."""
    return get_json(f"{BASE}/roster/{team}/{season}")


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_stats(team: str, season: str = SEASON) -> List[Dict[str, Any]]:
    """Fetch player stats from roster and game log data.

    Returns a list of player dicts with available stats. If data is
    unavailable, returns an empty list.
    """
    roster = get_roster(team, season)
    if not roster:
        return []

    players: List[Dict[str, Any]] = []
    for position_group in ["forwards", "defensemen", "goalies"]:
        group = roster.get(position_group, [])
        if not isinstance(group, list):
            continue
        for p in group:
            if not isinstance(p, dict):
                continue
            player_id = p.get("id")
            first = p.get("firstName", {})
            last = p.get("lastName", {})
            first_name = first.get("default", "") if isinstance(first, dict) else str(first)
            last_name = last.get("default", "") if isinstance(last, dict) else str(last)
            players.append({
                "playerId": player_id,
                "name": f"{first_name} {last_name}".strip(),
                "position": p.get("positionCode", ""),
                "sweaterNumber": p.get("sweaterNumber"),
                "headshot": p.get("headshot", ""),
                "positionGroup": position_group,
            })
    return players
