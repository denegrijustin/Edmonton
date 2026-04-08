"""Bracket view — projected or live playoff bracket with logo cards.

Before playoffs: clearly labeled "Projected Bracket (Simulated)".
After: live bracket with real scores. On-demand bracket simulation only.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ui.components import kpi_html, logo_card_html, prob_bar_html
from utils.formatters import fmt_number
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from services.simulation import SIM_DEPTHS, DEFAULT_SIM_DEPTH, run_bracket_sim
from services.series_tracker import get_active_series, get_completed_series
from config.settings import PLAYOFF_BRACKET_MAP


def _series_card_html(
    series: Dict[str, Any],
    sim_odds: Optional[Dict[str, Dict]] = None,
) -> str:
    """Render a single series matchup as an HTML card with logos."""
    top = series.get("topSeed", "?")
    bottom = series.get("bottomSeed", "?")
    tw = series.get("topSeedWins", 0)
    bw = series.get("bottomSeedWins", 0)
    status = series.get("seriesStatus", "")
    is_complete = series.get("is_complete", False)
    winner = series.get("winner")

    logo_top = logo_url(top)
    logo_bot = logo_url(bottom)

    # Highlight winner row
    top_style = "font-weight:800;" if winner == top else ""
    bot_style = "font-weight:800;" if winner == bottom else ""
    top_bg = "#dcfce7" if winner == top else "#f8fafc"
    bot_bg = "#dcfce7" if winner == bottom else "#f8fafc"

    # Series score dots
    def _dots(wins, total=4):
        filled = "●" * wins
        empty = "○" * (total - wins)
        return f"<span style='letter-spacing:2px;'>{filled}{empty}</span>"

    odds_row = ""
    if sim_odds and not is_complete:
        top_odds = sim_odds.get(top, {}).get("next_round_odds", 0)
        bot_odds = sim_odds.get(bottom, {}).get("next_round_odds", 0)
        if top_odds or bot_odds:
            odds_row = (
                f"<tr><td colspan='3' style='padding:4px;text-align:center;"
                f"font-size:0.75rem;color:#64748b;border-top:1px dashed #e2e8f0;'>"
                f"Simulated: {top} {top_odds:.0f}% — {bot_odds:.0f}% {bottom}"
                f"</td></tr>"
            )

    return (
        f"<table style='border:1px solid #e2e8f0;border-radius:10px;"
        f"overflow:hidden;min-width:200px;border-collapse:collapse;'>"
        f"<tr style='background:{top_bg};'>"
        f"<td style='padding:8px;'>"
        f"  <img src='{logo_top}' width='28' height='28' "
        f"  style='vertical-align:middle;margin-right:6px;'/>"
        f"  <span style='{top_style}'>{top}</span></td>"
        f"<td style='padding:8px;text-align:center;font-weight:700;"
        f"font-size:1.1rem;'>{tw}</td>"
        f"<td style='padding:8px;text-align:right;font-size:0.8rem;'>"
        f"  {_dots(tw)}</td>"
        f"</tr>"
        f"<tr style='background:{bot_bg};border-top:1px solid #e2e8f0;'>"
        f"<td style='padding:8px;'>"
        f"  <img src='{logo_bot}' width='28' height='28' "
        f"  style='vertical-align:middle;margin-right:6px;'/>"
        f"  <span style='{bot_style}'>{bottom}</span></td>"
        f"<td style='padding:8px;text-align:center;font-weight:700;"
        f"font-size:1.1rem;'>{bw}</td>"
        f"<td style='padding:8px;text-align:right;font-size:0.8rem;'>"
        f"  {_dots(bw)}</td>"
        f"</tr>"
        f"{odds_row}"
        f"<tr><td colspan='3' style='padding:4px 8px;text-align:center;"
        f"font-size:0.75rem;color:#94a3b8;background:#f8fafc;'>"
        f"{status}</td></tr>"
        f"</table>"
    )


def _projected_bracket(
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
) -> List[Dict[str, Any]]:
    """Build a projected bracket from current standings for pre-playoff display."""
    if standings_df.empty:
        return []

    conf_col = None
    for c in ("conferenceName", "conferenceAbbrev", "conference"):
        if c in standings_df.columns:
            conf_col = c
            break

    series_list = []
    if not conf_col:
        return series_list

    for conf in standings_df[conf_col].dropna().unique():
        conf_df = standings_df[standings_df[conf_col] == conf].sort_values(
            "points", ascending=False
        )
        teams = conf_df.get("teamAbbrev", conf_df.get("teamAbbrev.value", pd.Series())).tolist()
        if len(teams) < 8:
            continue

        for seed, opp_seed in PLAYOFF_BRACKET_MAP.items():
            if seed < opp_seed and seed <= len(teams) and opp_seed <= len(teams):
                series_list.append({
                    "topSeed": teams[seed - 1],
                    "bottomSeed": teams[opp_seed - 1],
                    "topSeedWins": 0,
                    "bottomSeedWins": 0,
                    "is_complete": False,
                    "winner": None,
                    "round": 1,
                    "seriesStatus": "Projected Matchup",
                    "teams": (teams[seed - 1], teams[opp_seed - 1]),
                    "games": [],
                    "completed_games": [],
                    "next_game": None,
                })

    return series_list


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    season_state: Any = None,
    playoff_state_obj: Any = None,
    series_list: Optional[List[Dict]] = None,
    selected_team: str = "",
    **kwargs: Any,
) -> None:
    """Render the bracket view."""
    is_playoffs = False
    if playoff_state_obj and hasattr(playoff_state_obj, "playoffs_started"):
        is_playoffs = playoff_state_obj.playoffs_started
    if season_state and hasattr(season_state, "value"):
        if str(season_state.value).lower() == "playoffs":
            is_playoffs = True

    if is_playoffs and series_list:
        # ── Live bracket ──────────────────────────────────────────────
        st.markdown("### 🏒 Playoff Bracket — Live")
        active = get_active_series(series_list)
        completed = get_completed_series(series_list)

        if active:
            st.markdown("#### Active Series")
            cols = st.columns(min(len(active), 4))
            for i, s in enumerate(active):
                with cols[i % len(cols)]:
                    st.markdown(_series_card_html(s), unsafe_allow_html=True)

        if completed:
            st.markdown("#### Completed Series")
            cols = st.columns(min(len(completed), 4))
            for i, s in enumerate(completed):
                with cols[i % len(cols)]:
                    st.markdown(_series_card_html(s), unsafe_allow_html=True)

        # On-demand bracket sim
        st.divider()
        st.markdown("#### Bracket Simulation")
        st.caption("🔬 Simulated — run on demand only")

        sc1, sc2 = st.columns([3, 1])
        with sc1:
            depth_label = st.selectbox(
                "Simulation depth",
                list(SIM_DEPTHS.keys()),
                index=list(SIM_DEPTHS.keys()).index(DEFAULT_SIM_DEPTH),
                key=mk_key("bracket", "selectbox", "sim_depth"),
            )
        with sc2:
            run_btn = st.button(
                "▶ Simulate Bracket",
                key=mk_key("bracket", "button", "run_sim"),
            )

        bsim_key = "bracket_sim_results"
        if run_btn:
            n = SIM_DEPTHS[depth_label]
            with st.spinner(f"Simulating bracket ({n:,} runs)…"):
                result = run_bracket_sim(series_list, team_metrics_dict, n_sims=n)
            st.session_state[bsim_key] = result

        sim_odds = st.session_state.get(bsim_key)
        if sim_odds and isinstance(sim_odds, dict):
            st.markdown("##### Simulated Cup Odds")
            odds_sorted = sorted(sim_odds.items(), key=lambda x: x[1].get("cup_odds", 0), reverse=True)
            rows_html = []
            for abbrev, odds in odds_sorted:
                cup = odds.get("cup_odds", 0)
                finals = odds.get("finals_odds", 0)
                conf_f = odds.get("conf_finals_odds", 0)
                logo = logo_url(abbrev)
                is_sel = abbrev == selected_team
                style = "background:#eff6ff;" if is_sel else ""
                rows_html.append(
                    f"<tr style='{style}'>"
                    f"<td style='padding:4px;'>"
                    f"  <img src='{logo}' width='20' height='20' "
                    f"  style='vertical-align:middle;margin-right:4px;'/>{abbrev}</td>"
                    f"<td style='padding:4px;text-align:center;font-weight:700;'>"
                    f"  {cup:.1f}%</td>"
                    f"<td style='padding:4px;text-align:center;'>{finals:.1f}%</td>"
                    f"<td style='padding:4px;text-align:center;'>{conf_f:.1f}%</td>"
                    f"</tr>"
                )
            header = (
                "<thead><tr style='border-bottom:2px solid #cbd5e1;background:#f8fafc;'>"
                "<th style='padding:4px;'>Team</th>"
                "<th style='padding:4px;text-align:center;'>Cup %</th>"
                "<th style='padding:4px;text-align:center;'>Finals %</th>"
                "<th style='padding:4px;text-align:center;'>Conf Finals %</th>"
                "</tr></thead>"
            )
            st.markdown(
                f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
                f"{header}<tbody>{''.join(rows_html)}</tbody></table>",
                unsafe_allow_html=True,
            )
            st.caption("⚠️ All odds are **Simulated** projections.")
        elif not run_btn:
            st.info("Click **▶ Simulate Bracket** to run bracket simulations.")

    else:
        # ── Projected bracket (pre-playoffs) ──────────────────────────
        st.markdown("### 🔮 Projected Bracket (Simulated)")
        st.caption(
            "⚠️ This bracket is **projected** from current standings and is "
            "**not official**. Matchups will change as the season progresses."
        )

        projected = _projected_bracket(standings_df, team_metrics_dict)
        if not projected:
            st.info("Cannot generate projected bracket from current standings data.")
            return

        cols = st.columns(min(len(projected), 4))
        for i, s in enumerate(projected):
            with cols[i % len(cols)]:
                st.markdown(_series_card_html(s), unsafe_allow_html=True)

        # On-demand bracket sim for projected matchups
        st.divider()
        st.markdown("#### Simulate Projected Bracket")
        st.caption("🔬 Simulated — run on demand only")

        sc1, sc2 = st.columns([3, 1])
        with sc1:
            depth_label = st.selectbox(
                "Simulation depth",
                list(SIM_DEPTHS.keys()),
                index=list(SIM_DEPTHS.keys()).index(DEFAULT_SIM_DEPTH),
                key=mk_key("bracket", "selectbox", "proj_depth"),
            )
        with sc2:
            run_btn = st.button(
                "▶ Simulate",
                key=mk_key("bracket", "button", "proj_sim"),
            )

        psim_key = "bracket_proj_sim_results"
        if run_btn:
            n = SIM_DEPTHS[depth_label]
            with st.spinner(f"Simulating projected bracket ({n:,} runs)…"):
                result = run_bracket_sim(projected, team_metrics_dict, n_sims=n)
            st.session_state[psim_key] = result

        proj_sim = st.session_state.get(psim_key)
        if proj_sim and isinstance(proj_sim, dict):
            st.markdown("##### Simulated Series Win Probabilities")
            for s in projected:
                top = s["topSeed"]
                bot = s["bottomSeed"]
                t_odds = proj_sim.get(top, {}).get("next_round_odds", 50)
                b_odds = proj_sim.get(bot, {}).get("next_round_odds", 50)
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;"
                    f"margin-bottom:6px;'>"
                    f"<img src='{logo_url(top)}' width='22' height='22'/>"
                    f"<span style='font-weight:600;width:40px;'>{top}</span>"
                    f"<div style='flex:1;background:#e2e8f0;border-radius:4px;"
                    f"height:18px;position:relative;'>"
                    f"<div style='background:#3b82f6;height:18px;border-radius:4px;"
                    f"width:{t_odds:.0f}%;'></div>"
                    f"<span style='position:absolute;left:4px;top:0;font-size:0.72rem;"
                    f"color:white;line-height:18px;'>{t_odds:.0f}%</span>"
                    f"</div>"
                    f"<span style='font-weight:600;width:40px;text-align:right;'>"
                    f"{bot}</span>"
                    f"<img src='{logo_url(bot)}' width='22' height='22'/>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            st.caption("⚠️ All odds are **Simulated** projections.")
        elif not run_btn:
            st.info("Click **▶ Simulate** to project series outcomes.")
