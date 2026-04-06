"""Stoplight visual helpers — green / yellow / red logic."""

from __future__ import annotations

import pandas as pd

from config.settings import SL_GREEN, SL_YELLOW, SL_RED


def stoplight(value: float, green_thresh: float, yellow_thresh: float, *, invert: bool = False) -> str:
    """Return a CSS style string for stoplight coloring.

    When *invert* is False (default), higher values are green.
    When *invert* is True, lower values are green (e.g. goals against).
    """
    if pd.isna(value):
        return ""
    if invert:
        if value <= yellow_thresh:
            return SL_GREEN
        if value <= green_thresh:
            return SL_YELLOW
        return SL_RED
    else:
        if value >= green_thresh:
            return SL_GREEN
        if value >= yellow_thresh:
            return SL_YELLOW
        return SL_RED


def stoplight_html(value: float, green_thresh: float, yellow_thresh: float, *, invert: bool = False) -> str:
    """Return an inline-styled span with stoplight dot."""
    if pd.isna(value):
        return "⚪"
    if invert:
        if value <= yellow_thresh:
            color = "#22c55e"
        elif value <= green_thresh:
            color = "#eab308"
        else:
            color = "#ef4444"
    else:
        if value >= green_thresh:
            color = "#22c55e"
        elif value >= yellow_thresh:
            color = "#eab308"
        else:
            color = "#ef4444"
    return f'<span style="color:{color}; font-size:1.4em;">●</span>'


def stoplight_label(value: float, green_thresh: float, yellow_thresh: float, *, invert: bool = False) -> str:
    """Return a text label: Strong / Neutral / Weak."""
    if pd.isna(value):
        return "N/A"
    if invert:
        if value <= yellow_thresh:
            return "Strong"
        if value <= green_thresh:
            return "Neutral"
        return "Weak"
    else:
        if value >= green_thresh:
            return "Strong"
        if value >= yellow_thresh:
            return "Neutral"
        return "Weak"


# Pre-configured stoplight stylers for pandas
def sl_grade(val: float) -> str:
    return stoplight(val, 70, 50)


def sl_momentum(val: float) -> str:
    return stoplight(val, 55, 45)


def sl_result(val: str) -> str:
    if val == "W":
        return SL_GREEN
    if val == "OTL":
        return SL_YELLOW
    if val == "L":
        return SL_RED
    return ""


def sl_odds(val: float) -> str:
    return stoplight(val, 70, 40)


def sl_damage(val: float) -> str:
    return stoplight(val, 60, 45, invert=True)
