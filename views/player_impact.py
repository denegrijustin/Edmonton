"""Player impact view — estimated player impact rankings.

Subviews: Season, Last 10, Single-Game, Wins, Losses.
Top 5 positive and bottom 5 negative with tables and heat indicators.
Clearly labeled as "Estimated Player Impact" with model explainer.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ui.components import kpi_html
from utils.formatters import fmt_number, fmt_signed_float
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from services.player_impact import (
    compute_player_impact,
    get_top_bottom_players,
    MODEL_LABEL,
    MODEL_DESCRIPTION,
)
from config.settings import SEASON


def _impact_color(score: float) -> str:
    """Return background color based on impact score."""
    if score >= 3.0:
        return "#dcfce7"
    if score >= 1.0:
        return "#d1fae5"
    if score >= 0:
        return "#f0fdf4"
    if score >= -1.0:
        return "#fef2f2"
    if score >= -3.0:
        return "#fee2e2"
    return "#fecaca"


def _player_table_html(
    players: List[Dict[str, Any]],
    title: str,
    is_positive: bool = True,
) -> str:
    """Build an HTML table for a list of players."""
    if not players:
        return f"<p style='color:#94a3b8;font-size:0.85rem;'>No {title.lower()} data available.</p>"

    rows = []
    for i, p in enumerate(players, 1):
        name = p.get("name", "Unknown")
        pos = p.get("position", "?")
        games = p.get("games", 0)
        impact = p.get("impact_score", 0)
        raw = p.get("raw_impact", 0)
        key_stats = p.get("key_stats", "")
        headshot = p.get("headshot", "")

        bg = _impact_color(impact)
        impact_str = fmt_signed_float(impact)

        img_html = ""
        if headshot:
            img_html = (
                f"<img src='{headshot}' width='28' height='28' "
                f"style='border-radius:50%;vertical-align:middle;margin-right:6px;'/>"
            )

        rows.append(
            f"<tr style='background:{bg};'>"
            f"<td style='padding:6px;text-align:center;font-weight:600;'>{i}</td>"
            f"<td style='padding:6px;'>{img_html}"
            f"<span style='font-weight:600;'>{name}</span>"
            f"<span style='color:#64748b;font-size:0.8rem;'> ({pos})</span></td>"
            f"<td style='padding:6px;text-align:center;'>{games}</td>"
            f"<td style='padding:6px;text-align:center;font-weight:700;"
            f"font-size:0.95rem;'>{impact_str}</td>"
            f"<td style='padding:6px;font-size:0.8rem;color:#475569;'>{key_stats}</td>"
            f"</tr>"
        )

    header = (
        "<thead><tr style='border-bottom:2px solid #cbd5e1;background:#f8fafc;'>"
        "<th style='padding:6px;text-align:center;'>#</th>"
        "<th style='padding:6px;'>Player</th>"
        "<th style='padding:6px;text-align:center;'>GP</th>"
        "<th style='padding:6px;text-align:center;'>Impact/G</th>"
        "<th style='padding:6px;'>Key Stats</th>"
        "</tr></thead>"
    )
    return (
        f"<div style='margin-bottom:16px;'>"
        f"<div style='font-weight:700;font-size:0.95rem;margin-bottom:6px;'>{title}</div>"
        f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
        f"{header}<tbody>{''.join(rows)}</tbody></table></div>"
    )


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    selected_team: str,
    sel_name: str,
    sel_tg: pd.DataFrame,
    team_name_map: Dict[str, str],
    **kwargs: Any,
) -> None:
    """Render the player impact view."""
    # ── Header with model explainer ───────────────────────────────────────
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<img src='{logo_url(selected_team)}' width='42' height='42'/>"
        f"<div>"
        f"<span style='font-size:1.1rem;font-weight:700;'>"
        f"Estimated Player Impact — {sel_name}</span><br/>"
        f"<span style='font-size:0.8rem;color:#64748b;'>{MODEL_LABEL}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    with st.expander("ℹ️ About this model"):
        st.markdown(MODEL_DESCRIPTION)
        st.caption(
            "Impact scores are **estimated** from box-score data and do not "
            "represent official NHL analytics. Use as a directional indicator only."
        )

    if sel_tg is None or sel_tg.empty:
        st.warning("No game data available to compute player impact.")
        return

    # ── Subview selector ──────────────────────────────────────────────────
    subview = st.radio(
        "Time Frame",
        ["Season", "Last 10", "Last Game", "Wins Only", "Losses Only"],
        horizontal=True,
        key=mk_key("player_impact", "radio", "subview"),
    )

    # Map subview to compute_player_impact parameters
    params: Dict[str, Any] = {"team": selected_team, "team_games": sel_tg, "season": SEASON}

    if subview == "Last 10":
        params["last_n"] = 10
    elif subview == "Last Game":
        params["last_n"] = 1
    elif subview == "Wins Only":
        params["result_filter"] = "W"
    elif subview == "Losses Only":
        params["result_filter"] = "L"

    # ── Compute impact ────────────────────────────────────────────────────
    compute_key = f"player_impact_{selected_team}_{subview}"
    run_btn = st.button(
        "▶ Compute Player Impact",
        key=mk_key("player_impact", "button", "compute"),
    )

    if run_btn:
        with st.spinner("Computing player impact from box scores…"):
            try:
                impact_list = compute_player_impact(**params)
                st.session_state[compute_key] = impact_list
            except Exception as e:
                st.error(f"Failed to compute player impact: {e}")
                st.session_state[compute_key] = []

    impact_list = st.session_state.get(compute_key)

    if impact_list is None:
        st.info("Click **▶ Compute Player Impact** to analyze player contributions.")
        return

    if not impact_list:
        st.warning("No player impact data available for the selected filters.")
        return

    # ── Top / Bottom players ──────────────────────────────────────────────
    tb = get_top_bottom_players(impact_list, top_n=5)

    col_top, col_bot = st.columns(2)
    with col_top:
        st.markdown(
            _player_table_html(tb["top"], "🟢 Top 5 Positive Impact", is_positive=True),
            unsafe_allow_html=True,
        )
    with col_bot:
        st.markdown(
            _player_table_html(tb["bottom"], "🔴 Bottom 5 Negative Impact", is_positive=False),
            unsafe_allow_html=True,
        )

    # ── Full roster table ─────────────────────────────────────────────────
    with st.expander("Full Roster Impact Rankings"):
        st.markdown(
            _player_table_html(impact_list, f"All Players — {subview}"),
            unsafe_allow_html=True,
        )

    st.caption(
        f"⚠️ All values are **Estimated** using the {MODEL_LABEL}. "
        f"Not an official NHL metric."
    )
