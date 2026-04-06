"""Safe numeric formatting helpers.

Every formatter handles int, float, None, NaN, and numpy numeric types
without raising exceptions.
"""

from typing import Union

import numpy as np


Numeric = Union[int, float, np.integer, np.floating, None]


def _safe_float(value: Numeric) -> float | None:
    """Coerce *value* to a plain Python float, returning None on failure."""
    if value is None:
        return None
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def fmt_signed_int(value: Numeric, fallback: str = "—") -> str:
    """Format as a signed integer, e.g. ``+12``, ``-3``, ``0``."""
    f = _safe_float(value)
    if f is None:
        return fallback
    return f"{int(round(f)):+d}"


def fmt_signed_float(value: Numeric, decimals: int = 1, fallback: str = "—") -> str:
    """Format as a signed float, e.g. ``+12.0``, ``-3.5``."""
    f = _safe_float(value)
    if f is None:
        return fallback
    return f"{f:+.{decimals}f}"


def fmt_pct(value: Numeric, decimals: int = 0, fallback: str = "—") -> str:
    """Format as percentage, e.g. ``72%``."""
    f = _safe_float(value)
    if f is None:
        return fallback
    return f"{f:.{decimals}f}%"


def fmt_prob(value: Numeric, decimals: int = 1, fallback: str = "—") -> str:
    """Format as probability bar label, e.g. ``72.3%``."""
    f = _safe_float(value)
    if f is None:
        return fallback
    return f"{f:.{decimals}f}%"


def fmt_number(value: Numeric, decimals: int = 0, fallback: str = "—") -> str:
    """Format as plain number, e.g. ``50``."""
    f = _safe_float(value)
    if f is None:
        return fallback
    return f"{f:.{decimals}f}"


def fmt_record(w: int, l: int, otl: int) -> str:
    """Format win-loss-OTL record string."""
    return f"{w}-{l}" if otl == 0 else f"{w}-{l}-{otl}"


def safe_format(fmt_str: str, value: Numeric, fallback: str = "—") -> str:
    """Apply *fmt_str* (e.g. ``'{:+.0f}'``) to *value* with fallback."""
    f = _safe_float(value)
    if f is None:
        return fallback
    try:
        return fmt_str.format(f)
    except (ValueError, TypeError):
        return fallback
