"""Unit tests for models — playoff odds, seeds, projections."""

from __future__ import annotations

import pandas as pd
import pytest

from models.playoff_model import PlayoffModel
from models.projections import project_opponents, project_seeds
from schemas.validators import (
    validate_playoff_odds,
    validate_projected_record,
    validate_standings,
)


def _make_standings() -> pd.DataFrame:
    """Create test standings for 8 Western Conference teams."""
    teams = [
        ("EDM", "Western", "Pacific", 60, 80, 38, 18, 4, 30, 30),
        ("CGY", "Western", "Pacific", 60, 75, 35, 20, 5, 28, 15),
        ("VAN", "Western", "Pacific", 60, 70, 32, 23, 5, 26, 5),
        ("LAK", "Western", "Pacific", 60, 65, 30, 25, 5, 24, -10),
        ("COL", "Western", "Central", 60, 85, 40, 16, 4, 33, 40),
        ("DAL", "Western", "Central", 60, 78, 37, 19, 4, 30, 25),
        ("WPG", "Western", "Central", 60, 72, 33, 22, 5, 27, 10),
        ("MIN", "Western", "Central", 60, 68, 31, 24, 5, 25, 0),
        ("SEA", "Western", "Pacific", 60, 55, 25, 30, 5, 20, -20),
        ("SJS", "Western", "Pacific", 60, 45, 20, 35, 5, 16, -40),
        ("BOS", "Eastern", "Atlantic", 60, 82, 39, 17, 4, 32, 35),
        ("TOR", "Eastern", "Atlantic", 60, 76, 36, 20, 4, 29, 20),
        ("CAR", "Eastern", "Metropolitan", 60, 80, 38, 18, 4, 31, 28),
        ("NYR", "Eastern", "Metropolitan", 60, 74, 35, 21, 4, 28, 15),
    ]
    rows = []
    for t in teams:
        rows.append({
            "teamAbbrev": t[0], "conference": t[1], "division": t[2],
            "gamesPlayed": t[3], "points": t[4], "wins": t[5], "losses": t[6],
            "otLosses": t[7], "regulationWins": t[8], "goalDifferential": t[9],
            "goalsFor": 200, "goalsAgainst": 200 - t[9],
            "pointPctg": t[4] / (t[3] * 2),
            "conferenceSequence": 0, "divisionSequence": 0, "wildcardSequence": 0,
            "teamName": t[0],
            "homeWins": t[5] // 2, "homeLosses": t[6] // 2, "homeOtLosses": t[7] // 2,
            "roadWins": t[5] // 2, "roadLosses": t[6] // 2, "roadOtLosses": t[7] // 2,
            "l10Wins": 6, "l10Losses": 3, "l10OtLosses": 1,
            "streakCode": "W", "streakCount": 2,
        })
    return pd.DataFrame(rows)


def _enrich_standings() -> pd.DataFrame:
    from features.team_features import compute_team_features
    return compute_team_features(_make_standings())


class TestPlayoffModel:
    def test_odds_range(self):
        standings = _enrich_standings()
        model = PlayoffModel(standings)
        df = model.compute_playoff_odds()
        assert (df["playoffOdds"] >= 1).all()
        assert (df["playoffOdds"] <= 99).all()

    def test_top_teams_have_higher_odds(self):
        standings = _enrich_standings()
        model = PlayoffModel(standings)
        df = model.compute_playoff_odds()
        col_pts = df[df["teamAbbrev"] == "COL"]["playoffOdds"].iloc[0]
        sjs_pts = df[df["teamAbbrev"] == "SJS"]["playoffOdds"].iloc[0]
        assert col_pts > sjs_pts

    def test_seeds_assigned(self):
        standings = _enrich_standings()
        model = PlayoffModel(standings)
        df = model.compute_seeds()
        assert "projectedSeed" in df.columns
        assert (df["projectedSeed"] >= 1).all()


class TestProjections:
    def test_project_seeds(self):
        standings = _enrich_standings()
        df = project_seeds(standings)
        assert "projectedSeed" in df.columns
        # Top team in West should have seed 1
        west = df[df["conference"].str.contains("Western", case=False, na=False)]
        top_team = west.sort_values("projectedPoints", ascending=False).iloc[0]
        assert top_team["projectedSeed"] <= 3  # should be among top seeds

    def test_project_opponents(self):
        standings = _enrich_standings()
        standings = project_seeds(standings)
        df = project_opponents(standings)
        assert "projectedOpponent" in df.columns
        # Teams with seeds 1-8 should have opponents
        playoff_teams = df[df["projectedSeed"] <= 8]
        assert playoff_teams["projectedOpponent"].notna().sum() > 0


class TestValidators:
    def test_valid_standings(self):
        ok, issues = validate_standings(_make_standings())
        assert ok, f"Issues: {issues}"

    def test_missing_column(self):
        df = _make_standings().drop(columns=["points"])
        ok, issues = validate_standings(df)
        assert not ok

    def test_playoff_odds_valid(self):
        ok, _ = validate_playoff_odds(75.0)
        assert ok

    def test_playoff_odds_invalid(self):
        ok, issues = validate_playoff_odds(150.0)
        assert not ok

    def test_projected_record_valid(self):
        ok, _ = validate_projected_record(40, 30, 12)
        assert ok

    def test_projected_record_over_82(self):
        ok, issues = validate_projected_record(50, 40, 10)
        assert not ok  # 100 > 82
