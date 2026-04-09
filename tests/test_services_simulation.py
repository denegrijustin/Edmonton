"""Tests for services/simulation.py — on-demand Monte Carlo wrapper.

All tests are fully offline — lower-level simulation functions are mocked.
"""

import unittest.mock as mock

import pytest

from services.simulation import SIM_DEPTHS, get_sim_depth, simulate_single_game, simulate_playoff_series


# ---------------------------------------------------------------------------
# SIM_DEPTHS
# ---------------------------------------------------------------------------

class TestSimDepths:
    def test_quick(self):
        assert SIM_DEPTHS["Quick"] == 100

    def test_standard(self):
        assert SIM_DEPTHS["Standard"] == 250

    def test_deep(self):
        assert SIM_DEPTHS["Deep"] == 1000

    def test_has_exactly_three_keys(self):
        assert set(SIM_DEPTHS.keys()) == {"Quick", "Standard", "Deep"}


# ---------------------------------------------------------------------------
# get_sim_depth
# ---------------------------------------------------------------------------

class TestGetSimDepth:
    def test_quick(self):
        assert get_sim_depth("Quick") == 100

    def test_standard(self):
        assert get_sim_depth("Standard") == 250

    def test_deep(self):
        assert get_sim_depth("Deep") == 1000

    def test_unknown_key_returns_standard(self):
        assert get_sim_depth("Unknown") == 250

    def test_empty_string_returns_standard(self):
        assert get_sim_depth("") == 250


# ---------------------------------------------------------------------------
# simulate_single_game
# ---------------------------------------------------------------------------

class TestSimulateSingleGame:
    @mock.patch("services.simulation.monte_carlo_sim")
    def test_returns_labelled_result(self, mock_sim):
        mock_sim.return_value = {"a_win_pct": 55.0, "b_win_pct": 45.0}
        metrics = {"EDM": {}, "CGY": {}}
        result = simulate_single_game("EDM", "CGY", metrics, n_sims=100)
        assert result["team_a"] == "EDM"
        assert result["team_b"] == "CGY"
        assert result["label"] == "Simulated"
        assert result["a_win_pct"] == 55.0

    @mock.patch("services.simulation.monte_carlo_sim")
    def test_passes_home_team_A(self, mock_sim):
        mock_sim.return_value = {}
        simulate_single_game("EDM", "CGY", {"EDM": {}, "CGY": {}}, home="A")
        mock_sim.assert_called_once()
        assert mock_sim.call_args[1]["home_team"] == "A" or mock_sim.call_args[0][2] == "A"

    @mock.patch("services.simulation.monte_carlo_sim")
    def test_passes_home_team_B(self, mock_sim):
        mock_sim.return_value = {}
        simulate_single_game("EDM", "CGY", {"EDM": {}, "CGY": {}}, home="B")
        _, kwargs = mock_sim.call_args
        assert kwargs.get("home_team") == "B"


# ---------------------------------------------------------------------------
# simulate_playoff_series
# ---------------------------------------------------------------------------

class TestSimulatePlayoffSeries:
    @mock.patch("services.simulation.simulate_series")
    def test_returns_labelled_result(self, mock_sim):
        mock_sim.return_value = {"team_a_wins_prob": 0.6, "team_b_wins_prob": 0.4}
        metrics = {"EDM": {}, "CGY": {}}
        result = simulate_playoff_series("EDM", "CGY", metrics, n_sims=100)
        assert result["team_a"] == "EDM"
        assert result["team_b"] == "CGY"
        assert result["label"] == "Simulated"
        assert result["team_a_wins_prob"] == 0.6

    @mock.patch("services.simulation.simulate_series")
    def test_forwards_wins(self, mock_sim):
        mock_sim.return_value = {}
        simulate_playoff_series("EDM", "CGY", {}, wins_a=2, wins_b=1)
        _, kwargs = mock_sim.call_args
        assert kwargs["wins_a"] == 2
        assert kwargs["wins_b"] == 1
