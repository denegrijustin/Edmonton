"""Tests for services/series_tracker.py — playoff series state tracking.

All tests are fully offline — no real NHL API calls are made.
"""

import pytest

from services.series_tracker import (
    build_bracket_state,
    compute_series_state,
    get_series_winner,
    is_series_complete,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_series(top="EDM", bot="LAK", top_w=0, bot_w=0):
    return {
        "topSeed": top,
        "bottomSeed": bot,
        "topSeedWins": top_w,
        "bottomSeedWins": bot_w,
        "round": 1,
    }


# ---------------------------------------------------------------------------
# compute_series_state
# ---------------------------------------------------------------------------

class TestComputeSeriesState:
    def test_complete_sweep(self):
        state = compute_series_state(_make_series(top_w=4, bot_w=0))
        assert state["completed"] is True
        assert state["winner"] == "EDM"
        assert state["tied"] is False
        assert state["wins_to_advance"] == 0
        assert "EDM wins" in state["status_text"]

    def test_incomplete_leading(self):
        state = compute_series_state(_make_series(top_w=2, bot_w=1))
        assert state["completed"] is False
        assert state["winner"] is None
        assert state["leading"] == "EDM"
        assert state["tied"] is False
        assert state["wins_to_advance"] == 2

    def test_tied_series(self):
        state = compute_series_state(_make_series(top_w=2, bot_w=2))
        assert state["completed"] is False
        assert state["winner"] is None
        assert state["tied"] is True
        assert state["leading"] is None
        assert "Tied" in state["status_text"]

    def test_bottom_seed_wins(self):
        state = compute_series_state(_make_series(top_w=3, bot_w=4))
        assert state["completed"] is True
        assert state["winner"] == "LAK"

    def test_status_text_leading(self):
        state = compute_series_state(_make_series(top_w=3, bot_w=1))
        assert "EDM leads 3-1" in state["status_text"]


# ---------------------------------------------------------------------------
# is_series_complete
# ---------------------------------------------------------------------------

class TestIsSeriesComplete:
    def test_complete_when_top_wins_4(self):
        assert is_series_complete(_make_series(top_w=4, bot_w=2)) is True

    def test_complete_when_bottom_wins_4(self):
        assert is_series_complete(_make_series(top_w=1, bot_w=4)) is True

    def test_incomplete(self):
        assert is_series_complete(_make_series(top_w=3, bot_w=3)) is False

    def test_fresh_series(self):
        assert is_series_complete(_make_series(top_w=0, bot_w=0)) is False


# ---------------------------------------------------------------------------
# get_series_winner
# ---------------------------------------------------------------------------

class TestGetSeriesWinner:
    def test_winner_top_seed(self):
        assert get_series_winner(_make_series(top_w=4, bot_w=1)) == "EDM"

    def test_winner_bottom_seed(self):
        assert get_series_winner(_make_series(top_w=2, bot_w=4)) == "LAK"

    def test_none_when_incomplete(self):
        assert get_series_winner(_make_series(top_w=3, bot_w=3)) is None

    def test_none_when_fresh(self):
        assert get_series_winner(_make_series(top_w=0, bot_w=0)) is None


# ---------------------------------------------------------------------------
# build_bracket_state
# ---------------------------------------------------------------------------

class TestBuildBracketState:
    def test_enriches_each_series(self):
        series_list = [
            _make_series("EDM", "LAK", 4, 1),
            _make_series("VGK", "CGY", 2, 2),
        ]
        result = build_bracket_state(series_list)
        assert len(result) == 2

        # First series (completed)
        assert result[0]["completed"] is True
        assert result[0]["winner"] == "EDM"
        assert result[0]["topSeed"] == "EDM"  # original keys preserved

        # Second series (tied)
        assert result[1]["completed"] is False
        assert result[1]["tied"] is True

    def test_empty_list(self):
        assert build_bracket_state([]) == []

    def test_preserves_original_keys(self):
        s = _make_series("EDM", "LAK", 1, 0)
        s["seriesLetter"] = "A"
        result = build_bracket_state([s])
        assert result[0]["seriesLetter"] == "A"
        assert "leading" in result[0]
