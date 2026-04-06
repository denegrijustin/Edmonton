"""Low-level data loading and utility functions for NHL API data."""

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import requests
import streamlit as st

from config.settings import TIMEOUT


@st.cache_data(ttl=3600, show_spinner=False)
def get_json(url: str) -> Dict[str, Any]:
    """Fetch JSON from *url* with caching and error handling."""
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        st.warning(f"API request failed ({url}): {exc}", icon="⚠️")
        return {}
    except Exception as exc:
        st.warning(f"Unexpected error fetching {url}: {exc}", icon="⚠️")
        return {}


def safe_get(obj: Any, path: List[Any], default=None):
    """Traverse nested dicts / lists along *path*, returning *default* on miss."""
    cur = obj
    try:
        for p in path:
            cur = cur[p]
        return cur
    except Exception:
        return default


def flatten_dict(obj: Any, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Recursively flatten nested dicts/lists into a single-level dict."""
    items: Dict[str, Any] = {}
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


def first_non_null(d: Dict[str, Any], keys: List[str], default=None):
    """Return the first non-None value among *keys* in *d*."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def parse_mmss(val: Any) -> float:
    """Parse ``'MM:SS'`` strings or numerics to float minutes."""
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
    """Compute z-scores for a numeric series."""
    s = pd.to_numeric(series, errors="coerce")
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - s.mean()) / std


def points_from_result(row: pd.Series) -> int:
    """Return standings points (2 = W, 1 = OTL, 0 = L)."""
    if row["result"] == "W":
        return 2
    if row["result"] == "OTL":
        return 1
    return 0
