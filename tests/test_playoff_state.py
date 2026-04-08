"""Tests for services.playoff_state — playoff detection."""

import pandas as pd
import pytest

from services.playoff_state import PlayoffState, detect_playoff_state


class TestPlayoffState:
    """Test PlayoffState immutable snapshot."""

    def test_default_state(self):
        ps = PlayoffState()
        assert ps.playoffs_started is False
        assert ps.playoff_games == []
        assert ps.completed_playoff_games == []
        assert ps.current_round == 0

    def test_playoffs_started(self):
        ps = PlayoffState(playoffs_started=True, current_round=1)
        assert ps.playoffs_started is True
        assert ps.current_round == 1

    def test_immutable(self):
        ps = PlayoffState()
        with pytest.raises(AttributeError):
            ps.playoffs_started = True


class TestDetectPlayoffState:
    """Test detect_playoff_state function."""

    def test_empty_standings_no_playoffs(self):
        ps = detect_playoff_state(pd.DataFrame())
        assert ps.playoffs_started is False

    def test_no_playoff_games_in_schedule(self):
        standings = pd.DataFrame({
            "teamAbbrev": ["EDM", "CGY"],
            "gamesPlayed": [70, 70],
        })
        # Provide empty team_schedules
        schedules = {
            "EDM": pd.DataFrame({
                "gameId": [1, 2],
                "gameType": [2, 2],
                "homeTeam": ["EDM", "CGY"],
                "awayTeam": ["CGY", "EDM"],
                "homeScore": [3, 2],
                "awayScore": [2, 3],
                "isCompleted": [True, True],
                "gameDate": ["2026-01-01", "2026-01-03"],
                "gameState": ["OFF", "OFF"],
            }),
        }
        ps = detect_playoff_state(standings, team_schedules=schedules)
        assert ps.playoffs_started is False

    def test_playoff_games_detected(self):
        standings = pd.DataFrame({
            "teamAbbrev": ["EDM", "CGY"],
            "gamesPlayed": [82, 82],
        })
        schedules = {
            "EDM": pd.DataFrame({
                "gameId": [100, 101],
                "gameType": [3, 3],  # Playoff games
                "homeTeam": ["EDM", "CGY"],
                "awayTeam": ["CGY", "EDM"],
                "homeScore": [3, 2],
                "awayScore": [2, 3],
                "isCompleted": [True, True],
                "gameDate": ["2026-04-15", "2026-04-17"],
                "gameState": ["OFF", "OFF"],
            }),
        }
        ps = detect_playoff_state(standings, team_schedules=schedules)
        assert ps.playoffs_started is True
        assert len(ps.playoff_games) == 2
        assert len(ps.completed_playoff_games) == 2

    def test_mixed_game_types(self):
        schedules = {
            "EDM": pd.DataFrame({
                "gameId": [1, 2, 100],
                "gameType": [2, 2, 3],
                "homeTeam": ["EDM", "CGY", "EDM"],
                "awayTeam": ["CGY", "EDM", "CGY"],
                "homeScore": [3, 2, 4],
                "awayScore": [2, 3, 1],
                "isCompleted": [True, True, True],
                "gameDate": ["2026-01-01", "2026-01-03", "2026-04-15"],
                "gameState": ["OFF", "OFF", "OFF"],
            }),
        }
        ps = detect_playoff_state(pd.DataFrame({"teamAbbrev": ["EDM"]}), team_schedules=schedules)
        assert ps.playoffs_started is True
        assert len(ps.playoff_games) == 1  # Only the one playoff game

    def test_deduplicates_games(self):
        """Same game appearing in multiple team schedules."""
        game = {
            "gameId": [100],
            "gameType": [3],
            "homeTeam": ["EDM"],
            "awayTeam": ["CGY"],
            "homeScore": [3],
            "awayScore": [2],
            "isCompleted": [True],
            "gameDate": ["2026-04-15"],
            "gameState": ["OFF"],
        }
        schedules = {
            "EDM": pd.DataFrame(game),
            "CGY": pd.DataFrame(game),
        }
        ps = detect_playoff_state(pd.DataFrame({"teamAbbrev": ["EDM", "CGY"]}), team_schedules=schedules)
        assert len(ps.playoff_games) == 1
