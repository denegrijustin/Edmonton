"""Unit tests for feature engineering modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from features.momentum import compute_momentum
from features.player_ratings import compute_player_ratings
from features.team_features import compute_team_features
from utils.helpers import (
    classify_zone,
    clamp,
    flatten_dict,
    format_record,
    parse_mmss,
    points_from_result,
    safe_get,
    zscore,
)


# ========== Helpers ==========
class TestSafeGet:
    def test_nested_access(self):
        d = {"a": {"b": {"c": 42}}}
        assert safe_get(d, ["a", "b", "c"]) == 42

    def test_missing_key(self):
        assert safe_get({"a": 1}, ["b"], default="x") == "x"

    def test_list_index(self):
        d = {"items": [10, 20, 30]}
        assert safe_get(d, ["items", 1]) == 20


class TestFlattenDict:
    def test_simple(self):
        result = flatten_dict({"a": 1, "b": {"c": 2}})
        assert result == {"a": 1, "b.c": 2}

    def test_with_list(self):
        result = flatten_dict({"items": [1, 2]})
        assert result == {"items.0": 1, "items.1": 2}


class TestParseMmss:
    def test_mmss_string(self):
        assert parse_mmss("15:30") == 15.5

    def test_numeric(self):
        assert parse_mmss(20.0) == 20.0

    def test_none(self):
        assert np.isnan(parse_mmss(None))


class TestFormatRecord:
    def test_no_otl(self):
        assert format_record(30, 20) == "30-20"

    def test_with_otl(self):
        assert format_record(30, 20, 5) == "30-20-5"


class TestPointsFromResult:
    def test_win(self):
        assert points_from_result("W") == 2

    def test_otl(self):
        assert points_from_result("OTL") == 1

    def test_loss(self):
        assert points_from_result("L") == 0


class TestClassifyZone:
    def test_net_front(self):
        assert classify_zone(10, 5) == "Net Front"

    def test_slot(self):
        assert classify_zone(25, 15) == "Slot"

    def test_perimeter(self):
        assert classify_zone(75, 30) == "Perimeter"

    def test_nan(self):
        assert classify_zone(float("nan"), 0) == "Unknown"


class TestClamp:
    def test_in_range(self):
        assert clamp(50) == 50

    def test_below(self):
        assert clamp(-10) == 0

    def test_above(self):
        assert clamp(150) == 100


class TestZscore:
    def test_basic(self):
        s = pd.Series([1, 2, 3, 4, 5])
        z = zscore(s)
        assert abs(z.mean()) < 1e-10
        assert abs(z.std(ddof=0) - 1) < 1e-10

    def test_constant(self):
        s = pd.Series([5, 5, 5])
        z = zscore(s)
        assert (z == 0).all()


# ========== Momentum ==========
class TestMomentum:
    def _make_team_games(self, n: int = 20) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        results = rng.choice(["W", "L", "OTL"], n, p=[0.5, 0.35, 0.15])
        return pd.DataFrame({
            "gameDate": pd.date_range("2025-10-10", periods=n),
            "gameId": range(1, n + 1),
            "teamScore": rng.integers(1, 6, n),
            "oppScore": rng.integers(0, 5, n),
            "goalDiff": rng.integers(-3, 4, n),
            "shotDiff": rng.integers(-10, 11, n).astype(float),
            "result": results,
        })

    def test_adds_momentum_columns(self):
        df = compute_momentum(self._make_team_games())
        assert "momentumScore" in df.columns
        assert "momentumDirection" in df.columns
        assert "momentumSupported" in df.columns

    def test_momentum_range(self):
        df = compute_momentum(self._make_team_games())
        assert df["momentumScore"].min() >= 0
        assert df["momentumScore"].max() <= 100

    def test_empty(self):
        df = compute_momentum(pd.DataFrame())
        assert df.empty

    def test_direction_values(self):
        df = compute_momentum(self._make_team_games())
        valid = {"Hot", "Steady", "Slipping", "Cold"}
        assert set(df["momentumDirection"].unique()).issubset(valid)


# ========== Player Ratings ==========
class TestPlayerRatings:
    def _make_player_games(self) -> pd.DataFrame:
        n = 30
        return pd.DataFrame({
            "gameDate": pd.date_range("2025-10-10", periods=n).tolist() * 2,
            "gameId": list(range(1, n + 1)) * 2,
            "playerName": ["Player A"] * n + ["Player B"] * n,
            "position": ["F"] * n + ["D"] * n,
            "goals": np.random.randint(0, 3, n * 2),
            "assists": np.random.randint(0, 3, n * 2),
            "points": np.random.randint(0, 4, n * 2),
            "plusMinus": np.random.randint(-2, 3, n * 2),
            "shots": np.random.randint(0, 7, n * 2),
            "hits": np.random.randint(0, 5, n * 2),
            "blockedShots": np.random.randint(0, 4, n * 2),
            "giveaways": np.random.randint(0, 3, n * 2),
            "takeaways": np.random.randint(0, 3, n * 2),
            "faceoffWins": np.random.randint(0, 10, n * 2),
            "faceoffTaken": np.random.randint(0, 15, n * 2),
            "toi_min": np.random.uniform(10, 25, n * 2),
            "saves": [0] * (n * 2),
            "goalsAgainst": [0] * (n * 2),
            "shotsAgainst": [0] * (n * 2),
            "pim": np.random.randint(0, 5, n * 2),
        })

    def test_adds_rating_columns(self):
        df = compute_player_ratings(self._make_player_games())
        assert "gameGrade" in df.columns
        assert "rollingGrade" in df.columns
        assert "consistencyScore" in df.columns
        assert "trendFlag" in df.columns

    def test_grade_range(self):
        df = compute_player_ratings(self._make_player_games())
        assert df["gameGrade"].min() >= 20
        assert df["gameGrade"].max() <= 99

    def test_trend_flags(self):
        df = compute_player_ratings(self._make_player_games())
        valid = {"Heating Up", "Stable", "Cooling Off"}
        assert set(df["trendFlag"].unique()).issubset(valid)


# ========== Team Features ==========
class TestTeamFeatures:
    def _make_standings(self) -> pd.DataFrame:
        return pd.DataFrame({
            "teamAbbrev": ["EDM", "CGY", "VAN", "LAK"],
            "teamName": ["Edmonton Oilers", "Calgary Flames", "Vancouver Canucks", "Los Angeles Kings"],
            "conference": ["Western", "Western", "Western", "Western"],
            "division": ["Pacific", "Pacific", "Pacific", "Pacific"],
            "gamesPlayed": [60, 60, 60, 60],
            "points": [80, 75, 70, 65],
            "wins": [38, 35, 32, 30],
            "losses": [18, 20, 23, 25],
            "otLosses": [4, 5, 5, 5],
            "regulationWins": [30, 28, 26, 24],
            "goalDifferential": [30, 15, 5, -10],
            "goalsFor": [210, 195, 180, 170],
            "goalsAgainst": [180, 180, 175, 180],
            "pointPctg": [0.667, 0.625, 0.583, 0.542],
            "conferenceSequence": [1, 3, 5, 7],
            "divisionSequence": [1, 2, 3, 4],
            "wildcardSequence": [0, 0, 1, 2],
            "homeWins": [20, 18, 16, 15],
            "homeLosses": [8, 10, 12, 13],
            "homeOtLosses": [2, 2, 2, 2],
            "roadWins": [18, 17, 16, 15],
            "roadLosses": [10, 10, 11, 12],
            "roadOtLosses": [2, 3, 3, 3],
            "l10Wins": [7, 6, 5, 4],
            "l10Losses": [2, 3, 4, 5],
            "l10OtLosses": [1, 1, 1, 1],
            "streakCode": ["W", "L", "W", "L"],
            "streakCount": [3, 1, 2, 2],
        })

    def test_projected_points(self):
        df = compute_team_features(self._make_standings())
        assert "projectedPoints" in df.columns
        assert "projectedRecord" in df.columns
        # EDM with most points should have highest projected
        edm = df[df["teamAbbrev"] == "EDM"].iloc[0]
        lak = df[df["teamAbbrev"] == "LAK"].iloc[0]
        assert edm["projectedPoints"] > lak["projectedPoints"]

    def test_remaining_games(self):
        df = compute_team_features(self._make_standings())
        assert (df["remainingGames"] == 22).all()

    def test_projected_record_sum(self):
        df = compute_team_features(self._make_standings())
        for _, row in df.iterrows():
            total = row["projectedWins"] + row["projectedLosses"] + row["projectedOTL"]
            assert total <= 82, f"Projected total {total} > 82 for {row['teamAbbrev']}"
