"""Player Impact view — top/bottom impact players with heat maps."""

import streamlit as st

from services.mode_state import AppMode
from services.player_impact import (
    compute_player_impact, get_top_impact_players, get_bottom_impact_players,
)
from ui.components import kpi_html
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


_PAGE = "player_impact"


def _impact_heat_color(score: float) -> str:
    """Map impact score to a background color."""
    if score >= 3.0:
        return "#bbf7d0"
    if score >= 1.5:
        return "#d1fae5"
    if score >= 0:
        return "#fef3c7"
    if score >= -1.5:
        return "#fed7aa"
    return "#fecaca"


def _impact_table_html(players: list, title: str) -> str:
    """Build an HTML table for impact players."""
    if not players:
        return f"<p><i>No {title.lower()} data available.</i></p>"

    html = (
        f"<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
        f"<tr style='border-bottom:2px solid #e2e8f0;'>"
        f"<th style='padding:4px 6px;text-align:left;'>#</th>"
        f"<th style='padding:4px 6px;text-align:left;'>Player</th>"
        f"<th style='padding:4px 6px;'>Pos</th>"
        f"<th style='padding:4px 6px;'>GP</th>"
        f"<th style='padding:4px 6px;'>Impact</th>"
        f"</tr>"
    )

    for i, p in enumerate(players, 1):
        name = p.get("name", "Unknown")
        pos = p.get("position", "—")
        gp = safe_int(p.get("games", 0))
        score = safe_numeric(p.get("impact_score", 0))
        bg = _impact_heat_color(score)

        html += (
            f"<tr style='border-bottom:1px solid #f1f5f9;'>"
            f"<td style='padding:4px 6px;'>{i}</td>"
            f"<td style='padding:4px 6px;font-weight:600;'>{name}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{pos}</td>"
            f"<td style='padding:4px 6px;text-align:center;'>{gp}</td>"
            f"<td style='padding:4px 6px;text-align:center;font-weight:700;"
            f"background:{bg};'>{score:+.2f}</td>"
            f"</tr>"
        )

    html += "</table>"
    return html


def _impact_heat_map(players: list) -> str:
    """Compact heat-map strip of all player impact scores."""
    if not players:
        return ""
    cells = []
    for p in players:
        score = safe_numeric(p.get("impact_score", 0))
        bg = _impact_heat_color(score)
        name_short = p.get("name", "?")[:8]
        cells.append(
            f"<span style='display:inline-block;padding:2px 4px;margin:1px;"
            f"border-radius:3px;background:{bg};font-size:0.68rem;font-weight:600;'>"
            f"{name_short} {score:+.1f}</span>"
        )
    return "".join(cells)


# ── Main render ───────────────────────────────────────────────────────────────

def render(selected_team, sel_tg, sel_schedule, app_mode):
    """Render the Player Impact tab."""
    try:
        _render_inner(selected_team, sel_tg, sel_schedule, app_mode)
    except Exception as exc:
        st.error(f"Player Impact view could not be rendered: {exc}")


def _render_inner(selected_team, sel_tg, sel_schedule, app_mode):
    st.markdown("#### Player Impact Analysis")
    st.caption("Estimated Player Impact (box-score model)")

    # Subview toggle
    sub = st.radio(
        "Period",
        ["Season", "Last 10", "Playoff"],
        horizontal=True,
        key=mk_key(_PAGE, "period"),
    )

    # Determine game IDs to use
    game_ids = _resolve_game_ids(sel_tg, sel_schedule, sub, app_mode)

    if not game_ids:
        st.info(f"No game data available for '{sub}' period. "
                "Ensure schedule data is loaded.")
        return

    st.markdown(f"**{len(game_ids)}** games available for analysis.")

    # Button-triggered computation
    cache_key = f"pi_{selected_team}_{sub}_{len(game_ids)}"
    if st.button("Compute Impact", key=mk_key(_PAGE, "compute_btn")):
        with st.spinner("Computing player impact…"):
            impact = compute_player_impact(game_ids, selected_team)
        st.session_state[cache_key] = impact

    impact = st.session_state.get(cache_key)
    if not impact:
        st.info("Press **Compute Impact** to analyze player performance.")
        return

    # Top / Bottom tables
    top5 = get_top_impact_players(impact, n=5)
    bot5 = get_bottom_impact_players(impact, n=5)

    tc = st.columns(2)
    with tc[0]:
        st.markdown("##### Top 5 Positive Impact")
        st.markdown(_impact_table_html(top5, "positive impact"), unsafe_allow_html=True)
    with tc[1]:
        st.markdown("##### Bottom 5 Impact")
        st.markdown(_impact_table_html(bot5, "negative impact"), unsafe_allow_html=True)

    # Impact heat map
    with st.expander("Full Impact Heat Map"):
        sorted_all = sorted(impact, key=lambda p: p.get("impact_score", 0), reverse=True)
        st.markdown(_impact_heat_map(sorted_all), unsafe_allow_html=True)


def _resolve_game_ids(sel_tg, sel_schedule, sub, app_mode):
    """Determine which game IDs to use for the selected sub-period."""
    ids = []

    if sel_tg is not None and not sel_tg.empty and "gameId" in sel_tg.columns:
        if sub == "Last 10":
            ids = sel_tg.tail(10)["gameId"].dropna().astype(int).tolist()
        elif sub == "Playoff" and app_mode == AppMode.PLAYOFFS:
            # Playoff games have gameType == 3
            if "gameType" in sel_tg.columns:
                playoff_games = sel_tg[sel_tg["gameType"] == 3]
                ids = playoff_games["gameId"].dropna().astype(int).tolist()
            if not ids:
                ids = sel_tg.tail(10)["gameId"].dropna().astype(int).tolist()
        else:
            ids = sel_tg["gameId"].dropna().astype(int).tolist()
    elif sel_schedule is not None and not sel_schedule.empty and "gameId" in sel_schedule.columns:
        completed = sel_schedule
        if "isCompleted" in sel_schedule.columns:
            completed = sel_schedule[sel_schedule["isCompleted"] == True]
        if sub == "Last 10":
            ids = completed.tail(10)["gameId"].dropna().astype(int).tolist()
        else:
            ids = completed["gameId"].dropna().astype(int).tolist()

    return ids
