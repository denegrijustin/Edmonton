"""Tests for services/odds_engine.py — real-data playoff odds engine.

All tests are fully offline — no real NHL API calls are made.
"""

import pandas as pd
import pytest

from services.odds_engine import compute_remaining_difficulty, compute_team_playoff_odds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_standings(n_teams=16, conference="Western"):
    """Build a minimal standings DataFrame."""
    rows = []
    for i in range(n_teams):
        rows.append({
            "teamAbbrev": f"T{i:02d}",
            "teamName": f"Team {i}",
            "conference": conference,
            "division": "Pacific" if i < 8 else "Central",
            "gamesPlayed": 70,
            "points": 100 - i * 3,
            "wins": 45 - i,
            "losses": 20 + i,
            "otLosses": 5,
            "goalFor": 230 - i * 5,
            "goalAgainst": 200 + i * 3,
            "goalDifferential": 30 - i * 8,
            "pointPctg": (100 - i * 3) / 140,
            "conferenceSequence": i + 1,
            "divisionSequence": (i % 8) + 1,
            "wildcardSequence": 0,
            "l10Wins": 6, "l10Losses": 3, "l10OtLosses": 1,
        })
    return pd.DataFrame(rows)


def _make_metrics(points=90, gp=70, gd=20, momentum=55):
    return {
        "points": points,
        "gamesPlayed": gp,
        "goalDifferential": gd,
        "momentum": momentum,
    }


# ---------------------------------------------------------------------------
# compute_team_playoff_odds
# ---------------------------------------------------------------------------

class TestComputeTeamPlayoffOdds:
    def test_returns_expected_keys(self):
        stdf = _make_standings()
        metrics = {"T00": _make_metrics(points=100, gd=30)}
        result = compute_team_playoff_odds("T00", stdf, metrics)
        assert "playoff_odds" in result
        assert "division_odds" in result
        assert "seed_range" in result
        assert "label" in result

    def test_label_is_model_derived(self):
        stdf = _make_standings()
        metrics = {"T00": _make_metrics()}
        result = compute_team_playoff_odds("T00", stdf, metrics)
        assert result["label"] == "Model-derived"

    def test_good_team_has_high_odds(self):
        stdf = _make_standings()
        metrics = {"T00": _make_metrics(points=100, gd=30, momentum=70)}
        result = compute_team_playoff_odds("T00", stdf, metrics)
        assert result["playoff_odds"] >= 50.0

    def test_weak_team_has_lower_odds(self):
        stdf = _make_standings()
        metrics = {"T15": _make_metrics(points=55, gd=-40, momentum=30)}
        result = compute_team_playoff_odds("T15", stdf, metrics)
        assert result["playoff_odds"] < 50.0

    def test_empty_standings(self):
        result = compute_team_playoff_odds("T00", pd.DataFrame(), {"T00": _make_metrics()})
        assert result["playoff_odds"] == 0.0

    def test_missing_metrics(self):
        stdf = _make_standings()
        result = compute_team_playoff_odds("T00", stdf, {})
        assert result["playoff_odds"] == 0.0
        assert result["label"] == "Model-derived"

    def test_seed_range_is_tuple(self):
        stdf = _make_standings()
        metrics = {"T00": _make_metrics(points=100)}
        result = compute_team_playoff_odds("T00", stdf, metrics)
        assert isinstance(result["seed_range"], tuple)
        assert len(result["seed_range"]) == 2

    def test_odds_bounded(self):
        stdf = _make_standings()
        metrics = {"T00": _make_metrics(points=100, gd=80, momentum=90)}
        result = compute_team_playoff_odds("T00", stdf, metrics)
        assert 1.0 <= result["playoff_odds"] <= 99.0


# ---------------------------------------------------------------------------
# compute_remaining_difficulty
# ---------------------------------------------------------------------------

class TestComputeRemainingDifficulty:
    def test_empty_schedule_returns_half(self):
        stdf = _make_standings()
        assert compute_remaining_difficulty("T00", pd.DataFrame(), stdf) == 0.5

    def test_empty_standings_returns_half(self):
        sched = pd.DataFrame({"opponent": ["T01"], "gameOutcome": [None]})
        assert compute_remaining_difficulty("T00", sched, pd.DataFrame()) == 0.5

    def test_both_empty_returns_half(self):
        assert compute_remaining_difficulty("T00", pd.DataFrame(), pd.DataFrame()) == 0.5

    def test_with_remaining_games(self):
        stdf = _make_standings()
        sched = pd.DataFrame({
            "opponent": ["T01", "T02", "T03"],
            "gameOutcome": [None, None, None],
        })
        difficulty = compute_remaining_difficulty("T00", sched, stdf)
        assert 0.0 <= difficulty <= 1.0

    def test_all_played_returns_half(self):
        """When all games have outcomes, no remaining games → 0.5."""
        stdf = _make_standings()
        sched = pd.DataFrame({
            "opponent": ["T01", "T02"],
            "gameOutcome": ["W", "L"],
        })
        difficulty = compute_remaining_difficulty("T00", sched, stdf)
        assert difficulty == 0.5
