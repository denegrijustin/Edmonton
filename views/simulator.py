"""Simulator view — on-demand matchup and series simulations.

Supports Quick/Standard/Deep depth. Results clearly labeled "Simulated".
Series simulation can start from real current state.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from ui.components import kpi_html, logo_card_html, prob_bar_html
from utils.formatters import fmt_number, fmt_pct, fmt_record
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from services.simulation import (
    SIM_DEPTHS,
    DEFAULT_SIM_DEPTH,
    run_matchup_sim,
    run_series_sim,
)


def _render_matchup_result(
    team_a: str, team_b: str, result: Dict[str, Any],
) -> None:
    """Display matchup simulation results."""
    st.markdown(
        "<div style='background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;"
        "padding:8px 12px;margin-bottom:12px;font-size:0.85rem;'>"
        "⚠️ <strong>Simulated</strong> — These results are from a Monte Carlo model, "
        "not a prediction.</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        a_pct = result.get("a_win_pct", 0)  # Already 0-100 from monte_carlo_sim
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='{logo_url(team_a)}' width='48' height='48'/>"
            f"<div style='font-weight:700;font-size:1.1rem;'>{team_a}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            prob_bar_html(f"Win: {a_pct:.1f}%", a_pct, "#3b82f6"),
            unsafe_allow_html=True,
        )
        st.markdown(
            kpi_html("Avg Goals", f"{result.get('a_avg_goals', 0):.1f}", "Simulated"),
            unsafe_allow_html=True,
        )

    with c2:
        b_pct = result.get("b_win_pct", 0)  # Already 0-100 from monte_carlo_sim
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='{logo_url(team_b)}' width='48' height='48'/>"
            f"<div style='font-weight:700;font-size:1.1rem;'>{team_b}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            prob_bar_html(f"Win: {b_pct:.1f}%", b_pct, "#ef4444"),
            unsafe_allow_html=True,
        )
        st.markdown(
            kpi_html("Avg Goals", f"{result.get('b_avg_goals', 0):.1f}", "Simulated"),
            unsafe_allow_html=True,
        )

    # Additional details
    ot_pct = result.get("ot_pct", 0)  # Already 0-100
    a_reg = result.get("a_reg_win_pct", 0)  # Already 0-100
    b_reg = result.get("b_reg_win_pct", 0)  # Already 0-100
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        st.markdown(kpi_html("OT Probability", fmt_pct(ot_pct), "Simulated"), unsafe_allow_html=True)
    with dc2:
        st.markdown(kpi_html(f"{team_a} Reg Win", fmt_pct(a_reg), "Simulated"), unsafe_allow_html=True)
    with dc3:
        st.markdown(kpi_html(f"{team_b} Reg Win", fmt_pct(b_reg), "Simulated"), unsafe_allow_html=True)


def _render_series_result(
    team_a: str, team_b: str, result: Dict[str, Any],
    wins_a: int, wins_b: int,
) -> None:
    """Display series simulation results."""
    st.markdown(
        "<div style='background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;"
        "padding:8px 12px;margin-bottom:12px;font-size:0.85rem;'>"
        "⚠️ <strong>Simulated</strong> — Best-of-7 series Monte Carlo projection.</div>",
        unsafe_allow_html=True,
    )

    a_prob = result.get("team_a_wins_prob", 0) * 100
    b_prob = result.get("team_b_wins_prob", 0) * 100
    likely_len = result.get("most_likely_length", "—")
    avg_remaining = result.get("games_remaining_avg", "—")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='{logo_url(team_a)}' width='48' height='48'/>"
            f"<div style='font-weight:700;'>{team_a}</div>"
            f"<div style='font-size:0.85rem;color:#64748b;'>Current: {wins_a} wins</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            prob_bar_html(f"Series Win: {a_prob:.1f}%", a_prob, "#3b82f6"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='{logo_url(team_b)}' width='48' height='48'/>"
            f"<div style='font-weight:700;'>{team_b}</div>"
            f"<div style='font-size:0.85rem;color:#64748b;'>Current: {wins_b} wins</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            prob_bar_html(f"Series Win: {b_prob:.1f}%", b_prob, "#ef4444"),
            unsafe_allow_html=True,
        )

    mc1, mc2 = st.columns(2)
    with mc1:
        st.markdown(
            kpi_html("Most Likely Length", f"{likely_len} games", "Simulated"),
            unsafe_allow_html=True,
        )
    with mc2:
        avg_disp = f"{avg_remaining:.1f}" if isinstance(avg_remaining, (int, float)) else str(avg_remaining)
        st.markdown(
            kpi_html("Avg Games Remaining", avg_disp, "Simulated"),
            unsafe_allow_html=True,
        )


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    all_teams: List[str],
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    selected_team: str = "",
    series_list: Optional[List[Dict]] = None,
    **kwargs: Any,
) -> None:
    """Render the simulator view."""
    if not all_teams or len(all_teams) < 2:
        st.warning("Not enough teams available for simulation.")
        return

    sim_mode = st.radio(
        "Simulation Mode",
        ["Single Game", "Best-of-7 Series"],
        horizontal=True,
        key=mk_key("simulator", "radio", "mode"),
    )

    # ── Team selection ────────────────────────────────────────────────────
    tc1, tc2 = st.columns(2)
    default_a = all_teams.index(selected_team) if selected_team in all_teams else 0
    default_b = min(default_a + 1, len(all_teams) - 1)

    with tc1:
        team_a = st.selectbox(
            "Team A",
            all_teams,
            index=default_a,
            format_func=lambda t: f"{t} – {team_name_map.get(t, t)}",
            key=mk_key("simulator", "selectbox", "team_a"),
        )
    with tc2:
        team_b = st.selectbox(
            "Team B",
            all_teams,
            index=default_b,
            format_func=lambda t: f"{t} – {team_name_map.get(t, t)}",
            key=mk_key("simulator", "selectbox", "team_b"),
        )

    # ── Configuration ─────────────────────────────────────────────────────
    cfg1, cfg2, cfg3 = st.columns(3)
    with cfg1:
        depth_label = st.selectbox(
            "Depth",
            list(SIM_DEPTHS.keys()),
            index=list(SIM_DEPTHS.keys()).index(DEFAULT_SIM_DEPTH),
            key=mk_key("simulator", "selectbox", "depth"),
        )
    with cfg2:
        home_choice = st.radio(
            "Home team",
            [team_a, team_b, "Neutral"],
            horizontal=True,
            key=mk_key("simulator", "radio", "home"),
        )

    if sim_mode == "Best-of-7 Series":
        st.markdown("##### Starting Series State")
        st.caption("Set current wins to simulate from mid-series (0-0 for fresh series)")

        # Check for real active series state
        real_wa, real_wb = 0, 0
        if series_list:
            for s in series_list:
                teams_set = {s.get("topSeed"), s.get("bottomSeed")}
                if team_a in teams_set and team_b in teams_set:
                    if s.get("topSeed") == team_a:
                        real_wa = s.get("topSeedWins", 0)
                        real_wb = s.get("bottomSeedWins", 0)
                    else:
                        real_wa = s.get("bottomSeedWins", 0)
                        real_wb = s.get("topSeedWins", 0)
                    st.info(
                        f"Active series detected: {team_a} {real_wa} – {real_wb} {team_b}. "
                        f"Starting from real state."
                    )
                    break

        ws1, ws2 = st.columns(2)
        with ws1:
            wins_a = st.number_input(
                f"{team_a} Wins",
                min_value=0, max_value=3, value=real_wa,
                key=mk_key("simulator", "number", "wins_a"),
            )
        with ws2:
            wins_b = st.number_input(
                f"{team_b} Wins",
                min_value=0, max_value=3, value=real_wb,
                key=mk_key("simulator", "number", "wins_b"),
            )

    # ── Run button ────────────────────────────────────────────────────────
    run_btn = st.button(
        "▶ Run Simulation",
        key=mk_key("simulator", "button", "run"),
        type="primary",
    )

    sim_key = f"simulator_result_{sim_mode}_{team_a}_{team_b}"

    if run_btn:
        n = SIM_DEPTHS[depth_label]
        home_flag = "A" if home_choice == team_a else "B" if home_choice == team_b else "N"

        if sim_mode == "Single Game":
            with st.spinner(f"Simulating {n:,} games…"):
                result = run_matchup_sim(
                    team_a, team_b, team_metrics_dict,
                    home_team=home_flag, n_sims=n,
                )
            st.session_state[sim_key] = ("matchup", result)
        else:
            with st.spinner(f"Simulating {n:,} series…"):
                result = run_series_sim(
                    team_a, team_b, team_metrics_dict,
                    wins_a=wins_a, wins_b=wins_b, n_sims=n,
                )
            st.session_state[sim_key] = ("series", result, wins_a, wins_b)

    # ── Display results ───────────────────────────────────────────────────
    stored = st.session_state.get(sim_key)
    if stored:
        st.divider()
        if stored[0] == "matchup":
            _render_matchup_result(team_a, team_b, stored[1])
        elif stored[0] == "series":
            _render_series_result(team_a, team_b, stored[1], stored[2], stored[3])
    elif not run_btn:
        st.info("Configure your simulation and click **▶ Run Simulation**.")
