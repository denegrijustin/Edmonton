"""Tests for providers/moneypuck_provider.py."""

import pytest

from providers.moneypuck_provider import (
    _parse_predictions_html,
    get_all_playoff_odds,
    get_source_status,
    get_team_playoff_odds,
    map_team_name,
)
from utils.validators import validate_probability


class TestMapTeamName:
    def test_full_city_name(self):
        assert map_team_name("Edmonton") == "EDM"

    def test_abbreviation(self):
        assert map_team_name("EDM") == "EDM"

    def test_case_insensitive(self):
        assert map_team_name("edmonton") == "EDM"

    def test_unknown_team(self):
        assert map_team_name("Unknown City") is None

    def test_empty_string(self):
        assert map_team_name("") is None

    def test_all_major_teams(self):
        known = [
            "Anaheim", "Boston", "Buffalo", "Calgary", "Carolina",
            "Chicago", "Colorado", "Columbus", "Dallas", "Detroit",
            "Edmonton", "Florida", "Los Angeles", "Minnesota",
            "Montreal", "Nashville", "New Jersey", "NY Islanders",
            "NY Rangers", "Ottawa", "Philadelphia", "Pittsburgh",
            "San Jose", "Seattle", "St. Louis", "Tampa Bay",
            "Toronto", "Utah", "Vancouver", "Vegas",
            "Washington", "Winnipeg",
        ]
        for city in known:
            result = map_team_name(city)
            assert result is not None, f"Failed to map {city}"
            assert len(result) == 3


class TestParsePredictionsHtml:
    def test_valid_table(self):
        html = """
        <table>
        <tr><td>Edmonton</td><td>85.2%</td><td>5.1%</td><td>2.3%</td></tr>
        <tr><td>Calgary</td><td>45.0%</td><td>1.0%</td><td>0.5%</td></tr>
        </table>
        """
        rows = _parse_predictions_html(html)
        assert len(rows) == 2
        assert rows[0]["team"] == "EDM"
        assert rows[0]["playoff_pct"] == 85.2
        assert rows[1]["team"] == "CGY"

    def test_malformed_row_skipped(self):
        html = """
        <table>
        <tr><td>Edmonton</td><td>85.2%</td></tr>
        <tr><td>Bogus City</td><td>50%</td></tr>
        <tr><td></td><td>10%</td></tr>
        </table>
        """
        rows = _parse_predictions_html(html)
        assert len(rows) == 1
        assert rows[0]["team"] == "EDM"

    def test_empty_html(self):
        rows = _parse_predictions_html("")
        assert rows == []

    def test_no_table_rows(self):
        rows = _parse_predictions_html("<html><body>No data</body></html>")
        assert rows == []

    def test_probability_validation(self):
        html = """
        <table>
        <tr><td>Edmonton</td><td>85.2%</td></tr>
        </table>
        """
        rows = _parse_predictions_html(html)
        for row in rows:
            pct = row["playoff_pct"]
            assert 0 <= pct <= 100


class TestValidateProbability:
    def test_valid(self):
        assert validate_probability(50.0) == 50.0

    def test_clamp_high(self):
        assert validate_probability(150.0) == 100.0

    def test_clamp_low(self):
        assert validate_probability(-10.0) == 0.0

    def test_none(self):
        assert validate_probability(None) is None

    def test_nan(self):
        assert validate_probability(float("nan")) is None

    def test_string(self):
        assert validate_probability("not a number") is None


class TestSourceStatus:
    def test_status_dict(self):
        status = get_source_status()
        assert "source" in status
        assert status["source"] == "MoneyPuck"
        assert "success" in status
        assert "timestamp" in status


class TestFallbackBehavior:
    def test_unknown_team_returns_none(self):
        result = get_team_playoff_odds("ZZZZ")
        assert result is None

    def test_all_odds_returns_dict(self):
        result = get_all_playoff_odds()
        assert isinstance(result, dict)
