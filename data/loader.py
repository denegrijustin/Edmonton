"""League-wide data loader — orchestrates all data loading and feature engineering."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config.settings import CACHE_TTL, DEFAULT_TEAM, SEASON
from features.momentum import compute_momentum
from features.player_ratings import compute_player_ratings
from features.team_features import compute_team_features
from models.playoff_model import PlayoffModel
from models.projections import project_opponents, project_seeds
from providers.data_health import DataHealth
from providers.nhl_api import NHLApiProvider


class LeagueDataLoader:
    """Load, enrich, and cache league-wide data for all 32 teams."""

    def __init__(self, focus_team: str = DEFAULT_TEAM) -> None:
        self.focus_team = focus_team
        self.provider = NHLApiProvider()
        self.health = DataHealth()

    @st.cache_data(ttl=CACHE_TTL, show_spinner="Loading league data…")
    def load_all(_self) -> dict[str, Any]:
        """Master data load: standings + team features + projections."""
        # 1. Standings (all 32 teams)
        try:
            standings = _self.provider.get_standings()
            _self.health.record("standings", True)
        except Exception as e:
            _self.health.record("standings", False, error=str(e))
            standings = pd.DataFrame()

        # 2. Team features & projections
        if not standings.empty:
            standings = compute_team_features(standings)
            playoff_model = PlayoffModel(standings)
            standings = playoff_model.compute_playoff_odds()
            standings = project_seeds(standings)
            standings = project_opponents(standings)
        else:
            _self.health.record("team_features", False, error="No standings data")

        # 3. Schedule for focus team
        try:
            schedule = _self.provider.get_schedule(_self.focus_team, SEASON)
            _self.health.record("schedule", True)
        except Exception as e:
            _self.health.record("schedule", False, error=str(e))
            schedule = pd.DataFrame()

        # 4. Roster for focus team
        try:
            roster = _self.provider.get_roster(_self.focus_team, SEASON)
            _self.health.record("roster", True)
        except Exception as e:
            _self.health.record("roster", False, error=str(e))
            roster = pd.DataFrame()

        # 5. Team game data from boxscores
        team_games = pd.DataFrame()
        player_games = pd.DataFrame()
        if not schedule.empty:
            team_rows: list[dict] = []
            player_parts: list[pd.DataFrame] = []
            completed = schedule[schedule["isCompleted"]]
            for _, g in completed.iterrows():
                try:
                    box = _self.provider.get_boxscore(int(g["gameId"]))
                    team_rows.append(_self.provider.extract_team_game(g, box, _self.focus_team))
                    pg = _self.provider.extract_player_games(g, box, roster, _self.focus_team)
                    if not pg.empty:
                        player_parts.append(pg)
                except Exception:
                    continue

            if team_rows:
                team_games = pd.DataFrame(team_rows).sort_values(["gameDate", "gameId"]).reset_index(drop=True)
                team_games["gameNumber"] = range(1, len(team_games) + 1)
                team_games = compute_momentum(team_games, standings, _self.focus_team)
                _self.health.record("team_games", True)
            else:
                _self.health.record("team_games", False, error="No completed games parsed")

            if player_parts:
                player_games = pd.concat(player_parts, ignore_index=True)
                player_games = compute_player_ratings(player_games)
                _self.health.record("player_games", True)
            else:
                _self.health.record("player_games", False, error="No player data parsed")

        # 6. Shot events
        shot_events = pd.DataFrame()
        if not schedule.empty:
            try:
                shot_events = _self.provider.extract_shot_events(schedule, _self.focus_team)
                _self.health.record("shot_events", True)
            except Exception as e:
                _self.health.record("shot_events", False, error=str(e))

        # 7. Season simulation
        season_sim = {}
        if not standings.empty:
            try:
                from simulations.season_sim import simulate_season
                season_sim = simulate_season(standings, n_sims=1000)  # Use 1000 for speed
                _self.health.record("season_sim", True)
            except Exception as e:
                _self.health.record("season_sim", False, error=str(e))

        return {
            "standings": standings,
            "schedule": schedule,
            "roster": roster,
            "team_games": team_games,
            "player_games": player_games,
            "shot_events": shot_events,
            "season_sim": season_sim,
            "health": _self.health,
        }
