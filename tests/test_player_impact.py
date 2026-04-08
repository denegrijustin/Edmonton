"""Tests for services.player_impact — player impact computation."""

import pytest

from services.player_impact import (
    _compute_box_score_impact,
    get_top_bottom_players,
    MODEL_LABEL,
)


class TestComputeBoxScoreImpact:
    """Test the box-score impact model."""

    def test_skater_positive_impact(self):
        stats = {
            "p1": {
                "playerId": "p1",
                "name": "Test Player",
                "position": "Forward",
                "headshot": "",
                "games": 5,
                "goals": 3,
                "assists": 4,
                "shots": 15,
                "plusMinus": 5,
                "blockedShots": 2,
                "hits": 3,
                "pim": 4,
                "toi_seconds": 5000,
            }
        }
        result = _compute_box_score_impact(stats)
        assert len(result) == 1
        assert result[0]["impact_score"] > 0
        assert result[0]["position"] == "F"
        assert result[0]["model"] == MODEL_LABEL

    def test_goalie_impact(self):
        stats = {
            "g1": {
                "playerId": "g1",
                "name": "Test Goalie",
                "position": "Goalie",
                "headshot": "",
                "games": 3,
                "saves": 90,
                "goalsAgainst": 6,
                "shotsAgainst": 96,
                "savePct": 0.938,
                "toi_seconds": 10800,
            }
        }
        result = _compute_box_score_impact(stats)
        assert len(result) == 1
        assert result[0]["position"] == "G"
        assert "SV%" in result[0]["key_stats"]

    def test_empty_stats(self):
        result = _compute_box_score_impact({})
        assert result == []

    def test_sorting_by_impact(self):
        stats = {
            "p1": {
                "playerId": "p1", "name": "Star", "position": "Forward",
                "headshot": "", "games": 5, "goals": 10, "assists": 10,
                "shots": 30, "plusMinus": 10, "blockedShots": 0,
                "hits": 0, "pim": 0, "toi_seconds": 5000,
            },
            "p2": {
                "playerId": "p2", "name": "Bench", "position": "Forward",
                "headshot": "", "games": 5, "goals": 0, "assists": 0,
                "shots": 2, "plusMinus": -5, "blockedShots": 0,
                "hits": 0, "pim": 8, "toi_seconds": 2000,
            },
        }
        result = _compute_box_score_impact(stats)
        assert len(result) == 2
        assert result[0]["name"] == "Star"
        assert result[1]["name"] == "Bench"
        assert result[0]["impact_score"] > result[1]["impact_score"]


class TestGetTopBottomPlayers:
    def test_empty_input(self):
        result = get_top_bottom_players([])
        assert result == {"top": [], "bottom": []}

    def test_top_and_bottom(self):
        players = [
            {"name": f"P{i}", "impact_score": 10 - i}
            for i in range(10)
        ]
        result = get_top_bottom_players(players, top_n=3)
        assert len(result["top"]) == 3
        assert len(result["bottom"]) == 3
        assert result["top"][0]["name"] == "P0"

    def test_fewer_than_n(self):
        players = [
            {"name": "P1", "impact_score": 5.0},
            {"name": "P2", "impact_score": 3.0},
        ]
        result = get_top_bottom_players(players, top_n=5)
        assert len(result["top"]) == 2
        assert len(result["bottom"]) == 0
