"""Tests for utils/formatters.py — safe numeric formatting helpers."""

import math

import numpy as np
import pytest

from utils.formatters import (
    fmt_number,
    fmt_pct,
    fmt_prob,
    fmt_record,
    fmt_signed_float,
    fmt_signed_int,
    safe_format,
)


# ── fmt_signed_int ────────────────────────────────────────────────────────────

class TestFmtSignedInt:
    def test_positive_int(self):
        assert fmt_signed_int(12) == "+12"

    def test_negative_int(self):
        assert fmt_signed_int(-3) == "-3"

    def test_zero(self):
        assert fmt_signed_int(0) == "+0"

    def test_positive_float(self):
        """Float values should be rounded to int for :+d display."""
        assert fmt_signed_int(12.7) == "+13"

    def test_negative_float(self):
        assert fmt_signed_int(-3.2) == "-3"

    def test_float_zero(self):
        assert fmt_signed_int(0.0) == "+0"

    def test_none(self):
        assert fmt_signed_int(None) == "—"

    def test_nan(self):
        assert fmt_signed_int(float("nan")) == "—"

    def test_numpy_int(self):
        assert fmt_signed_int(np.int64(42)) == "+42"

    def test_numpy_float(self):
        assert fmt_signed_int(np.float64(-5.0)) == "-5"

    def test_numpy_nan(self):
        assert fmt_signed_int(np.nan) == "—"

    def test_inf(self):
        assert fmt_signed_int(float("inf")) == "—"

    def test_custom_fallback(self):
        assert fmt_signed_int(None, fallback="N/A") == "N/A"


# ── fmt_signed_float ──────────────────────────────────────────────────────────

class TestFmtSignedFloat:
    def test_positive(self):
        assert fmt_signed_float(12.5) == "+12.5"

    def test_negative(self):
        assert fmt_signed_float(-3.1) == "-3.1"

    def test_zero(self):
        assert fmt_signed_float(0.0) == "+0.0"

    def test_none(self):
        assert fmt_signed_float(None) == "—"

    def test_nan(self):
        assert fmt_signed_float(float("nan")) == "—"

    def test_two_decimals(self):
        assert fmt_signed_float(12.567, decimals=2) == "+12.57"


# ── fmt_pct ───────────────────────────────────────────────────────────────────

class TestFmtPct:
    def test_integer_pct(self):
        assert fmt_pct(72) == "72%"

    def test_float_pct(self):
        assert fmt_pct(72.3, decimals=1) == "72.3%"

    def test_none(self):
        assert fmt_pct(None) == "—"

    def test_nan(self):
        assert fmt_pct(float("nan")) == "—"


# ── fmt_prob ──────────────────────────────────────────────────────────────────

class TestFmtProb:
    def test_basic(self):
        assert fmt_prob(72.3) == "72.3%"

    def test_none(self):
        assert fmt_prob(None) == "—"


# ── fmt_number ────────────────────────────────────────────────────────────────

class TestFmtNumber:
    def test_basic(self):
        assert fmt_number(50) == "50"

    def test_decimals(self):
        assert fmt_number(50.123, decimals=2) == "50.12"

    def test_none(self):
        assert fmt_number(None) == "—"


# ── fmt_record ────────────────────────────────────────────────────────────────

class TestFmtRecord:
    def test_no_otl(self):
        assert fmt_record(40, 30, 0) == "40-30"

    def test_with_otl(self):
        assert fmt_record(40, 30, 5) == "40-30-5"


# ── safe_format ───────────────────────────────────────────────────────────────

class TestSafeFormat:
    def test_signed_int_format(self):
        """This is the exact pattern that caused the original crash."""
        assert safe_format("{:+.0f}", 12.0) == "+12"
        assert safe_format("{:+.0f}", -3.0) == "-3"

    def test_float_format(self):
        assert safe_format("{:.2f}", 3.14159) == "3.14"

    def test_none_returns_fallback(self):
        assert safe_format("{:+d}", None) == "—"

    def test_nan_returns_fallback(self):
        assert safe_format("{:+d}", float("nan")) == "—"

    def test_numpy_types(self):
        assert safe_format("{:.0f}", np.int64(42)) == "42"
        assert safe_format("{:.0f}", np.float64(3.7)) == "4"
