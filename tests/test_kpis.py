"""Tests for UI KPI components — safe rendering with various value types."""

import numpy as np
import pytest

from ui.components import kpi_html, prob_bar_html, safe_kpi


class TestKpiHtml:
    def test_basic_rendering(self):
        html = kpi_html("Record", "40-30-5", "85 pts")
        assert "Record" in html
        assert "40-30-5" in html
        assert "85 pts" in html
        assert "kpi-card" in html

    def test_empty_sub(self):
        html = kpi_html("Test", "value")
        assert "kpi-sub" in html


class TestSafeKpi:
    """Test safe_kpi which wraps formatting + stoplight + kpi_html."""

    def test_signed_int_positive(self):
        html = safe_kpi("Goal Diff", 12, fmt="signed_int")
        assert "+12" in html

    def test_signed_int_negative(self):
        html = safe_kpi("Goal Diff", -3, fmt="signed_int")
        assert "-3" in html

    def test_signed_int_zero(self):
        html = safe_kpi("Goal Diff", 0, fmt="signed_int")
        assert "+0" in html

    def test_signed_int_float_value(self):
        """This was the original crash: float passed to :+d format."""
        html = safe_kpi("Goal Diff", 12.0, fmt="signed_int")
        assert "+12" in html

    def test_signed_int_negative_float(self):
        html = safe_kpi("Goal Diff", -3.7, fmt="signed_int")
        assert "-4" in html

    def test_signed_float(self):
        html = safe_kpi("GD/G", 1.5, fmt="signed_float")
        assert "+1.5" in html

    def test_pct(self):
        html = safe_kpi("Odds", 72.3, fmt="pct")
        assert "72%" in html

    def test_plain(self):
        html = safe_kpi("Momentum", 55.0, fmt="plain")
        assert "55" in html

    def test_none_value(self):
        html = safe_kpi("Goal Diff", None, fmt="signed_int")
        assert "—" in html

    def test_nan_value(self):
        html = safe_kpi("Goal Diff", float("nan"), fmt="signed_int")
        assert "—" in html

    def test_numpy_int(self):
        html = safe_kpi("Goal Diff", np.int64(42), fmt="signed_int")
        assert "+42" in html

    def test_numpy_float(self):
        html = safe_kpi("Goal Diff", np.float64(-5.0), fmt="signed_int")
        assert "-5" in html

    def test_stoplight_included(self):
        html = safe_kpi("Goal Diff", 12, fmt="signed_int", good=10, bad=-10)
        assert "🟢" in html

    def test_no_stoplight(self):
        html = safe_kpi("Goal Diff", 12, fmt="signed_int", show_stoplight=False)
        assert "🟢" not in html
        assert "+12" in html


class TestProbBarHtml:
    def test_basic(self):
        html = prob_bar_html("Win %", 65.5, "#3b82f6")
        assert "65.5%" in html

    def test_clamped_high(self):
        html = prob_bar_html("Over", 150.0)
        assert "100.0%" in html

    def test_clamped_low(self):
        html = prob_bar_html("Under", -10.0)
        assert "0.0%" in html

    def test_none_value(self):
        html = prob_bar_html("Test", None)
        assert "0.0%" in html

    def test_nan_value(self):
        html = prob_bar_html("Test", float("nan"))
        assert "0.0%" in html
