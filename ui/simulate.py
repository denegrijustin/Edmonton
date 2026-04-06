"""Simulate tab (Tab 5) — Monte Carlo game simulator."""

from typing import Any, Dict, List

import numpy as np
import streamlit as st

from config.settings import (
    LEAGUE_AVG_GPG,
    SIM_HOME_ADV,
    SIM_LAST10_WEIGHT,
    SIM_SEASON_WEIGHT,
)
from models.monte_carlo import monte_carlo_sim
from providers.metrics_provider import compute_team_metrics
from ui.charts import plot_sim_histogram
from ui.components import logo_card_html, prob_bar_html
from utils.stoplights import stoplight


def render(
    all_teams: List[str],
    standings_df,
    team_metrics_dict: Dict[str, Dict],
) -> None:
    """Render the Simulate tab content."""
    st.markdown("### 🎲 Monte Carlo Game Simulator")
    st.caption(
        "Runs 10,000 simulations using a blended team strength model "
        "(70% season average · 30% last-10 trend) + home ice advantage (+0.15 goals). "
        "Goals modelled with Poisson distribution."
    )

    sim_c1, sim_c2, sim_c3 = st.columns(3)
    with sim_c1:
        sim_a = st.selectbox("Team A", all_teams, index=0, key="sim_a")
    with sim_c2:
        sim_b = st.selectbox(
            "Team B",
            all_teams,
            index=1 if len(all_teams) > 1 else 0,
            key="sim_b",
        )
    with sim_c3:
        home_choice = st.radio("Home Team", [sim_a, sim_b], horizontal=True, key="sim_home")

    home_flag = "A" if home_choice == sim_a else "B"

    sim_ma = team_metrics_dict.get(sim_a, compute_team_metrics(sim_a, standings_df))
    sim_mb = team_metrics_dict.get(sim_b, compute_team_metrics(sim_b, standings_df))

    if "sim_seed" not in st.session_state:
        st.session_state["sim_seed"] = 0
    if st.button("🔄 Re-run Simulation", type="secondary"):
        st.session_state["sim_seed"] += 1

    sim_seed = st.session_state["sim_seed"]
    with st.spinner("Running 10,000 simulations…"):
        rng_seed = hash(f"{sim_a}{sim_b}{home_flag}{sim_seed}") & 0xFFFFFFFF
        rng_state = np.random.default_rng(rng_seed)  # noqa: F841
        sim_res = monte_carlo_sim(sim_ma, sim_mb, home_team=home_flag, n_sims=10000)

    a_win = sim_res["a_win_pct"]
    b_win = sim_res["b_win_pct"]
    ot_pct = sim_res["ot_pct"]
    a_avg = sim_res["a_avg_goals"]
    b_avg = sim_res["b_avg_goals"]
    a_arr = sim_res["a_goals_arr"]
    b_arr = sim_res["b_goals_arr"]
    a_lam = sim_res["a_lambda"]
    b_lam = sim_res["b_lambda"]

    res_left, res_right = st.columns([2, 3])

    with res_left:
        la_col, vs_col_s, lb_col = st.columns([2, 1, 2])
        with la_col:
            st.markdown(
                logo_card_html(sim_a, sim_a, "🏠 Home" if home_flag == "A" else "✈️ Away"),
                unsafe_allow_html=True,
            )
        with vs_col_s:
            st.markdown(
                "<div style='text-align:center;padding:18px 0;font-weight:800;font-size:1.1rem;'>VS</div>",
                unsafe_allow_html=True,
            )
        with lb_col:
            st.markdown(
                logo_card_html(sim_b, sim_b, "🏠 Home" if home_flag == "B" else "✈️ Away"),
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("**Win Probabilities**")
        st.markdown(prob_bar_html(f"{sim_a} wins", a_win, "#3b82f6"), unsafe_allow_html=True)
        st.markdown(prob_bar_html(f"{sim_b} wins", b_win, "#ef4444"), unsafe_allow_html=True)
        st.markdown(prob_bar_html("Goes to OT/SO", ot_pct, "#f59e0b"), unsafe_allow_html=True)

        st.markdown("---")
        proj_a_s = round(a_avg)
        proj_b_s = round(b_avg)
        st.markdown(f"**Projected Score:** `{sim_a} {proj_a_s} – {proj_b_s} {sim_b}`")

        a_lo = int(np.percentile(a_arr, 5))
        a_hi = int(np.percentile(a_arr, 95))
        b_lo = int(np.percentile(b_arr, 5))
        b_hi = int(np.percentile(b_arr, 95))
        st.markdown(
            f"**90% Confidence Range:** "
            f"{sim_a} {a_lo}–{a_hi} goals &nbsp;|&nbsp; {sim_b} {b_lo}–{b_hi} goals"
        )

        # Game script
        winner = sim_a if a_win >= b_win else sim_b
        win_pct_show = max(a_win, b_win)
        if ot_pct > 28:
            script = (
                f"Expect a tight battle. {winner} holds a {win_pct_show:.0f}% edge, "
                f"but {ot_pct:.0f}% of simulations go to overtime."
            )
        elif win_pct_show > 65:
            script = (
                f"{winner} is the clear favourite ({win_pct_show:.0f}%) "
                f"and projected to control this matchup throughout."
            )
        else:
            script = (
                f"Closely contested game. {winner} has a slight edge at {win_pct_show:.0f}%. "
                f"Either team can win on any given night."
            )
        st.info(f"**Most Likely Game Script:** {script}")

    with res_right:
        st.plotly_chart(
            plot_sim_histogram(a_arr, b_arr, sim_a, sim_b),
            use_container_width=True,
        )

        st.markdown("---")
        st.markdown("**Key Matchup Edges (Team A perspective)**")

        gf_edge = sim_ma["gf_per_game"] - sim_mb["gf_per_game"]
        ga_edge = sim_mb["ga_per_game"] - sim_ma["ga_per_game"]
        season_edge = (gf_edge + ga_edge) / 2

        l10_gf_edge = sim_ma["last10_gf_per_game"] - sim_mb["last10_gf_per_game"]
        l10_ga_edge = sim_mb["last10_ga_per_game"] - sim_ma["last10_ga_per_game"]
        l10_edge = (l10_gf_edge + l10_ga_edge) / 2

        home_edge_val = 0.15 if home_flag == "A" else -0.15
        lambda_edge = a_lam - b_lam

        edge_items = [
            ("Season Strength",     season_edge,    0.20, -0.20, True),
            ("Last 10 Momentum",    l10_edge,       0.20, -0.20, True),
            ("Home / Away",         home_edge_val,  0.10, -0.10, True),
            ("Expected Goals (λ)",  lambda_edge,    0.30, -0.30, True),
        ]

        for _elbl, _eval, _eg, _eb, _ehib in edge_items:
            try:
                _esl = stoplight(float(_eval), _eg, _eb, _ehib)
            except Exception:
                _esl = "⚪"
            _dir = "↑ A advantage" if _eval > 0.05 else "↓ B advantage" if _eval < -0.05 else "≈ Even"
            st.markdown(f"{_esl} **{_elbl}:** {_eval:+.3f} — *{_dir}*")

        with st.expander("ℹ️ Model Weighting Logic"):
            sw_pct = int(SIM_SEASON_WEIGHT * 100)
            l10_pct = int(SIM_LAST10_WEIGHT * 100)
            st.markdown(
                f"""
**Blended team strength (per team):**
- Season average: **{sw_pct}%** weight (`SIM_SEASON_WEIGHT`)
- Last 10 games: **{l10_pct}%** weight (`SIM_LAST10_WEIGHT`)

**Team A — {sim_a}**
| Metric | Season | Last 10 | Blended |
|---|---|---|---|
| GF/G | {sim_ma['gf_per_game']:.2f} | {sim_ma['last10_gf_per_game']:.2f} | {(SIM_SEASON_WEIGHT*sim_ma['gf_per_game']+SIM_LAST10_WEIGHT*sim_ma['last10_gf_per_game']):.2f} |
| GA/G | {sim_ma['ga_per_game']:.2f} | {sim_ma['last10_ga_per_game']:.2f} | {(SIM_SEASON_WEIGHT*sim_ma['ga_per_game']+SIM_LAST10_WEIGHT*sim_ma['last10_ga_per_game']):.2f} |

**Team B — {sim_b}**
| Metric | Season | Last 10 | Blended |
|---|---|---|---|
| GF/G | {sim_mb['gf_per_game']:.2f} | {sim_mb['last10_gf_per_game']:.2f} | {(SIM_SEASON_WEIGHT*sim_mb['gf_per_game']+SIM_LAST10_WEIGHT*sim_mb['last10_gf_per_game']):.2f} |
| GA/G | {sim_mb['ga_per_game']:.2f} | {sim_mb['last10_ga_per_game']:.2f} | {(SIM_SEASON_WEIGHT*sim_mb['ga_per_game']+SIM_LAST10_WEIGHT*sim_mb['last10_ga_per_game']):.2f} |

**Expected goals λ:** Team A = {a_lam:.3f} · Team B = {b_lam:.3f}

**Home ice advantage:** +{SIM_HOME_ADV} goals added to home team's λ, −{SIM_HOME_ADV} from away team.

**Simulation:** Poisson(λ) draws × 10,000. Tied games go to OT/SO (50/50 coin flip).
                """
            )
