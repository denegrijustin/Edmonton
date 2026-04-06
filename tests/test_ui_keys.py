"""Tests for utils/streamlit_keys.py — unique Streamlit key generation."""

import pytest

from utils.streamlit_keys import mk_key, _slug


class TestSlug:
    def test_lowercase(self):
        assert _slug("Trends") == "trends"

    def test_spaces_to_underscores(self):
        assert _slug("rolling 5") == "rolling_5"

    def test_special_chars(self):
        assert _slug("goal-diff (season)") == "goal_diff_season"

    def test_already_slug(self):
        assert _slug("goal_diff") == "goal_diff"

    def test_strips_leading_trailing(self):
        assert _slug("__hello__") == "hello"

    def test_numeric(self):
        assert _slug(5) == "5"


class TestMkKey:
    def test_basic_two_parts(self):
        key = mk_key("trends", "chart")
        assert key == "trends__chart"

    def test_three_parts(self):
        key = mk_key("trends", "chart", "rolling_5")
        assert key == "trends__chart__rolling_5"

    def test_detail_slugified(self):
        key = mk_key("trends", "chart", "Rolling 5-Game")
        assert key == "trends__chart__rolling_5_game"

    def test_empty_detail_omitted(self):
        key = mk_key("overview", "dataframe", "")
        assert key == "overview__dataframe"

    def test_deterministic(self):
        assert mk_key("trends", "chart", "goal_diff") == mk_key("trends", "chart", "goal_diff")

    def test_different_pages_differ(self):
        k1 = mk_key("trends", "chart", "goal_diff")
        k2 = mk_key("overview", "chart", "goal_diff")
        assert k1 != k2

    def test_different_details_differ(self):
        k1 = mk_key("trends", "chart", "rolling_5")
        k2 = mk_key("trends", "chart", "rolling_10")
        assert k1 != k2

    def test_team_in_detail(self):
        k1 = mk_key("simulate", "chart", "histogram_EDM_CGY")
        k2 = mk_key("simulate", "chart", "histogram_CGY_EDM")
        assert k1 != k2

    def test_no_duplicate_for_overview_charts(self):
        """Regression: overview goal_diff and trends goal_diff must differ."""
        k1 = mk_key("overview", "chart", "goal_diff")
        k2 = mk_key("trends", "chart", "goal_diff")
        assert k1 != k2

    def test_no_duplicate_rolling_windows(self):
        """Regression: two rolling-trend charts in trends tab must differ."""
        k1 = mk_key("trends", "chart", "rolling_5")
        k2 = mk_key("trends", "chart", "rolling_10")
        assert k1 != k2

    def test_all_ui_keys_are_unique(self):
        """Ensure all keys used across UI files are globally distinct."""
        keys = [
            mk_key("trends", "chart", "rolling_5"),
            mk_key("trends", "chart", "rolling_10"),
            mk_key("trends", "chart", "goal_diff"),
            mk_key("trends", "chart", "points_path"),
            mk_key("trends", "dataframe", "game_log"),
            mk_key("overview", "chart", "goal_diff"),
            mk_key("overview", "chart", "momentum"),
            mk_key("simulate", "chart", "histogram_EDM_CGY"),
        ]
        assert len(keys) == len(set(keys)), "Duplicate keys detected in UI key inventory"
