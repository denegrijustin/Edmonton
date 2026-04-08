"""Playoff race view — conference position, wildcard, clinch scenarios.

Projections clearly labeled. On-demand season simulation button.
No live bracket here.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ui.components import kpi_html, logo_card_html, prob_bar_html, safe_kpi
from utils.formatters import fmt_number, fmt_pct, fmt_record, fmt_signed_int
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from services.simulation import (
    SIM_DEPTHS,
    DEFAULT_SIM_DEPTH,
    run_season_sim_on_demand,
)
from config.settings import GAMES_IN_SEASON


def _clinch_scenario_text(
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    standings_df: pd.DataFrame,
) -> str:
    """Generate plain-language clinch/elimination scenarios."""
    if not sel_outlook:
        return "Outlook data unavailable."

    pts = sel_metrics.get("points", 0)
    gp = sel_metrics.get("gamesPlayed", 0)
    remaining = GAMES_IN_SEASON - gp
    max_pts = pts + remaining * 2
    projected = sel_outlook.get("projected_points", 0)
    cutoff = sel_outlook.get("west_cutoff_points", 0)
    gap = sel_outlook.get("gap_to_cutoff", 0)
    odds = sel_outlook.get("playoff_odds", 0)

    lines = []
    if gap is not None and gap > 0 and remaining < 15:
        lines.append(f"Currently **{gap} points above** the projected cutoff.")
    elif gap is not None and gap < 0:
        lines.append(
            f"Currently **{abs(gap)} points below** the projected cutoff. "
            f"Needs approximately {abs(gap) // 2 + 1} more wins to close the gap."
        )
    elif gap is not None:
        lines.append("Currently **on the cutoff line** — every game matters.")

    if max_pts and cutoff and max_pts < cutoff:
        lines.append("⚠️ **Mathematically eliminated** — cannot reach projected cutoff.")
    elif remaining <= 10 and odds and odds >= 90:
        lines.append(f"With {remaining} games left and {odds:.0f}% projected odds, a playoff spot is nearly secured.")
    elif remaining <= 10 and odds and odds <= 20:
        lines.append(f"With {remaining} games left and only {odds:.0f}% odds, the path is very narrow.")
    elif remaining > 0:
        wins_needed = max(0, (cutoff - pts + 1) // 2) if cutoff else None
        if wins_needed is not None:
            lines.append(
                f"Needs roughly **{wins_needed} wins** from {remaining} remaining games "
                f"to reach the projected cutoff of ~{cutoff} points."
            )

    return "\n\n".join(lines) if lines else "Season scenario analysis unavailable."


def _competitor_table(
    standings_df: pd.DataFrame,
    conference: str,
    team_metrics_dict: Dict[str, Dict],
    selected_team: str,
) -> None:
    """Render a conference competitor table with projection labels."""
    if standings_df.empty:
        st.info("Standings data unavailable.")
        return

    conf_col = None
    for c in ("conferenceName", "conferenceAbbrev", "conference"):
        if c in standings_df.columns:
            conf_col = c
            break

    if conf_col and conference:
        df = standings_df[
            standings_df[conf_col].str.contains(conference, case=False, na=False)
        ].copy()
    else:
        df = standings_df.copy()

    df = df.sort_values("points", ascending=False)

    rows_html = []
    for rank, (_, row) in enumerate(df.iterrows(), 1):
        abbrev = row.get("teamAbbrev", row.get("teamAbbrev.value", ""))
        if not abbrev:
            continue
        pts = row.get("points", 0)
        gp = row.get("gamesPlayed", 0)
        remaining = GAMES_IN_SEASON - gp
        wins = row.get("wins", 0)
        losses = row.get("losses", 0)
        otl = row.get("otLosses", row.get("otl", 0))
        rw = row.get("regulationWins", "—")
        logo = logo_url(abbrev)

        is_selected = abbrev == selected_team
        row_style = "background:#eff6ff;font-weight:600;" if is_selected else ""
        playoff_marker = "✅" if rank <= 8 else "❌" if rank > 12 else "⚠️"

        rows_html.append(
            f"<tr style='{row_style}'>"
            f"<td style='padding:5px;text-align:center;'>{rank}</td>"
            f"<td style='padding:5px;'>"
            f"  <img src='{logo}' width='22' height='22' "
            f"  style='vertical-align:middle;margin-right:4px;'/>"
            f"  <span style='font-weight:600;'>{abbrev}</span></td>"
            f"<td style='padding:5px;text-align:center;'>{gp}</td>"
            f"<td style='padding:5px;text-align:center;'>{fmt_record(wins, losses, otl)}</td>"
            f"<td style='padding:5px;text-align:center;font-weight:700;'>{pts}</td>"
            f"<td style='padding:5px;text-align:center;'>{rw}</td>"
            f"<td style='padding:5px;text-align:center;'>{remaining}</td>"
            f"<td style='padding:5px;text-align:center;'>{playoff_marker}</td>"
            f"</tr>"
        )

    header = (
        "<thead><tr style='border-bottom:2px solid #cbd5e1;background:#f8fafc;'>"
        "<th style='padding:5px;text-align:center;'>#</th>"
        "<th style='padding:5px;'>Team</th>"
        "<th style='padding:5px;text-align:center;'>GP</th>"
        "<th style='padding:5px;text-align:center;'>Record</th>"
        "<th style='padding:5px;text-align:center;'>PTS</th>"
        "<th style='padding:5px;text-align:center;'>RW</th>"
        "<th style='padding:5px;text-align:center;'>Rem</th>"
        "<th style='padding:5px;text-align:center;'>Status</th>"
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
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    season_state: Any = None,
    **kwargs: Any,
) -> None:
    """Render the playoff race view."""
    if not sel_metrics:
        st.warning("Team metrics unavailable.")
        return

    # ── Position summary ──────────────────────────────────────────────────
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;'>"
        f"<img src='{logo_url(selected_team)}' width='48' height='48'/>"
        f"<div>"
        f"<span style='font-size:1.2rem;font-weight:700;'>{sel_name}</span><br/>"
        f"<span style='color:#64748b;'>Playoff Race Status</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    kpi_cols = st.columns(5)
    conference = sel_outlook.get("conference", "") if sel_outlook else ""
    conf_rank = sel_outlook.get("conference_rank") if sel_outlook else None
    proj_pts = sel_outlook.get("projected_points") if sel_outlook else None
    proj_seed = sel_outlook.get("projected_seed") if sel_outlook else None
    playoff_odds = sel_outlook.get("playoff_odds") if sel_outlook else None
    gap = sel_outlook.get("gap_to_cutoff") if sel_outlook else None

    with kpi_cols[0]:
        st.markdown(
            safe_kpi("Conf Rank", conf_rank, fmt="plain", good=4, bad=9, higher_is_better=False),
            unsafe_allow_html=True,
        )
    with kpi_cols[1]:
        st.markdown(
            safe_kpi("Projected Pts", proj_pts, fmt="plain", good=95, bad=85, sub="Projected"),
            unsafe_allow_html=True,
        )
    with kpi_cols[2]:
        seed_str = str(proj_seed) if proj_seed else "—"
        st.markdown(kpi_html("Projected Seed", seed_str, "Projected"), unsafe_allow_html=True)
    with kpi_cols[3]:
        st.markdown(
            safe_kpi("Playoff Odds", playoff_odds, fmt="pct", good=70, bad=40, sub="Projected"),
            unsafe_allow_html=True,
        )
    with kpi_cols[4]:
        st.markdown(
            safe_kpi("Gap to Cutoff", gap, fmt="signed_int", good=5, bad=-5),
            unsafe_allow_html=True,
        )

    # ── Clinch scenarios ──────────────────────────────────────────────────
    st.markdown("#### Clinch / Elimination Scenarios")
    st.markdown(_clinch_scenario_text(sel_metrics, sel_outlook or {}, standings_df))

    # ── Conference competitor table ───────────────────────────────────────
    st.markdown(f"#### {conference or 'Conference'} Standings")
    _competitor_table(standings_df, conference, team_metrics_dict, selected_team)

    # ── On-demand season simulation ───────────────────────────────────────
    st.divider()
    st.markdown("#### Season Simulation")
    st.caption("🔬 Simulated playoff odds — run on demand only")

    sc1, sc2 = st.columns([3, 1])
    with sc1:
        depth_label = st.selectbox(
            "Simulation depth",
            list(SIM_DEPTHS.keys()),
            index=list(SIM_DEPTHS.keys()).index(DEFAULT_SIM_DEPTH),
            key=mk_key("playoff_race", "selectbox", "sim_depth"),
        )
    with sc2:
        run_btn = st.button(
            "▶ Run Season Sim",
            key=mk_key("playoff_race", "button", "run_sim"),
        )

    sim_key = "playoff_race_season_sim"
    if run_btn:
        n = SIM_DEPTHS[depth_label]
        with st.spinner(f"Simulating {n:,} seasons…"):
            result = run_season_sim_on_demand(standings_df, team_metrics_dict, n_sims=n)
        st.session_state[sim_key] = result

    sim_result = st.session_state.get(sim_key)
    if sim_result and isinstance(sim_result, dict):
        st.markdown("##### Simulated Playoff Odds by Team")
        team_odds = []
        for team_abbrev, data in sim_result.items():
            if isinstance(data, dict) and "playoff_odds" in data:
                team_odds.append((team_abbrev, data["playoff_odds"]))
        team_odds.sort(key=lambda x: x[1], reverse=True)

        rows_html = []
        for abbrev, odds in team_odds:
            if conference:
                m = team_metrics_dict.get(abbrev, {})
                if m:
                    conf_col = None
                    for c in ("conferenceName", "conferenceAbbrev", "conference"):
                        if c in standings_df.columns:
                            conf_col = c
                            break
                    if conf_col:
                        team_rows = standings_df[
                            standings_df.get("teamAbbrev", standings_df.get("teamAbbrev.value", pd.Series())) == abbrev
                        ]
                        if not team_rows.empty:
                            team_conf = team_rows.iloc[0].get(conf_col, "")
                            if not str(team_conf).lower().startswith(conference[:3].lower()):
                                continue

            logo = logo_url(abbrev)
            is_sel = abbrev == selected_team
            style = "background:#eff6ff;font-weight:600;" if is_sel else ""
            bar_w = max(0, min(100, odds))
            bar_color = "#22c55e" if odds >= 70 else "#eab308" if odds >= 40 else "#ef4444"
            rows_html.append(
                f"<tr style='{style}'>"
                f"<td style='padding:4px;'>"
                f"  <img src='{logo}' width='20' height='20' "
                f"  style='vertical-align:middle;margin-right:4px;'/>"
                f"  {abbrev}</td>"
                f"<td style='padding:4px;width:60%;'>"
                f"  <div style='background:#e2e8f0;border-radius:4px;height:16px;'>"
                f"  <div style='background:{bar_color};height:16px;border-radius:4px;"
                f"  width:{bar_w}%;font-size:0.75rem;color:white;padding-left:4px;"
                f"  line-height:16px;'>{odds:.1f}%</div></div></td>"
                f"</tr>"
            )

        if rows_html:
            st.markdown(
                f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
                f"<tbody>{''.join(rows_html)}</tbody></table>",
                unsafe_allow_html=True,
            )
            st.caption("⚠️ All odds are **Simulated** projections, not official.")
    elif not run_btn:
        st.info("Click **▶ Run Season Sim** to simulate the remaining season.")
