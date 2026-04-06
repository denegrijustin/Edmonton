"""Tests for models/monte_carlo.py — simulation model."""

import numpy as np
import pytest

from models.monte_carlo import monte_carlo_sim


def _dummy_metrics(**overrides):
    base = {
        "gf_per_game": 3.0,
        "ga_per_game": 2.8,
        "last10_gf_per_game": 3.2,
        "last10_ga_per_game": 2.5,
    }
    base.update(overrides)
    return base


class TestMonteCarloSim:
    def test_returns_expected_keys(self):
        res = monte_carlo_sim(_dummy_metrics(), _dummy_metrics(), n_sims=100)
        assert "a_win_pct" in res
        assert "b_win_pct" in res
        assert "ot_pct" in res
        assert "a_avg_goals" in res
        assert "b_avg_goals" in res
        assert "a_lambda" in res
        assert "b_lambda" in res

    def test_probabilities_sum_to_100(self):
        res = monte_carlo_sim(_dummy_metrics(), _dummy_metrics(), n_sims=10000)
        total = res["a_win_pct"] + res["b_win_pct"]
        assert abs(total - 100.0) < 0.01

    def test_home_advantage(self):
        ma = _dummy_metrics()
        mb = _dummy_metrics()
        res_a_home = monte_carlo_sim(ma, mb, home_team="A", n_sims=10000)
        res_b_home = monte_carlo_sim(ma, mb, home_team="B", n_sims=10000)
        # Home team should win more often on average
        assert res_a_home["a_lambda"] > res_b_home["a_lambda"]

    def test_goals_are_non_negative(self):
        res = monte_carlo_sim(_dummy_metrics(), _dummy_metrics(), n_sims=1000)
        assert res["a_avg_goals"] >= 0
        assert res["b_avg_goals"] >= 0
        assert (res["a_goals_arr"] >= 0).all()
        assert (res["b_goals_arr"] >= 0).all()

    def test_lambda_minimum(self):
        weak = _dummy_metrics(gf_per_game=0.1, last10_gf_per_game=0.1)
        res = monte_carlo_sim(weak, _dummy_metrics(), n_sims=100)
        assert res["a_lambda"] >= 0.5
        assert res["b_lambda"] >= 0.5
