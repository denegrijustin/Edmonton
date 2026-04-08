"""Tests for season simulation engine and related components.

All tests are fully offline — no real NHL API calls are made.
"""

import math

import pandas as pd
import pytest

from models.season_sim import (
    compute_win_probability,
    run_season_simulation,
    _assign_conference_seeds,
    _sort_by_tiebreaks,
)
from models.playoff_series_sim import simulate_series, simulate_full_bracket
from utils.state_detection import SeasonState, detect_season_state


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_metrics(points=80, gp=65, goal_diff=10, momentum=55):
    return {
        "points": points,
        "gamesPlayed": gp,
        "goalDifferential": goal_diff,
        "momentum": momentum,
    }


def _make_standings(n_teams=16, conference="Western", same_div=False):
    """Build a minimal 16-team standings DataFrame with two divisions."""
    rows = []
    for i in range(n_teams):
        div = "Pacific" if (i < 8 or same_div) else "Central"
        rows.append(
            {
                "teamAbbrev": f"T{i:02d}",
                "teamName": f"Team {i}",
                "conference": conference,
                "division": div,
                "gamesPlayed": 70 - i,
                "points": 100 - i * 3,
                "wins": 45 - i,
                "losses": 20 + i,
                "otLosses": 5,
                "goalFor": 230.0 - i * 5,
                "goalAgainst": 200.0 + i * 3,
                "goalDifferential": float(30 - i * 8),
                "conferenceSequence": i + 1,
                "divisionSequence": (i % 8) + 1,
                "wildcardSequence": 0,
                "l10Wins": 6,
                "l10Losses": 3,
                "l10OtLosses": 1,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# compute_win_probability tests
# ---------------------------------------------------------------------------

class TestComputeWinProbability:
    def test_returns_float_in_unit_interval(self):
        ma = _make_metrics(points=90, gp=70, goal_diff=20, momentum=60)
        mb = _make_metrics(points=70, gp=70, goal_diff=-5, momentum=45)
        p = compute_win_probability(ma, mb)
        assert isinstance(p, float)
        assert 0.0 <= p <= 1.0

    def test_bounded_minimum(self):
        """Even a hopeless team should have at least 5% chance."""
        ma = _make_metrics(points=10, gp=70, goal_diff=-80, momentum=20)
        mb = _make_metrics(points=110, gp=70, goal_diff=80, momentum=80)
        p = compute_win_probability(ma, mb)
        assert p >= 0.05

    def test_bounded_maximum(self):
        """Even a dominant team should be capped at 95%."""
        ma = _make_metrics(points=110, gp=70, goal_diff=80, momentum=80)
        mb = _make_metrics(points=10, gp=70, goal_diff=-80, momentum=20)
        p = compute_win_probability(ma, mb)
        assert p <= 0.95

    def test_home_advantage_increases_home_win_prob(self):
        ma = _make_metrics(points=85, gp=70, goal_diff=5, momentum=52)
        mb = _make_metrics(points=85, gp=70, goal_diff=5, momentum=52)
        p_home_a = compute_win_probability(ma, mb, home="a")
        p_home_b = compute_win_probability(ma, mb, home="b")
        assert p_home_a > p_home_b

    def test_symmetric_equal_teams_near_half(self):
        """Equal teams with home advantage should give ~55% to home team."""
        ma = _make_metrics(points=80, gp=70, goal_diff=0, momentum=50)
        mb = _make_metrics(points=80, gp=70, goal_diff=0, momentum=50)
        p = compute_win_probability(ma, mb, home="a")
        assert 0.50 < p < 0.65

    def test_strong_vs_weak_team(self):
        """Better team should win more than 50% away."""
        strong = _make_metrics(points=110, gp=70, goal_diff=50, momentum=70)
        weak = _make_metrics(points=50, gp=70, goal_diff=-50, momentum=30)
        p = compute_win_probability(strong, weak, home="b")  # strong team is away
        assert p > 0.5

    def test_handles_zero_games_played(self):
        """Zero gamesPlayed should not raise an error."""
        ma = _make_metrics(gp=0)
        mb = _make_metrics(gp=0)
        p = compute_win_probability(ma, mb)
        assert 0.0 <= p <= 1.0


# ---------------------------------------------------------------------------
# run_season_simulation tests
# ---------------------------------------------------------------------------

class TestRunSeasonSimulation:
    def test_returns_correct_keys(self):
        stdf = _make_standings()
        metrics = {
            row["teamAbbrev"]: _make_metrics(
                points=row["points"],
                gp=row["gamesPlayed"],
                goal_diff=int(row["goalDifferential"]),
            )
            for _, row in stdf.iterrows()
        }
        result = run_season_simulation(stdf, [], metrics, n_sims=50)
        assert "playoff_odds" in result
        assert "division_title_odds" in result
        assert "wild_card_odds" in result
        assert "seed_odds" in result
        assert "projected_final_standings" in result
        assert "likely_final_ranking" in result
        assert "most_likely_finish" in result

    def test_playoff_odds_in_range(self):
        stdf = _make_standings()
        metrics = {
            row["teamAbbrev"]: _make_metrics(points=row["points"], gp=row["gamesPlayed"])
            for _, row in stdf.iterrows()
        }
        result = run_season_simulation(stdf, [], metrics, n_sims=100)
        for team, odds in result["playoff_odds"].items():
            assert 0.0 <= odds <= 100.0, f"{team}: playoff_odds={odds} out of range"

    def test_division_title_odds_in_range(self):
        stdf = _make_standings()
        metrics = {r["teamAbbrev"]: _make_metrics() for _, r in stdf.iterrows()}
        result = run_season_simulation(stdf, [], metrics, n_sims=50)
        for team, odds in result["division_title_odds"].items():
            assert 0.0 <= odds <= 100.0

    def test_seed_odds_keys(self):
        stdf = _make_standings()
        metrics = {r["teamAbbrev"]: _make_metrics() for _, r in stdf.iterrows()}
        result = run_season_simulation(stdf, [], metrics, n_sims=50)
        for team, seeds in result["seed_odds"].items():
            assert set(seeds.keys()) == set(range(1, 9))

    def test_projected_standings_is_dataframe(self):
        stdf = _make_standings()
        metrics = {r["teamAbbrev"]: _make_metrics() for _, r in stdf.iterrows()}
        result = run_season_simulation(stdf, [], metrics, n_sims=50)
        assert isinstance(result["projected_final_standings"], pd.DataFrame)

    def test_empty_standings_returns_empty(self):
        result = run_season_simulation(pd.DataFrame(), [], {}, n_sims=10)
        assert result["playoff_odds"] == {}
        assert result["projected_final_standings"].empty

    def test_with_remaining_games(self):
        """Simulation with a few remaining games should still return valid results."""
        stdf = _make_standings()
        metrics = {r["teamAbbrev"]: _make_metrics() for _, r in stdf.iterrows()}
        games = [
            {"gameId": 1, "homeTeam": "T00", "awayTeam": "T01"},
            {"gameId": 2, "homeTeam": "T02", "awayTeam": "T03"},
        ]
        result = run_season_simulation(stdf, games, metrics, n_sims=100)
        assert "T00" in result["playoff_odds"]

    def test_likely_final_ranking_structure(self):
        stdf = _make_standings()
        metrics = {r["teamAbbrev"]: _make_metrics() for _, r in stdf.iterrows()}
        result = run_season_simulation(stdf, [], metrics, n_sims=50)
        for team, ranking in result["likely_final_ranking"].items():
            assert "league_rank" in ranking
            assert "conf_rank" in ranking
            assert "div_rank" in ranking
            assert "proj_pts" in ranking
            assert "proj_pts_p10" in ranking
            assert "proj_pts_p90" in ranking


# ---------------------------------------------------------------------------
# simulate_series tests
# ---------------------------------------------------------------------------

class TestSimulateSeries:
    def _metrics(self):
        return {
            "EDM": _make_metrics(points=95, gp=72, goal_diff=25, momentum=58),
            "CGY": _make_metrics(points=85, gp=72, goal_diff=5, momentum=50),
        }

    def test_returns_correct_keys(self):
        result = simulate_series("EDM", "CGY", self._metrics(), n_sims=200)
        assert "team_a_wins_prob" in result
        assert "team_b_wins_prob" in result
        assert "most_likely_length" in result
        assert "games_remaining_avg" in result

    def test_probabilities_sum_to_one(self):
        result = simulate_series("EDM", "CGY", self._metrics(), n_sims=1000)
        total = result["team_a_wins_prob"] + result["team_b_wins_prob"]
        assert abs(total - 1.0) < 0.001

    def test_probabilities_in_unit_interval(self):
        result = simulate_series("EDM", "CGY", self._metrics(), n_sims=500)
        assert 0.0 <= result["team_a_wins_prob"] <= 1.0
        assert 0.0 <= result["team_b_wins_prob"] <= 1.0

    def test_series_already_won(self):
        """If one team already has 4 wins, it should win 100% of the time."""
        result = simulate_series("EDM", "CGY", self._metrics(), wins_a=4, wins_b=1, n_sims=100)
        # Once team has 4 wins, no further simulation — but our code starts from
        # current state so team_a_wins_prob should be 1.0
        assert result["team_a_wins_prob"] == 1.0

    def test_most_likely_length_is_reasonable(self):
        result = simulate_series("EDM", "CGY", self._metrics(), n_sims=500)
        # Best of 7: minimum 4 games, maximum 7 games
        assert 4 <= result["most_likely_length"] <= 7

    def test_partial_series_state(self):
        """Already 2-1 in series should still produce valid probabilities."""
        result = simulate_series("EDM", "CGY", self._metrics(), wins_a=2, wins_b=1, n_sims=500)
        assert 0.0 <= result["team_a_wins_prob"] <= 1.0


# ---------------------------------------------------------------------------
# simulate_full_bracket tests
# ---------------------------------------------------------------------------

class TestSimulateFullBracket:
    def _metrics(self):
        teams = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]
        return {t: _make_metrics(points=100 - i * 5) for i, t in enumerate(teams)}

    def _series_list(self):
        return [
            {"round": 1, "topSeed": "T1", "bottomSeed": "T8", "topSeedWins": 0, "bottomSeedWins": 0, "seriesLetter": "A"},
            {"round": 1, "topSeed": "T2", "bottomSeed": "T7", "topSeedWins": 0, "bottomSeedWins": 0, "seriesLetter": "B"},
            {"round": 1, "topSeed": "T3", "bottomSeed": "T6", "topSeedWins": 0, "bottomSeedWins": 0, "seriesLetter": "C"},
            {"round": 1, "topSeed": "T4", "bottomSeed": "T5", "topSeedWins": 0, "bottomSeedWins": 0, "seriesLetter": "D"},
        ]

    def test_returns_dict(self):
        result = simulate_full_bracket(self._series_list(), self._metrics(), n_sims=100)
        assert isinstance(result, dict)

    def test_empty_series_list(self):
        result = simulate_full_bracket([], self._metrics(), n_sims=100)
        assert result == {}

    def test_cup_odds_structure(self):
        result = simulate_full_bracket(self._series_list(), self._metrics(), n_sims=200)
        for team, odds in result.items():
            assert "cup_odds" in odds
            assert "next_round_odds" in odds
            assert 0.0 <= odds["cup_odds"] <= 100.0


# ---------------------------------------------------------------------------
# detect_season_state tests
# ---------------------------------------------------------------------------

class TestDetectSeasonState:
    def test_regular_season_when_games_remain(self):
        """Any team with < 82 games played → REGULAR_SEASON."""
        stdf = _make_standings()
        # gamesPlayed is 70 in our fixture, well under 82
        state = detect_season_state("20252026", stdf)
        # Without playoff data (API call mocked away), should be REGULAR_SEASON
        assert state == SeasonState.REGULAR_SEASON

    def test_offseason_when_all_82_played(self):
        """All teams at 82 GP and no playoff data → OFFSEASON."""
        stdf = _make_standings()
        stdf["gamesPlayed"] = 82
        # Mock detect_playoff_state to indicate no playoffs
        import unittest.mock as mock
        from services.playoff_state import PlayoffState
        with mock.patch("services.playoff_state.detect_playoff_state", return_value=PlayoffState(playoffs_started=False)):
            state = detect_season_state("20252026", stdf)
        assert state == SeasonState.OFFSEASON

    def test_playoffs_when_is_playoff_active_true(self):
        """Playoff games detected in schedules → PLAYOFFS regardless of standings."""
        stdf = _make_standings()
        import unittest.mock as mock
        from services.playoff_state import PlayoffState
        with mock.patch("services.playoff_state.detect_playoff_state", return_value=PlayoffState(playoffs_started=True, current_round=1)):
            state = detect_season_state("20252026", stdf)
        assert state == SeasonState.PLAYOFFS

    def test_empty_standings_defaults_to_offseason(self):
        """Empty standings with no playoffs → OFFSEASON."""
        import unittest.mock as mock
        from services.playoff_state import PlayoffState
        with mock.patch("services.playoff_state.detect_playoff_state", return_value=PlayoffState(playoffs_started=False)):
            state = detect_season_state("20252026", pd.DataFrame())
        assert state == SeasonState.OFFSEASON

    def test_season_state_enum_values(self):
        assert SeasonState.REGULAR_SEASON.value == "REGULAR_SEASON"
        assert SeasonState.PLAYOFFS.value == "PLAYOFFS"
        assert SeasonState.OFFSEASON.value == "OFFSEASON"
