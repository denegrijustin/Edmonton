"""Overview view — logo-first team summary dashboard.

Shows team identity, key stats, last-10 heat map, and upcoming games.
No simulations run at load time.
"""

from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from ui.components import (
    kpi_html,
    logo_card_html,
    prob_bar_html,
    safe_kpi,
    upcoming_card_html,
)
from utils.formatters import (
    fmt_number,
    fmt_pct,
    fmt_record,
    fmt_signed_int,
    safe_format,
)
from utils.logos import logo_url
from utils.stoplights import stoplight
from utils.streamlit_keys import mk_key


def _last10_heat_map_html(sel_tg: pd.DataFrame) -> str:
    """Build an HTML heat map of the last 10 game outcomes."""
    if sel_tg is None or sel_tg.empty:
        return "<p style='color:#94a3b8;font-size:0.85rem;'>No recent game data.</p>"

    recent = sel_tg.tail(10)
    cells = []
    for _, row in recent.iterrows():
        result = row.get("result", "?")
        opp = row.get("opponent", "?")
        if result == "W":
            bg, fg = "#dcfce7", "#166534"
        elif result == "OTL":
            bg, fg = "#fef9c3", "#713f12"
        elif result == "L":
            bg, fg = "#fee2e2", "#991b1b"
        else:
            bg, fg = "#f1f5f9", "#64748b"
        cells.append(
            f"<td style='background:{bg};color:{fg};text-align:center;"
            f"padding:6px 8px;font-weight:700;font-size:0.85rem;"
            f"border-radius:6px;min-width:42px;'>"
            f"{result}<br/>"
            f"<span style='font-size:0.7rem;font-weight:400;'>{opp}</span>"
            f"</td>"
        )
    return (
        "<table style='border-collapse:separate;border-spacing:4px;'><tr>"
        + "".join(cells)
        + "</tr></table>"
    )


def _upcoming_games_html(
    sel_schedule: pd.DataFrame,
    team: str,
    team_metrics_dict: Dict[str, Dict],
    count: int = 5,
) -> str:
    """Build upcoming game cards with opponent logos."""
    if sel_schedule is None or sel_schedule.empty:
        return "<p style='color:#94a3b8;font-size:0.85rem;'>No upcoming games.</p>"

    upcoming = sel_schedule[sel_schedule.get("isCompleted", pd.Series(dtype=bool)) == False]  # noqa: E712
    if upcoming.empty:
        return "<p style='color:#94a3b8;font-size:0.85rem;'>No upcoming games scheduled.</p>"

    upcoming = upcoming.head(count)
    cards = []
    for _, row in upcoming.iterrows():
        home = row.get("homeTeam", "")
        away = row.get("awayTeam", "")
        opponent = away if home == team else home
        venue = "Home" if home == team else "Away"
        date_str = str(row.get("gameDate", ""))[:10]

        opp_m = team_metrics_dict.get(opponent, {})
        opp_rec = fmt_record(
            opp_m.get("wins", 0), opp_m.get("losses", 0), opp_m.get("otl", 0)
        ) if opp_m else "—"

        cards.append(upcoming_card_html(opponent, f"{venue} · {date_str}", opp_rec))

    return (
        "<div style='display:flex;gap:8px;flex-wrap:wrap;'>"
        + "".join(cards)
        + "</div>"
    )


def render(
    selected_team: str,
    sel_name: str,
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    sel_schedule: pd.DataFrame,
    sel_tg: pd.DataFrame,
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    **kwargs: Any,
) -> None:
    """Render the overview tab."""
    if not sel_metrics:
        st.warning("Team metrics unavailable. Select a different team or try again.")
        return

    # ── Team identity row ─────────────────────────────────────────────────
    col_logo, col_info = st.columns([1, 3])
    with col_logo:
        st.markdown(
            logo_card_html(selected_team, selected_team, sel_name),
            unsafe_allow_html=True,
        )
    with col_info:
        wins = sel_metrics.get("wins", 0)
        losses = sel_metrics.get("losses", 0)
        otl = sel_metrics.get("otl", 0)
        gp = sel_metrics.get("gamesPlayed", 0)
        pts = sel_metrics.get("points", 0)
        record_str = fmt_record(wins, losses, otl)

        st.markdown(
            f"<h2 style='margin:0;'>{sel_name}</h2>"
            f"<span style='font-size:1.15rem;font-weight:600;'>"
            f"{record_str} &nbsp;·&nbsp; {fmt_number(pts)} pts"
            f"&nbsp;·&nbsp; {fmt_number(gp)} GP</span>",
            unsafe_allow_html=True,
        )

    # ── KPI row ───────────────────────────────────────────────────────────
    kpi_cols = st.columns(6)
    point_pct = (pts / max(gp * 2, 1)) * 100 if gp else None
    gd = sel_metrics.get("goalDifferential")
    reg_wins = sel_metrics.get("regulationWins")
    momentum = sel_metrics.get("momentum")
    conf_rank = sel_outlook.get("conference_rank") if sel_outlook else None
    streak = sel_metrics.get("streakCode", sel_metrics.get("streak"))

    kpi_data = [
        ("Point %", point_pct, "pct", 55, 45),
        ("Goal Diff", gd, "signed_int", 10, -10),
        ("Reg Wins", reg_wins, "plain", 25, 15),
        ("Momentum", momentum, "plain", 60, 45),
        ("Conf Rank", conf_rank, "plain", 4, 9),
    ]
    for i, (label, val, fmt, good, bad) in enumerate(kpi_data):
        hib = label != "Conf Rank"
        with kpi_cols[i]:
            st.markdown(
                safe_kpi(label, val, fmt=fmt, good=good, bad=bad, higher_is_better=hib),
                unsafe_allow_html=True,
            )
    with kpi_cols[5]:
        streak_display = str(streak) if streak else "—"
        st.markdown(kpi_html("Streak", streak_display), unsafe_allow_html=True)

    # ── Last 10 heat map ─────────────────────────────────────────────────
    st.markdown("#### Last 10 Games")
    l10w = sel_metrics.get("l10W", 0)
    l10l = sel_metrics.get("l10L", 0)
    l10otl = sel_metrics.get("l10OTL", 0)
    st.markdown(
        f"<span style='font-size:0.9rem;color:#64748b;'>"
        f"L10 Record: {fmt_record(l10w, l10l, l10otl)}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(_last10_heat_map_html(sel_tg), unsafe_allow_html=True)

    # ── Playoff position ─────────────────────────────────────────────────
    if sel_outlook:
        st.markdown("#### Playoff Position")
        po_cols = st.columns(4)
        with po_cols[0]:
            st.markdown(
                safe_kpi(
                    "Projected Pts",
                    sel_outlook.get("projected_points"),
                    fmt="plain", good=95, bad=85,
                    sub="Projected",
                ),
                unsafe_allow_html=True,
            )
        with po_cols[1]:
            seed = sel_outlook.get("projected_seed")
            seed_display = str(seed) if seed else "—"
            st.markdown(
                kpi_html("Projected Seed", seed_display, "Projected"),
                unsafe_allow_html=True,
            )
        with po_cols[2]:
            st.markdown(
                safe_kpi(
                    "Playoff Odds",
                    sel_outlook.get("playoff_odds"),
                    fmt="pct", good=70, bad=40,
                    sub="Projected",
                ),
                unsafe_allow_html=True,
            )
        with po_cols[3]:
            gap = sel_outlook.get("gap_to_cutoff")
            st.markdown(
                safe_kpi(
                    "Gap to Cutoff",
                    gap,
                    fmt="signed_int", good=5, bad=-5,
                ),
                unsafe_allow_html=True,
            )

    # ── Upcoming games ────────────────────────────────────────────────────
    st.markdown("#### Upcoming Games")
    st.markdown(
        _upcoming_games_html(sel_schedule, selected_team, team_metrics_dict),
        unsafe_allow_html=True,
    )
