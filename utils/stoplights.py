"""Stoplight indicator helpers — emoji and DataFrame style functions."""

from typing import Union

import numpy as np
import pandas as pd


Numeric = Union[int, float, np.integer, np.floating, None]


def stoplight(
    value: Numeric,
    good_threshold: float,
    bad_threshold: float,
    higher_is_better: bool = True,
) -> str:
    """Return 🟢 / 🟡 / 🔴 / ⚪ based on threshold comparison."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "⚪"
    if higher_is_better:
        if v >= good_threshold:
            return "🟢"
        elif v >= bad_threshold:
            return "🟡"
        else:
            return "🔴"
    else:
        if v <= good_threshold:
            return "🟢"
        elif v <= bad_threshold:
            return "🟡"
        else:
            return "🔴"


# ── DataFrame cell style helpers ──────────────────────────────────────────────

def sl_grade(val: float) -> str:
    if pd.isna(val):
        return ""
    if val >= 70:
        return "background-color:#dcfce7;color:#166534"
    if val >= 50:
        return "background-color:#fef9c3;color:#713f12"
    return "background-color:#fee2e2;color:#991b1b"


def sl_momentum(val: float) -> str:
    if pd.isna(val):
        return ""
    if val > 55:
        return "background-color:#dcfce7;color:#166534"
    if val >= 45:
        return "background-color:#fef9c3;color:#713f12"
    return "background-color:#fee2e2;color:#991b1b"


def sl_result(val: str) -> str:
    if val == "W":
        return "background-color:#dcfce7;color:#166534"
    if val == "OTL":
        return "background-color:#fef9c3;color:#713f12"
    if val == "L":
        return "background-color:#fee2e2;color:#991b1b"
    return ""
