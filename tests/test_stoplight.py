"""Unit tests for stoplight and UI utility functions."""

from __future__ import annotations

import pandas as pd
import pytest

from config.settings import SL_GREEN, SL_RED, SL_YELLOW
from config.teams import CONFERENCES, DIVISIONS, TEAMS, TEAM_LOGOS
from utils.stoplight import (
    sl_damage,
    sl_grade,
    sl_momentum,
    sl_odds,
    sl_result,
    stoplight,
    stoplight_html,
    stoplight_label,
)


class TestStoplight:
    def test_green(self):
        assert stoplight(80, 70, 50) == SL_GREEN

    def test_yellow(self):
        assert stoplight(60, 70, 50) == SL_YELLOW

    def test_red(self):
        assert stoplight(30, 70, 50) == SL_RED

    def test_inverted_green(self):
        assert stoplight(2.0, 3.0, 2.5, invert=True) == SL_GREEN

    def test_inverted_red(self):
        assert stoplight(4.0, 3.0, 2.5, invert=True) == SL_RED

    def test_nan(self):
        assert stoplight(float("nan"), 70, 50) == ""


class TestStoplightHtml:
    def test_returns_span(self):
        result = stoplight_html(80, 70, 50)
        assert "●" in result
        assert "#22c55e" in result  # green

    def test_red_html(self):
        result = stoplight_html(30, 70, 50)
        assert "#ef4444" in result


class TestStoplightLabel:
    def test_strong(self):
        assert stoplight_label(80, 70, 50) == "Strong"

    def test_neutral(self):
        assert stoplight_label(60, 70, 50) == "Neutral"

    def test_weak(self):
        assert stoplight_label(30, 70, 50) == "Weak"


class TestPreConfiguredStoplights:
    def test_sl_grade(self):
        assert sl_grade(80) == SL_GREEN
        assert sl_grade(60) == SL_YELLOW
        assert sl_grade(40) == SL_RED

    def test_sl_momentum(self):
        assert sl_momentum(60) == SL_GREEN
        assert sl_momentum(50) == SL_YELLOW
        assert sl_momentum(40) == SL_RED

    def test_sl_result(self):
        assert sl_result("W") == SL_GREEN
        assert sl_result("OTL") == SL_YELLOW
        assert sl_result("L") == SL_RED

    def test_sl_odds(self):
        assert sl_odds(80) == SL_GREEN
        assert sl_odds(50) == SL_YELLOW
        assert sl_odds(20) == SL_RED


class TestTeamConfig:
    def test_32_teams(self):
        assert len(TEAMS) >= 32

    def test_all_teams_have_logos(self):
        for abbrev in TEAMS:
            assert abbrev in TEAM_LOGOS
            assert TEAM_LOGOS[abbrev].startswith("https://")

    def test_conferences(self):
        assert "Eastern" in CONFERENCES
        assert "Western" in CONFERENCES
        assert len(CONFERENCES["Eastern"]) == 16
        assert len(CONFERENCES["Western"]) == 16

    def test_divisions(self):
        assert len(DIVISIONS) == 4
        for div, teams in DIVISIONS.items():
            assert len(teams) == 8

    def test_edm_in_pacific(self):
        assert "EDM" in DIVISIONS["Pacific"]
        assert TEAMS["EDM"]["conference"] == "Western"
