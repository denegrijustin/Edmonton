"""Schedule view — upcoming games as compact cards and schedule difficulty.

Shows next 3-5 games with opponent logos, home/away, record, and form.
Remaining schedule difficulty uses real opponent data. No tiny charts.
"""

from typing import Any, Dict

import pandas as pd
import streamlit as st

from ui.components import kpi_html, safe_kpi, upcoming_card_html
from utils.formatters import fmt_number, fmt_pct, fmt_record, fmt_signed_int
from utils.logos import logo_url
from utils.streamlit_keys import mk_key


def _opponent_form_bar(m: Dict[str, Any]) -> str:
    """Small W/OTL/L bar for an opponent's last 10."""
    l10w = m.get("l10W", 0)
    l10l = m.get("l10L", 0)
    l10otl = m.get("l10OTL", 0)
    total = max(l10w + l10l + l10otl, 1)
    wp = int(l10w / total * 100)
    op = int(l10otl / total * 100)
    lp = 100 - wp - op
    return (
        f"<div style='display:flex;height:10px;border-radius:3px;overflow:hidden;"
        f"width:60px;'>"
        f"<div style='width:{wp}%;background:#22c55e;'></div>"
        f"<div style='width:{op}%;background:#eab308;'></div>"
        f"<div style='width:{lp}%;background:#ef4444;'></div>"
        f"</div>"
    )


def _upcoming_card(
    row: pd.Series,
    team: str,
    team_metrics_dict: Dict[str, Dict],
) -> str:
    """Build a rich upcoming-game card with opponent details."""
    home = row.get("homeTeam", "")
    away = row.get("awayTeam", "")
    opponent = away if home == team else home
    venue = "Home" if home == team else "Away"
    date_str = str(row.get("gameDate", ""))[:10]

    opp_m = team_metrics_dict.get(opponent, {})
    opp_rec = fmt_record(
        opp_m.get("wins", 0), opp_m.get("losses", 0), opp_m.get("otl", 0)
    ) if opp_m else "—"
    opp_pts = opp_m.get("points", "—") if opp_m else "—"

    logo = logo_url(opponent)
    form_bar = _opponent_form_bar(opp_m) if opp_m else ""
    venue_icon = "🏠" if venue == "Home" else "✈️"

    return (
        f"<div style='background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;"
        f"padding:12px;text-align:center;min-width:120px;'>"
        f"<img src='{logo}' width='48' height='48' style='object-fit:contain;'/>"
        f"<div style='font-weight:700;font-size:0.95rem;margin-top:4px;'>"
        f"{opponent}</div>"
        f"<div style='font-size:0.8rem;color:#64748b;'>"
        f"{venue_icon} {venue} · {date_str}</div>"
        f"<div style='font-size:0.8rem;font-weight:600;'>{opp_rec} · {opp_pts} pts</div>"
        f"<div style='display:flex;justify-content:center;margin-top:4px;'>"
        f"{form_bar}</div>"
        f"</div>"
    )


def _schedule_difficulty(
    sel_schedule: pd.DataFrame,
    team: str,
    team_metrics_dict: Dict[str, Dict],
) -> None:
    """Display remaining schedule difficulty metrics from real opponent data."""
    if sel_schedule is None or sel_schedule.empty:
        st.info("Schedule data unavailable.")
        return

    completed_col = sel_schedule.get("isCompleted", pd.Series(dtype=bool))
    remaining = sel_schedule[~completed_col.astype(bool)]
    if remaining.empty:
        st.info("No remaining games on the schedule.")
        return

    opp_points = []
    opp_records = []
    home_count = 0
    away_count = 0

    for _, row in remaining.iterrows():
        home = row.get("homeTeam", "")
        away = row.get("awayTeam", "")
        opponent = away if home == team else home
        if home == team:
            home_count += 1
        else:
            away_count += 1

        opp_m = team_metrics_dict.get(opponent, {})
        if opp_m:
            pts = opp_m.get("points", 0)
            gp = opp_m.get("gamesPlayed", 1)
            opp_points.append(pts / max(gp * 2, 1) * 100)

    avg_opp_pt_pct = sum(opp_points) / len(opp_points) if opp_points else None
    total_remaining = home_count + away_count

    st.markdown("#### Remaining Schedule Difficulty")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            safe_kpi("Games Left", total_remaining, fmt="plain", show_stoplight=False),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            safe_kpi("Home", home_count, fmt="plain", show_stoplight=False),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            safe_kpi("Away", away_count, fmt="plain", show_stoplight=False),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            safe_kpi(
                "Avg Opp Pt%",
                avg_opp_pt_pct,
                fmt="pct",
                good=45,
                bad=55,
                higher_is_better=False,
                sub="lower = easier",
            ),
            unsafe_allow_html=True,
        )

    # Opponent difficulty table
    if remaining.empty:
        return

    st.markdown("##### Upcoming Opponent Strength")
    rows_html = []
    for _, row in remaining.head(10).iterrows():
        home = row.get("homeTeam", "")
        away = row.get("awayTeam", "")
        opponent = away if home == team else home
        venue = "Home" if home == team else "Away"
        date_str = str(row.get("gameDate", ""))[:10]

        opp_m = team_metrics_dict.get(opponent, {})
        opp_rec = fmt_record(
            opp_m.get("wins", 0), opp_m.get("losses", 0), opp_m.get("otl", 0)
        ) if opp_m else "—"
        opp_pt_pct = None
        if opp_m:
            opp_gp = opp_m.get("gamesPlayed", 1)
            opp_pt_pct = opp_m.get("points", 0) / max(opp_gp * 2, 1) * 100

        logo = logo_url(opponent)
        form_bar = _opponent_form_bar(opp_m) if opp_m else ""

        # Color by difficulty
        if opp_pt_pct is not None:
            if opp_pt_pct >= 55:
                diff_bg = "#fee2e2"
            elif opp_pt_pct >= 48:
                diff_bg = "#fef9c3"
            else:
                diff_bg = "#dcfce7"
        else:
            diff_bg = "#f1f5f9"

        rows_html.append(
            f"<tr style='background:{diff_bg};'>"
            f"<td style='padding:6px;'>{date_str}</td>"
            f"<td style='padding:6px;'>"
            f"  <img src='{logo}' width='22' height='22' "
            f"  style='vertical-align:middle;margin-right:4px;'/>"
            f"  <span style='font-weight:600;'>{opponent}</span></td>"
            f"<td style='padding:6px;text-align:center;'>{venue}</td>"
            f"<td style='padding:6px;text-align:center;'>{opp_rec}</td>"
            f"<td style='padding:6px;text-align:center;'>"
            f"  {fmt_pct(opp_pt_pct) if opp_pt_pct is not None else '—'}</td>"
            f"<td style='padding:6px;'>{form_bar}</td>"
            f"</tr>"
        )

    header = (
        "<thead><tr style='border-bottom:2px solid #cbd5e1;'>"
        "<th style='padding:6px;'>Date</th>"
        "<th style='padding:6px;'>Opponent</th>"
        "<th style='padding:6px;text-align:center;'>Venue</th>"
        "<th style='padding:6px;text-align:center;'>Record</th>"
        "<th style='padding:6px;text-align:center;'>Pt%</th>"
        "<th style='padding:6px;'>L10 Form</th>"
        "</tr></thead>"
    )
    st.markdown(
        f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
        f"{header}<tbody>{''.join(rows_html)}</tbody></table>",
        unsafe_allow_html=True,
    )


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    selected_team: str,
    sel_name: str,
    sel_schedule: pd.DataFrame,
    sel_tg: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    **kwargs: Any,
) -> None:
    """Render schedule view with upcoming game cards and difficulty analysis."""
    if sel_schedule is None or sel_schedule.empty:
        st.warning("Schedule data is currently unavailable.")
        return

    # ── Upcoming games cards ──────────────────────────────────────────────
    st.markdown("#### Next Games")
    completed_series = sel_schedule.get("isCompleted", pd.Series(dtype=bool))
    upcoming = sel_schedule[~completed_series.astype(bool)]

    if upcoming.empty:
        st.info("No upcoming games on the schedule.")
    else:
        count = min(5, len(upcoming))
        cols = st.columns(count)
        for i, (_, row) in enumerate(upcoming.head(count).iterrows()):
            with cols[i]:
                st.markdown(
                    _upcoming_card(row, selected_team, team_metrics_dict),
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Schedule difficulty ───────────────────────────────────────────────
    _schedule_difficulty(sel_schedule, selected_team, team_metrics_dict)
