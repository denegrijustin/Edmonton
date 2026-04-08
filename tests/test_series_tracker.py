"""Tests for services.series_tracker — series grouping and tracking."""

import pytest

from services.series_tracker import (
    build_series_from_games,
    get_active_series,
    get_completed_series,
)


class TestBuildSeriesFromGames:
    """Test build_series_from_games function."""

    def test_empty_input(self):
        result = build_series_from_games([])
        assert result == []

    def test_single_completed_game(self):
        games = [
            {
                "gameId": 1,
                "gameDate": "2026-04-15",
                "homeTeam": "EDM",
                "awayTeam": "CGY",
                "homeScore": 4,
                "awayScore": 2,
                "isCompleted": True,
                "round": 1,
            }
        ]
        result = build_series_from_games(games)
        assert len(result) == 1
        assert result[0]["topSeed"] == "EDM"
        assert result[0]["bottomSeed"] == "CGY"
        assert result[0]["topSeedWins"] == 1
        assert result[0]["bottomSeedWins"] == 0
        assert result[0]["is_complete"] is False

    def test_completed_series(self):
        games = []
        # EDM wins 4-1
        for i in range(5):
            is_edm_home = i % 2 == 0
            home = "EDM" if is_edm_home else "CGY"
            away = "CGY" if is_edm_home else "EDM"
            if i < 4:
                hs = 3 if is_edm_home else 1
                aws = 1 if is_edm_home else 3
            else:
                hs = 2
                aws = 4
            games.append({
                "gameId": 100 + i,
                "gameDate": f"2026-04-{15 + i}",
                "homeTeam": home,
                "awayTeam": away,
                "homeScore": hs,
                "awayScore": aws,
                "isCompleted": True,
                "round": 1,
            })

        result = build_series_from_games(games)
        assert len(result) == 1
        series = result[0]
        # EDM should have won 4 games (games 0,1,2,3) and CGY won game 4
        assert series["is_complete"] is True
        assert series["winner"] == "EDM"
        assert series["topSeedWins"] == 4

    def test_multiple_series(self):
        games = [
            {
                "gameId": 1,
                "gameDate": "2026-04-15",
                "homeTeam": "EDM",
                "awayTeam": "CGY",
                "homeScore": 3,
                "awayScore": 2,
                "isCompleted": True,
                "round": 1,
            },
            {
                "gameId": 2,
                "gameDate": "2026-04-15",
                "homeTeam": "VAN",
                "awayTeam": "LAK",
                "homeScore": 1,
                "awayScore": 4,
                "isCompleted": True,
                "round": 1,
            },
        ]
        result = build_series_from_games(games)
        assert len(result) == 2

    def test_next_game_tracking(self):
        games = [
            {
                "gameId": 1,
                "gameDate": "2026-04-15",
                "homeTeam": "EDM",
                "awayTeam": "CGY",
                "homeScore": 3,
                "awayScore": 2,
                "isCompleted": True,
                "round": 1,
            },
            {
                "gameId": 2,
                "gameDate": "2026-04-17",
                "homeTeam": "EDM",
                "awayTeam": "CGY",
                "homeScore": None,
                "awayScore": None,
                "isCompleted": False,
                "round": 1,
            },
        ]
        result = build_series_from_games(games)
        assert len(result) == 1
        assert result[0]["next_game"] is not None
        assert result[0]["next_game"]["gameId"] == 2

    def test_status_string_tied(self):
        games = [
            {
                "gameId": 1, "gameDate": "2026-04-15",
                "homeTeam": "EDM", "awayTeam": "CGY",
                "homeScore": 3, "awayScore": 2,
                "isCompleted": True, "round": 1,
            },
            {
                "gameId": 2, "gameDate": "2026-04-17",
                "homeTeam": "CGY", "awayTeam": "EDM",
                "homeScore": 4, "awayScore": 1,
                "isCompleted": True, "round": 1,
            },
        ]
        result = build_series_from_games(games)
        assert "tied" in result[0]["seriesStatus"].lower()

    def test_missing_teams_skipped(self):
        games = [
            {
                "gameId": 1,
                "gameDate": "2026-04-15",
                "homeTeam": "",
                "awayTeam": "CGY",
                "homeScore": 3,
                "awayScore": 2,
                "isCompleted": True,
            },
        ]
        result = build_series_from_games(games)
        assert len(result) == 0


class TestGetCompletedSeries:
    def test_filters_completed(self):
        series = [
            {"topSeed": "EDM", "is_complete": True, "winner": "EDM"},
            {"topSeed": "VAN", "is_complete": False, "winner": None},
        ]
        result = get_completed_series(series)
        assert len(result) == 1
        assert result[0]["topSeed"] == "EDM"


class TestGetActiveSeries:
    def test_filters_active(self):
        series = [
            {"topSeed": "EDM", "is_complete": True, "winner": "EDM"},
            {"topSeed": "VAN", "is_complete": False, "winner": None},
        ]
        result = get_active_series(series)
        assert len(result) == 1
        assert result[0]["topSeed"] == "VAN"
