"""Data validation helpers for numeric fields and team abbreviations."""

from typing import Any, Optional

import numpy as np
import pandas as pd


def safe_numeric(value: Any, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on failure or NaN."""
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Coerce *value* to int, returning *default* on failure."""
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return int(round(f))
    except (TypeError, ValueError):
        return default


def validate_probability(value: Any) -> Optional[float]:
    """Return *value* clamped to [0, 100] as a float, or None."""
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return max(0.0, min(100.0, f))
    except (TypeError, ValueError):
        return None


def validate_team_abbrev(abbrev: Any, known_teams: set) -> Optional[str]:
    """Return *abbrev* as string if it is in *known_teams*, else None."""
    if abbrev is None:
        return None
    s = str(abbrev).strip().upper()
    if s in known_teams:
        return s
    return None
