"""Tests for models/projections.py."""

import pandas as pd
import pytest

from models.projections import (
    build_playoff_projection_table,
    compute_outlook,
    get_seed_prob_distribution,
)


def _make_standings(n_teams: int = 16, conference: str = "Western") -> pd.DataFrame:
    """Build a minimal fake standings DataFrame."""
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
            "conferenceSequence": i + 1,
            "divisionSequence": (i % 8) + 1,
            "wildcardSequence": 0,
            "l10Wins": 6,
            "l10Losses": 3,
            "l10OtLosses": 1,
        })
    return pd.DataFrame(rows)


class TestComputeOutlook:
    def test_basic_outlook(self):
        stdf = _make_standings()
        metrics = {"T00": {"points": 100, "gamesPlayed": 70, "goalDifferential": 30,
                           "wins": 45, "losses": 20, "otl": 5}}
        result = compute_outlook("T00", stdf, metrics)
        assert "playoff_odds" in result
        assert "projected_points" in result
        assert "projected_record" in result
        assert 0 < result["playoff_odds"] <= 100

    def test_empty_standings(self):
        result = compute_outlook("EDM", pd.DataFrame(), {})
        assert result["projected_points"] >= 0


class TestBuildPlayoffProjectionTable:
    def test_produces_table(self):
        stdf = _make_standings()
        tbl = build_playoff_projection_table(stdf, "Western")
        assert not tbl.empty
        assert "proj_pts" in tbl.columns
        assert "in_playoffs" in tbl.columns

    def test_empty_standings(self):
        tbl = build_playoff_projection_table(pd.DataFrame(), "Western")
        assert tbl.empty


class TestGetSeedProbDistribution:
    def test_returns_probs(self):
        stdf = _make_standings()
        probs = get_seed_prob_distribution("T00", stdf)
        assert isinstance(probs, dict)
        if probs:
            assert all(1 <= k <= 8 for k in probs)
            assert abs(sum(probs.values()) - 100) < 1.0

    def test_unknown_team(self):
        stdf = _make_standings()
        probs = get_seed_prob_distribution("UNKNOWN", stdf)
        assert probs == {}
