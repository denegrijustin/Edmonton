"""Tests for services/mode_state.py — fail-safe season mode detection.

All tests are fully offline — no real NHL API calls are made.
"""

import unittest.mock as mock

import pandas as pd
import pytest

from services.mode_state import AppMode, detect_app_mode, get_safe_mode, update_mode_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_standings(n_teams=16, conference="Western", gp=70):
    """Build a minimal standings DataFrame."""
    rows = []
    for i in range(n_teams):
        rows.append({
            "teamAbbrev": f"T{i:02d}",
            "teamName": f"Team {i}",
            "conference": conference,
            "division": "Pacific" if i < 8 else "Central",
            "gamesPlayed": gp,
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


# ---------------------------------------------------------------------------
# AppMode enum
# ---------------------------------------------------------------------------

class TestAppModeEnum:
    def test_regular_season_value(self):
        assert AppMode.REGULAR_SEASON.value == "REGULAR_SEASON"

    def test_playoff_race_value(self):
        assert AppMode.PLAYOFF_RACE.value == "PLAYOFF_RACE"

    def test_playoffs_value(self):
        assert AppMode.PLAYOFFS.value == "PLAYOFFS"

    def test_offseason_value(self):
        assert AppMode.OFFSEASON.value == "OFFSEASON"

    def test_safe_fallback_value(self):
        assert AppMode.SAFE_FALLBACK.value == "SAFE_FALLBACK"

    def test_member_count(self):
        assert len(AppMode) == 5


# ---------------------------------------------------------------------------
# detect_app_mode
# ---------------------------------------------------------------------------

class TestDetectAppMode:
    @mock.patch("services.mode_state.is_playoff_active", return_value=False)
    def test_regular_season_under_82_gp(self, _mock):
        """Teams with < 76 GP → REGULAR_SEASON."""
        stdf = _make_standings(gp=65)
        assert detect_app_mode("20252026", stdf) == AppMode.REGULAR_SEASON

    @mock.patch("services.mode_state.is_playoff_active", return_value=False)
    def test_playoff_race_over_75_gp(self, _mock):
        """Max GP > 75 but min GP < 82 → PLAYOFF_RACE."""
        stdf = _make_standings(gp=78)
        assert detect_app_mode("20252026", stdf) == AppMode.PLAYOFF_RACE

    @mock.patch("services.mode_state.is_playoff_active", return_value=False)
    def test_offseason_all_82_gp(self, _mock):
        """All teams at 82 GP → OFFSEASON."""
        stdf = _make_standings(gp=82)
        assert detect_app_mode("20252026", stdf) == AppMode.OFFSEASON

    @mock.patch("services.mode_state.is_playoff_active", return_value=True)
    def test_playoffs_active(self, _mock):
        """is_playoff_active=True → PLAYOFFS regardless of standings."""
        stdf = _make_standings(gp=82)
        assert detect_app_mode("20252026", stdf) == AppMode.PLAYOFFS

    @mock.patch("services.mode_state.is_playoff_active", return_value=False)
    def test_empty_standings_returns_safe_fallback(self, _mock):
        assert detect_app_mode("20252026", pd.DataFrame()) == AppMode.SAFE_FALLBACK

    @mock.patch("services.mode_state.is_playoff_active", side_effect=Exception("boom"))
    def test_exception_returns_safe_fallback(self, _mock):
        stdf = _make_standings(gp=70)
        assert detect_app_mode("20252026", stdf) == AppMode.SAFE_FALLBACK


# ---------------------------------------------------------------------------
# get_safe_mode
# ---------------------------------------------------------------------------

class TestGetSafeMode:
    def test_returns_stored_mode(self):
        session = {"last_confirmed_app_mode": AppMode.PLAYOFFS}
        assert get_safe_mode(session) == AppMode.PLAYOFFS

    def test_returns_safe_fallback_when_nothing_stored(self):
        assert get_safe_mode({}) == AppMode.SAFE_FALLBACK

    def test_returns_safe_fallback_for_non_enum_value(self):
        session = {"last_confirmed_app_mode": "PLAYOFFS"}
        assert get_safe_mode(session) == AppMode.SAFE_FALLBACK


# ---------------------------------------------------------------------------
# update_mode_state
# ---------------------------------------------------------------------------

class TestUpdateModeState:
    def test_stores_real_mode(self):
        session = {}
        update_mode_state(session, AppMode.REGULAR_SEASON)
        assert session["last_confirmed_app_mode"] == AppMode.REGULAR_SEASON

    def test_overwrites_existing_with_real_mode(self):
        session = {"last_confirmed_app_mode": AppMode.REGULAR_SEASON}
        update_mode_state(session, AppMode.PLAYOFFS)
        assert session["last_confirmed_app_mode"] == AppMode.PLAYOFFS

    def test_safe_fallback_does_not_overwrite_existing(self):
        session = {"last_confirmed_app_mode": AppMode.REGULAR_SEASON}
        update_mode_state(session, AppMode.SAFE_FALLBACK)
        assert session["last_confirmed_app_mode"] == AppMode.REGULAR_SEASON

    def test_safe_fallback_stored_when_no_prior(self):
        session = {}
        update_mode_state(session, AppMode.SAFE_FALLBACK)
        assert session["last_confirmed_app_mode"] == AppMode.SAFE_FALLBACK
