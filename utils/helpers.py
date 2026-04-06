"""General-purpose helper functions."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def safe_get(obj: Any, path: list[Any], default: Any = None) -> Any:
    """Traverse nested dicts/lists safely."""
    cur = obj
    try:
        for p in path:
            cur = cur[p]
        return cur
    except Exception:
        return default


def flatten_dict(obj: Any, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten nested dicts/lists into dot-keyed dict."""
    items: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            items.update(flatten_dict(v, new_key, sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            items.update(flatten_dict(v, new_key, sep))
    else:
        items[parent_key] = obj
    return items


def first_non_null(d: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """Return first non-None value from *d* matching *keys*."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def parse_mmss(val: Any) -> float:
    """Parse MM:SS time strings to float minutes."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    if ":" in s:
        try:
            mm, ss = s.split(":")
            return int(mm) + int(ss) / 60
        except Exception:
            return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def zscore(series: pd.Series) -> pd.Series:
    """Standardize a series to z-scores (ddof=0)."""
    s = pd.to_numeric(series, errors="coerce")
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.mean()) / std


def format_record(wins: int, losses: int, otl: int = 0) -> str:
    """Format W-L-OTL record string."""
    if otl == 0:
        return f"{wins}-{losses}"
    return f"{wins}-{losses}-{otl}"


def points_from_result(result: str) -> int:
    """Return points earned from a result string."""
    if result == "W":
        return 2
    if result == "OTL":
        return 1
    return 0


def classify_zone(x: float, y: float) -> str:
    """Classify rink coordinates into offensive zones."""
    if pd.isna(x) or pd.isna(y):
        return "Unknown"
    ax = abs(x)
    ay = abs(y)
    if ax <= 20 and ay <= 10:
        return "Net Front"
    if ax <= 35 and ay <= 20:
        return "Slot"
    if ax <= 69 and ay <= 22:
        return "Circle / Inner Lane"
    if ax <= 89 and ay <= 42:
        return "Perimeter"
    return "Outer / Point"


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp *value* between *lo* and *hi*."""
    return max(lo, min(hi, value))
