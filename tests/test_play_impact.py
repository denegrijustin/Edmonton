"""Tests for services.play_impact — play ranking from play-by-play."""

import pandas as pd
import pytest

from services.play_impact import (
    find_last_completed_game,
    _compute_play_impact,
    _annotate_callouts,
)


class TestFindLastCompletedGame:
    """Test finding the most recent completed game."""

    def test_empty_schedule(self):
        result = find_last_completed_game(pd.DataFrame(), "EDM")
        assert result is None

    def test_no_completed_games(self):
        schedule = pd.DataFrame({
            "gameId": [1, 2],
            "gameDate": ["2026-04-15", "2026-04-17"],
            "homeTeam": ["EDM", "CGY"],
            "awayTeam": ["CGY", "EDM"],
            "isCompleted": [False, False],
        })
        result = find_last_completed_game(schedule, "EDM")
        assert result is None

    def test_finds_most_recent(self):
        schedule = pd.DataFrame({
            "gameId": [1, 2, 3],
            "gameDate": ["2026-04-10", "2026-04-12", "2026-04-15"],
            "homeTeam": ["EDM", "CGY", "EDM"],
            "awayTeam": ["CGY", "EDM", "VAN"],
            "homeScore": [3, 2, None],
            "awayScore": [2, 3, None],
            "isCompleted": [True, True, False],
        })
        result = find_last_completed_game(schedule, "EDM")
        assert result is not None
        assert result["gameId"] == 2
        assert result["opponent"] == "CGY"

    def test_home_vs_away_detection(self):
        schedule = pd.DataFrame({
            "gameId": [1],
            "gameDate": ["2026-04-10"],
            "homeTeam": ["CGY"],
            "awayTeam": ["EDM"],
            "homeScore": [2],
            "awayScore": [3],
            "isCompleted": [True],
        })
        result = find_last_completed_game(schedule, "EDM")
        assert result["isHome"] is False
        assert result["opponent"] == "CGY"


class TestComputePlayImpact:
    """Test the play impact scoring model."""

    def test_goal_in_third_period_close_game(self):
        impact = _compute_play_impact(
            base_impact=8.0,
            event_type="goal",
            period=3,
            time_remaining="05:00",
            home_score=2,
            away_score=2,
            details={},
        )
        # Should be boosted: 3rd period, tied game, late
        assert impact > 8.0

    def test_first_period_blowout(self):
        impact = _compute_play_impact(
            base_impact=8.0,
            event_type="goal",
            period=1,
            time_remaining="15:00",
            home_score=0,
            away_score=5,
            details={},
        )
        # Less impactful: 1st period, blowout
        assert impact < 15.0

    def test_penalty_impact(self):
        impact = _compute_play_impact(
            base_impact=3.0,
            event_type="penalty",
            period=2,
            time_remaining="10:00",
            home_score=1,
            away_score=1,
            details={},
        )
        assert impact > 0


class TestAnnotateCallouts:
    """Test special play annotations."""

    def test_turning_point(self):
        plays = [
            {"impact_score": 10, "is_positive": True, "event_type": "goal"},
            {"impact_score": 5, "is_positive": False, "event_type": "penalty"},
        ]
        _annotate_callouts(plays)
        assert plays[0].get("callout") == "Turning Point"

    def test_most_damaging(self):
        plays = [
            {"impact_score": 10, "is_positive": True, "event_type": "goal"},
            {"impact_score": -8, "is_positive": False, "event_type": "penalty"},
        ]
        _annotate_callouts(plays)
        assert plays[1].get("callout") == "Most Damaging Negative Play"

    def test_empty_plays(self):
        plays = []
        _annotate_callouts(plays)
        assert plays == []
