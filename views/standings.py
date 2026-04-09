"""Standings view — division, conference, wildcard, and playoff-race tables."""

import streamlit as st
import pandas as pd

from services.mode_state import AppMode
from ui.components import kpi_html
from utils.formatters import fmt_pct, fmt_record
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_int, safe_numeric


_PAGE = "standings"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _logo_img(abbrev: str, size: int = 28) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _l10_strip(row) -> str:
    """Compact inline heat strip from l10 counts."""
    w = safe_int(row.get("l10Wins"))
    lo = safe_int(row.get("l10Losses"))
    o = safe_int(row.get("l10OtLosses"))
    cells = (
        [f"<span style='color:#fff;background:#22c55e;border-radius:3px;"
         f"padding:0 3px;font-size:0.7rem;font-weight:700;margin:0 1px;'>W</span>"] * w
        + [f"<span style='color:#fff;background:#ef4444;border-radius:3px;"
           f"padding:0 3px;font-size:0.7rem;font-weight:700;margin:0 1px;'>L</span>"] * lo
        + [f"<span style='color:#fff;background:#f59e0b;border-radius:3px;"
           f"padding:0 3px;font-size:0.7rem;font-weight:700;margin:0 1px;'>O</span>"] * o
    )
    return "".join(cells)


def _status_icon(row) -> str:
    """Playoff status marker based on conference sequence."""
    cs = safe_int(row.get("conferenceSequence"))
    ws = safe_int(row.get("wildcardSequence"))
    if cs and cs <= 8:
        if ws and ws <= 2:
            return "🟡"
        return "✅"
    return "❌"


def _highlight_row(abbrev: str, selected: str) -> str:
    if abbrev == selected:
        return "background:#eff6ff;font-weight:700;"
    return ""


def _team_table_html(df: pd.DataFrame, selected_team: str, show_status: bool = True) -> str:
    """Build an HTML table from a standings subset."""
    if df is None or df.empty:
        return "<p>No data available.</p>"

    header = (
        "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
        "<tr style='border-bottom:2px solid #e2e8f0;'>"
        "<th style='text-align:left;padding:4px 6px;'>Team</th>"
    )
    if show_status:
        header += "<th style='padding:4px 3px;'>•</th>"
    header += (
        "<th style='padding:4px 6px;'>GP</th>"
        "<th style='padding:4px 6px;'>Pts</th>"
        "<th style='padding:4px 6px;'>Record</th>"
        "<th style='padding:4px 6px;'>GD</th>"
        "<th style='padding:4px 6px;'>Pts%</th>"
        "<th style='padding:4px 6px;'>Last 10</th>"
        "</tr>"
    )

    rows = []
    for _, r in df.iterrows():
        abbrev = r.get("teamAbbrev", "")
        hl = _highlight_row(abbrev, selected_team)
        w = safe_int(r.get("wins"))
        lo = safe_int(r.get("losses"))
        otl = safe_int(r.get("otLosses"))
        pts = safe_int(r.get("points"))
        gp = safe_int(r.get("gamesPlayed"))
        gd = safe_int(r.get("goalDifferential"))
        pp = safe_numeric(r.get("pointPctg"))
        pp_display = fmt_pct(pp * 100 if pp and pp < 1 else pp)

        row_html = f"<tr style='{hl}border-bottom:1px solid #f1f5f9;'>"
        row_html += (
            f"<td style='padding:4px 6px;white-space:nowrap;'>"
            f"{_logo_img(abbrev)} {r.get('teamName', abbrev)}</td>"
        )
        if show_status:
            row_html += f"<td style='padding:4px 3px;text-align:center;'>{_status_icon(r)}</td>"
        row_html += (
            f"<td style='padding:4px 6px;text-align:center;'>{gp}</td>"
            f"<td style='padding:4px 6px;text-align:center;font-weight:700;'>{pts}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{fmt_record(w, lo, otl)}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{gd:+d}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{pp_display}</td>"
            f"<td style='padding:4px 6px;'>{_l10_strip(r)}</td>"
            f"</tr>"
        )
        rows.append(row_html)

    return header + "".join(rows) + "</table>"


# ── Main render ───────────────────────────────────────────────────────────────

def render(standings_df, team_metrics_dict, team_name_map, selected_team, app_mode):
    """Render the Standings tab."""
    try:
        _render_inner(standings_df, team_metrics_dict, team_name_map,
                      selected_team, app_mode)
    except Exception as exc:
        st.error(f"Standings could not be rendered: {exc}")


def _render_inner(standings_df, team_metrics_dict, team_name_map,
                  selected_team, app_mode):
    if standings_df is None or standings_df.empty:
        st.info("Standings data is unavailable.")
        return

    view = st.radio(
        "View",
        ["Division", "Conference", "Wildcard", "Playoff Race"],
        horizontal=True,
        key=mk_key(_PAGE, "view_toggle"),
    )

    if view == "Division":
        _division_view(standings_df, selected_team)
    elif view == "Conference":
        _conference_view(standings_df, selected_team)
    elif view == "Wildcard":
        _wildcard_view(standings_df, selected_team)
    else:
        _playoff_race_view(standings_df, selected_team)


# ── Division view ─────────────────────────────────────────────────────────────

def _division_view(df: pd.DataFrame, selected_team: str):
    divisions = sorted(df["division"].dropna().unique())
    for div in divisions:
        sub = df[df["division"] == div].sort_values("divisionSequence")
        st.markdown(f"##### {div}")
        st.markdown(_team_table_html(sub, selected_team), unsafe_allow_html=True)


# ── Conference view ───────────────────────────────────────────────────────────

def _conference_view(df: pd.DataFrame, selected_team: str):
    conferences = sorted(df["conference"].dropna().unique())
    for conf in conferences:
        sub = df[df["conference"] == conf].sort_values("conferenceSequence")
        sub = sub.reset_index(drop=True)
        sub.index = sub.index + 1
        st.markdown(f"##### {conf}")
        st.markdown(_team_table_html(sub, selected_team), unsafe_allow_html=True)


# ── Wildcard view ─────────────────────────────────────────────────────────────

def _wildcard_view(df: pd.DataFrame, selected_team: str):
    conferences = sorted(df["conference"].dropna().unique())
    for conf in conferences:
        conf_df = df[df["conference"] == conf]
        divisions = sorted(conf_df["division"].dropna().unique())

        st.markdown(f"##### {conf}")
        for div in divisions:
            div_df = conf_df[conf_df["division"] == div].sort_values("divisionSequence")
            top3 = div_df.head(3)
            st.markdown(f"**{div} — Top 3**")
            st.markdown(_team_table_html(top3, selected_team, show_status=False),
                        unsafe_allow_html=True)

        # Wildcard slots
        wc_df = conf_df.sort_values("wildcardSequence")
        wc_df = wc_df[wc_df["wildcardSequence"].notna() & (wc_df["wildcardSequence"] > 0)]
        if not wc_df.empty:
            st.markdown("**Wildcard**")
            wc_top = wc_df[wc_df["wildcardSequence"] <= 2]
            if not wc_top.empty:
                st.markdown(_team_table_html(wc_top, selected_team, show_status=False),
                            unsafe_allow_html=True)
            st.markdown(
                "<hr style='border:1px dashed #94a3b8;margin:4px 0;'/>",
                unsafe_allow_html=True,
            )
            wc_out = wc_df[wc_df["wildcardSequence"] > 2]
            if not wc_out.empty:
                st.markdown(_team_table_html(wc_out, selected_team, show_status=False),
                            unsafe_allow_html=True)


# ── Playoff race view ────────────────────────────────────────────────────────

def _playoff_race_view(df: pd.DataFrame, selected_team: str):
    """Show teams near the playoff cutoff line."""
    conferences = sorted(df["conference"].dropna().unique())
    for conf in conferences:
        conf_df = df[df["conference"] == conf].sort_values("conferenceSequence")
        cutoff_row = conf_df[conf_df["conferenceSequence"] == 8]
        if cutoff_row.empty:
            near = conf_df.head(12)
        else:
            cutoff_pts = safe_int(cutoff_row.iloc[0].get("points"))
            near = conf_df[
                conf_df["points"].apply(lambda p: abs(safe_int(p) - cutoff_pts) <= 10)
            ]
            if near.empty:
                near = conf_df.head(12)

        st.markdown(f"##### {conf} — Playoff Bubble")
        st.markdown(_team_table_html(near, selected_team), unsafe_allow_html=True)
