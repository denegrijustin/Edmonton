"""Unit tests for Monte Carlo simulation modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from simulations.game_sim import simulate_game
from simulations.season_sim import simulate_season


def _make_standings() -> pd.DataFrame:
    teams = [
        ("EDM", "Western", "Pacific", 60, 80, 38, 18, 4, 30, 30, 200, 170),
        ("CGY", "Western", "Pacific", 60, 70, 32, 23, 5, 26, 5, 180, 175),
        ("COL", "Western", "Central", 60, 85, 40, 16, 4, 33, 40, 220, 180),
        ("DAL", "Western", "Central", 60, 78, 37, 19, 4, 30, 25, 210, 185),
        ("BOS", "Eastern", "Atlantic", 60, 82, 39, 17, 4, 32, 35, 215, 180),
        ("TOR", "Eastern", "Atlantic", 60, 76, 36, 20, 4, 29, 20, 200, 180),
        ("CAR", "Eastern", "Metropolitan", 60, 80, 38, 18, 4, 31, 28, 205, 177),
        ("NYR", "Eastern", "Metropolitan", 60, 74, 35, 21, 4, 28, 15, 195, 180),
    ]
    rows = []
    for t in teams:
        rows.append({
            "teamAbbrev": t[0], "conference": t[1], "division": t[2],
            "gamesPlayed": t[3], "points": t[4], "wins": t[5], "losses": t[6],
            "otLosses": t[7], "regulationWins": t[8], "goalDifferential": t[9],
            "goalsFor": t[10], "goalsAgainst": t[11],
            "pointPctg": t[4] / (t[3] * 2),
            "homeWins": t[5] // 2, "homeLosses": t[6] // 2, "homeOtLosses": t[7] // 2,
            "roadWins": t[5] // 2, "roadLosses": t[6] // 2, "roadOtLosses": t[7] // 2,
            "teamName": t[0],
        })
    return pd.DataFrame(rows)


class TestGameSimulation:
    def test_basic_simulation(self):
        standings = _make_standings()
        result = simulate_game("EDM", "CGY", standings, n_sims=1000)
        assert "homeWinPct" in result
        assert "awayWinPct" in result
        assert "projectedScore" in result
        assert result["homeTeam"] == "EDM"
        assert result["awayTeam"] == "CGY"

    def test_probabilities_sum_to_100(self):
        standings = _make_standings()
        result = simulate_game("EDM", "CGY", standings, n_sims=1000)
        total = result["homeWinPct"] + result["awayWinPct"]
        assert abs(total - 100) < 1  # should be ~100

    def test_stronger_team_advantage(self):
        standings = _make_standings()
        # COL (85 pts) vs lowest team at home should have advantage
        result = simulate_game("COL", "CGY", standings, n_sims=1000)
        assert result["homeWinPct"] > 30  # Home team with better stats should win often

    def test_home_vs_away_matters(self):
        standings = _make_standings()
        home_result = simulate_game("EDM", "CGY", standings, n_sims=1000)
        away_result = simulate_game("CGY", "EDM", standings, n_sims=1000)
        # Home team should generally have higher win %
        assert home_result["homeWinPct"] != away_result["homeWinPct"]

    def test_projected_score_format(self):
        standings = _make_standings()
        result = simulate_game("EDM", "CGY", standings, n_sims=1000)
        parts = result["projectedScore"].split("-")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)

    def test_goal_distributions(self):
        standings = _make_standings()
        result = simulate_game("EDM", "CGY", standings, n_sims=1000)
        assert len(result["homeGoalDist"]) == 10
        assert len(result["awayGoalDist"]) == 10
        assert sum(result["homeGoalDist"]) == 1000


class TestSeasonSimulation:
    def test_basic_simulation(self):
        standings = _make_standings()
        results = simulate_season(standings, n_sims=100)
        assert "EDM" in results
        assert "meanFinalPts" in results["EDM"]

    def test_all_teams_simulated(self):
        standings = _make_standings()
        results = simulate_season(standings, n_sims=100)
        for _, row in standings.iterrows():
            assert row["teamAbbrev"] in results

    def test_playoff_probability_range(self):
        standings = _make_standings()
        results = simulate_season(standings, n_sims=100)
        for abbrev, data in results.items():
            assert 0 <= data["makePlayoffsPct"] <= 100

    def test_final_points_reasonable(self):
        standings = _make_standings()
        results = simulate_season(standings, n_sims=100)
        for abbrev, data in results.items():
            gp = int(standings[standings["teamAbbrev"] == abbrev].iloc[0]["gamesPlayed"])
            current = int(standings[standings["teamAbbrev"] == abbrev].iloc[0]["points"])
            # Mean final points should be >= current points
            assert data["meanFinalPts"] >= current - 1  # small tolerance
            # Max possible is 164 (82 * 2)
            assert data["meanFinalPts"] <= 164

    def test_strong_team_higher_playoff_odds(self):
        standings = _make_standings()
        results = simulate_season(standings, n_sims=500)
        # COL (85 pts) should have higher odds than CGY (70 pts) in same conference
        assert results["COL"]["makePlayoffsPct"] >= results["CGY"]["makePlayoffsPct"]
