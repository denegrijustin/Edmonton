"""Standings view — division / conference / wildcard with logo-first rows.

Visual playoff-status indicators and recent-form heat map column.
"""

from typing import Any, Dict

import pandas as pd
import streamlit as st

from ui.components import kpi_html
from utils.formatters import fmt_number, fmt_record, fmt_signed_int
from utils.logos import logo_url
from utils.stoplights import sl_grade, sl_momentum
from utils.streamlit_keys import mk_key


# ── Helpers ───────────────────────────────────────────────────────────────────

_STATUS_COLORS = {
    "Playoff": ("#dcfce7", "#166534", "🟢"),
    "Wildcard": ("#dbeafe", "#1e40af", "🔵"),
    "Bubble": ("#fef9c3", "#713f12", "🟡"),
    "Eliminated": ("#fee2e2", "#991b1b", "🔴"),
    "Unknown": ("#f1f5f9", "#64748b", "⚪"),
}


def _playoff_status(row: pd.Series, wc_cutoff: int) -> str:
    """Classify a team's playoff status from standings row."""
    pts = row.get("points", 0)
    gp = row.get("gamesPlayed", 0)
    elim = row.get("clinchIndicator", "")
    rank = row.get("wildcardSequence", row.get("conferenceSequence", 99))

    if isinstance(elim, str) and elim.lower() in ("e", "eliminated"):
        return "Eliminated"
    try:
        rank = int(rank)
    except (TypeError, ValueError):
        rank = 99
    if rank <= 3:
        return "Playoff"
    if rank <= 8:
        return "Wildcard"
    try:
        pts = int(pts)
    except (TypeError, ValueError):
        pts = 0
    if pts >= wc_cutoff - 6:
        return "Bubble"
    return "Eliminated"


def _form_cells_html(l10w: int, l10l: int, l10otl: int) -> str:
    """Compact L10 heat bar: green portion for W, yellow for OTL, red for L."""
    total = max(l10w + l10l + l10otl, 1)
    wp = int(l10w / total * 100)
    op = int(l10otl / total * 100)
    lp = 100 - wp - op
    return (
        f"<div style='display:flex;height:14px;border-radius:4px;overflow:hidden;"
        f"width:80px;'>"
        f"<div style='width:{wp}%;background:#22c55e;'></div>"
        f"<div style='width:{op}%;background:#eab308;'></div>"
        f"<div style='width:{lp}%;background:#ef4444;'></div>"
        f"</div>"
    )


def _render_standings_table(
    df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    wc_cutoff: int,
    view_label: str,
) -> None:
    """Render a logo-first standings table as HTML."""
    if df.empty:
        st.info("No standings data available.")
        return

    rows_html = []
    for _, row in df.iterrows():
        abbrev = row.get("teamAbbrev", row.get("teamAbbrev.value", ""))
        if not abbrev:
            continue
        name = row.get("teamName", row.get("teamName.default", abbrev))
        wins = row.get("wins", 0)
        losses = row.get("losses", 0)
        otl = row.get("otLosses", row.get("otl", 0))
        pts = row.get("points", 0)
        gp = row.get("gamesPlayed", 0)
        gd = row.get("goalDifferential", row.get("goalFor", 0) - row.get("goalAgainst", 0))
        rw = row.get("regulationWins", "")

        m = team_metrics_dict.get(abbrev, {})
        l10w = m.get("l10W", 0)
        l10l = m.get("l10L", 0)
        l10otl = m.get("l10OTL", 0)

        status = _playoff_status(row, wc_cutoff)
        bg, fg, icon = _STATUS_COLORS.get(status, _STATUS_COLORS["Unknown"])

        logo = logo_url(abbrev)
        form_bar = _form_cells_html(l10w, l10l, l10otl)

        rows_html.append(
            f"<tr style='border-bottom:1px solid #e2e8f0;'>"
            f"<td style='padding:6px;'>"
            f"  <span style='background:{bg};color:{fg};padding:2px 6px;"
            f"  border-radius:4px;font-size:0.75rem;font-weight:600;'>"
            f"  {icon} {status}</span>"
            f"</td>"
            f"<td style='padding:6px;'>"
            f"  <img src='{logo}' width='28' height='28' "
            f"  style='vertical-align:middle;margin-right:6px;'/>"
            f"  <span style='font-weight:600;'>{abbrev}</span>"
            f"</td>"
            f"<td style='padding:6px;text-align:center;'>{gp}</td>"
            f"<td style='padding:6px;text-align:center;'>{fmt_record(wins, losses, otl)}</td>"
            f"<td style='padding:6px;text-align:center;font-weight:700;'>{pts}</td>"
            f"<td style='padding:6px;text-align:center;'>{fmt_signed_int(gd)}</td>"
            f"<td style='padding:6px;text-align:center;'>{rw}</td>"
            f"<td style='padding:6px;'>{form_bar}</td>"
            f"</tr>"
        )

    header = (
        "<thead><tr style='background:#f8fafc;border-bottom:2px solid #cbd5e1;'>"
        "<th style='padding:6px;text-align:left;'>Status</th>"
        "<th style='padding:6px;text-align:left;'>Team</th>"
        "<th style='padding:6px;text-align:center;'>GP</th>"
        "<th style='padding:6px;text-align:center;'>Record</th>"
        "<th style='padding:6px;text-align:center;'>PTS</th>"
        "<th style='padding:6px;text-align:center;'>GD</th>"
        "<th style='padding:6px;text-align:center;'>RW</th>"
        "<th style='padding:6px;text-align:left;'>L10 Form</th>"
        "</tr></thead>"
    )
    table = (
        f"<table style='width:100%;border-collapse:collapse;font-size:0.88rem;'>"
        f"{header}<tbody>{''.join(rows_html)}</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)


def _wildcard_cutoff(standings_df: pd.DataFrame, conference: str) -> int:
    """Determine the approximate wildcard cutoff points for a conference."""
    if standings_df.empty:
        return 80
    conf_col = None
    for c in ("conferenceName", "conferenceAbbrev", "conference"):
        if c in standings_df.columns:
            conf_col = c
            break
    if conf_col is None:
        return 80
    conf_df = standings_df[standings_df[conf_col].str.contains(conference, case=False, na=False)]
    if conf_df.empty:
        return 80
    pts_sorted = conf_df["points"].sort_values(ascending=False)
    if len(pts_sorted) >= 8:
        return int(pts_sorted.iloc[7])
    return int(pts_sorted.iloc[-1]) if len(pts_sorted) else 80


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    selected_team: str = "",
    **kwargs: Any,
) -> None:
    """Render standings with division / conference / wildcard toggle."""
    if standings_df is None or standings_df.empty:
        st.warning("Standings data is currently unavailable.")
        return

    view = st.radio(
        "View",
        ["Conference", "Division", "League"],
        horizontal=True,
        key=mk_key("standings", "radio", "view"),
    )

    # Determine conference column
    conf_col = None
    for c in ("conferenceName", "conferenceAbbrev", "conference"):
        if c in standings_df.columns:
            conf_col = c
            break

    div_col = None
    for c in ("divisionName", "divisionAbbrev", "division"):
        if c in standings_df.columns:
            div_col = c
            break

    # Sort by points descending
    sdf = standings_df.sort_values("points", ascending=False).copy()

    if view == "League":
        wc_cut = _wildcard_cutoff(sdf, "")
        _render_standings_table(sdf, team_metrics_dict, wc_cut, "League")

    elif view == "Conference" and conf_col:
        conferences = sdf[conf_col].dropna().unique()
        for conf in sorted(conferences):
            st.markdown(f"### {conf}")
            subset = sdf[sdf[conf_col] == conf].sort_values("points", ascending=False)
            wc_cut = _wildcard_cutoff(sdf, conf)
            _render_standings_table(subset, team_metrics_dict, wc_cut, conf)

    elif view == "Division" and div_col:
        divisions = sdf[div_col].dropna().unique()
        for div in sorted(divisions):
            st.markdown(f"### {div}")
            subset = sdf[sdf[div_col] == div].sort_values("points", ascending=False)
            wc_cut = _wildcard_cutoff(sdf, "")
            _render_standings_table(subset, team_metrics_dict, wc_cut, div)
    else:
        wc_cut = _wildcard_cutoff(sdf, "")
        _render_standings_table(sdf, team_metrics_dict, wc_cut, "League")
