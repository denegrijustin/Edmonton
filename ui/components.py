"""Reusable UI components — KPI cards, logo cards, probability bars, etc.

All rendering helpers use safe formatting so they never crash on float,
int, None, NaN, or numpy numeric types.
"""

from typing import Union

import numpy as np

from utils.formatters import Numeric, _safe_float, fmt_number, fmt_pct, fmt_signed_int
from utils.logos import logo_url
from utils.stoplights import stoplight


# ── KPI card ──────────────────────────────────────────────────────────────────

def kpi_html(label: str, value: str, sub: str = "") -> str:
    """Render a styled KPI card as HTML."""
    return (
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div>"
        f"<div class='kpi-sub'>{sub}</div>"
        f"</div>"
    )


def safe_kpi(
    label: str,
    value: Numeric,
    fmt: str = "plain",
    sub: str = "",
    good: float = 70,
    bad: float = 45,
    higher_is_better: bool = True,
    show_stoplight: bool = True,
) -> str:
    """Build a KPI card with safe formatting and optional stoplight.

    *fmt* can be: ``"signed_int"``, ``"signed_float"``, ``"pct"``, ``"plain"``.
    """
    sl = stoplight(value, good, bad, higher_is_better) if show_stoplight else ""

    f = _safe_float(value)
    if f is None:
        formatted = "—"
    elif fmt == "signed_int":
        formatted = f"{int(round(f)):+d}"
    elif fmt == "signed_float":
        formatted = f"{f:+.1f}"
    elif fmt == "pct":
        formatted = f"{f:.0f}%"
    else:
        formatted = f"{f:.0f}"

    display = f"{sl} {formatted}".strip() if sl else formatted
    return kpi_html(label, display, sub)


# ── Logo card ─────────────────────────────────────────────────────────────────

def logo_card_html(abbrev: str, label: str, sublabel: str = "") -> str:
    url = logo_url(abbrev)
    return (
        f"<div style='text-align:center;padding:10px 8px;background:#f8fafc;"
        f"border-radius:12px;border:1px solid #e2e8f0;min-width:80px;'>"
        f"<img src='{url}' width='52' height='52' style='object-fit:contain;'/>"
        f"<div style='font-weight:700;font-size:0.85rem;margin-top:4px;'>{label}</div>"
        f"<div style='font-size:0.75rem;color:#64748b;'>{sublabel}</div>"
        f"</div>"
    )


# ── Probability bar ───────────────────────────────────────────────────────────

def prob_bar_html(label: str, pct: float, color: str = "#3b82f6") -> str:
    f = _safe_float(pct)
    pct_c = max(0.0, min(100.0, f)) if f is not None else 0.0
    return (
        f"<div style='margin-bottom:4px;'>"
        f"<div style='font-size:0.82rem;font-weight:600;margin-bottom:1px;'>{label}</div>"
        f"<div class='prob-bar-wrap'>"
        f"<div class='prob-bar-fill' style='width:{pct_c:.0f}%;background:{color};'>"
        f"{pct_c:.1f}%</div></div></div>"
    )


# ── Result card ───────────────────────────────────────────────────────────────

def result_card_html(abbrev: str, result: str, score: str, sub: str) -> str:
    color = "#22c55e" if result == "W" else "#ef4444" if result == "L" else "#f59e0b"
    url = logo_url(abbrev)
    return (
        f"<div style='text-align:center;padding:8px;background:#f8fafc;"
        f"border-radius:12px;border:2px solid {color};'>"
        f"<img src='{url}' width='42' height='42' style='object-fit:contain;'/>"
        f"<div style='font-weight:800;font-size:1.05rem;color:{color};'>{result}</div>"
        f"<div style='font-size:0.82rem;font-weight:600;'>{score}</div>"
        f"<div style='font-size:0.72rem;color:#64748b;'>{sub}</div>"
        f"</div>"
    )


# ── Upcoming card ─────────────────────────────────────────────────────────────

def upcoming_card_html(abbrev: str, sub1: str, sub2: str) -> str:
    url = logo_url(abbrev)
    return (
        f"<div style='text-align:center;padding:8px;background:#f8fafc;"
        f"border-radius:12px;border:1px solid #e2e8f0;'>"
        f"<img src='{url}' width='42' height='42' style='object-fit:contain;'/>"
        f"<div style='font-weight:700;font-size:0.85rem;margin-top:4px;'>{abbrev}</div>"
        f"<div style='font-size:0.75rem;color:#64748b;'>{sub1}</div>"
        f"<div style='font-size:0.72rem;color:#94a3b8;'>{sub2}</div>"
        f"</div>"
    )
