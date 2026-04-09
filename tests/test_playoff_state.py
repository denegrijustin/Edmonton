"""Tests for services/playoff_state.py — playoff state helpers.

All tests are fully offline — no real NHL API calls are made.
"""

import pytest

from services.playoff_state import (
    get_team_playoff_record,
    get_team_series,
    is_team_in_playoffs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_series(top, bot, top_w=0, bot_w=0, rnd=1):
    return {
        "topSeed": top,
        "bottomSeed": bot,
        "topSeedWins": top_w,
        "bottomSeedWins": bot_w,
        "round": rnd,
    }


def _sample_bracket():
    return [
        _make_series("EDM", "LAK", 4, 2, rnd=1),
        _make_series("VGK", "CGY", 3, 1, rnd=1),
        _make_series("EDM", "VGK", 1, 2, rnd=2),
    ]


# ---------------------------------------------------------------------------
# is_team_in_playoffs
# ---------------------------------------------------------------------------

class TestIsTeamInPlayoffs:
    def test_top_seed_found(self):
        assert is_team_in_playoffs("EDM", _sample_bracket()) is True

    def test_bottom_seed_found(self):
        assert is_team_in_playoffs("LAK", _sample_bracket()) is True

    def test_team_not_in_bracket(self):
        assert is_team_in_playoffs("TOR", _sample_bracket()) is False

    def test_empty_series_list(self):
        assert is_team_in_playoffs("EDM", []) is False


# ---------------------------------------------------------------------------
# get_team_series
# ---------------------------------------------------------------------------

class TestGetTeamSeries:
    def test_returns_active_series(self):
        """EDM has completed R1 (4-2) and active R2 (1-2)."""
        result = get_team_series("EDM", _sample_bracket())
        assert result is not None
        assert result["round"] == 2
        assert result["topSeed"] == "EDM"

    def test_returns_none_for_non_playoff_team(self):
        assert get_team_series("TOR", _sample_bracket()) is None

    def test_returns_none_when_all_series_complete(self):
        """LAK lost in R1 (4-2) → no active series."""
        assert get_team_series("LAK", _sample_bracket()) is None

    def test_returns_highest_round(self):
        """VGK is in both R1 (3-1, active) and R2 (1-2, active).
        Should return the R2 series."""
        result = get_team_series("VGK", _sample_bracket())
        assert result is not None
        assert result["round"] == 2


# ---------------------------------------------------------------------------
# get_team_playoff_record
# ---------------------------------------------------------------------------

class TestGetTeamPlayoffRecord:
    def test_aggregate_record_top_seed(self):
        """EDM: R1 top 4-2, R2 top 1-2 → wins=5, losses=4."""
        record = get_team_playoff_record("EDM", _sample_bracket())
        assert record["wins"] == 5
        assert record["losses"] == 4

    def test_aggregate_record_bottom_seed(self):
        """LAK: R1 bottom 4-2 → wins=2, losses=4."""
        record = get_team_playoff_record("LAK", _sample_bracket())
        assert record["wins"] == 2
        assert record["losses"] == 4

    def test_non_playoff_team(self):
        record = get_team_playoff_record("TOR", _sample_bracket())
        assert record == {"wins": 0, "losses": 0}

    def test_empty_series_list(self):
        record = get_team_playoff_record("EDM", [])
        assert record == {"wins": 0, "losses": 0}
