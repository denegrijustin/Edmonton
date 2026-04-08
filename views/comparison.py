"""Comparison view — side-by-side team comparison with logos.

Heat map matrix for offense, defense, recent form. Head-to-head simulation
runs on-demand only (never automatically).
"""

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from ui.components import kpi_html, logo_card_html, prob_bar_html, safe_kpi
from utils.formatters import (
    fmt_number,
    fmt_pct,
    fmt_record,
    fmt_signed_float,
    fmt_signed_int,
)
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from services.simulation import SIM_DEPTHS, DEFAULT_SIM_DEPTH, run_matchup_sim


def _heat_color(val_a: float, val_b: float, higher_is_better: bool = True) -> tuple:
    """Return (color_a, color_b) based on which value is better."""
    if val_a is None or val_b is None:
        return ("#f1f5f9", "#f1f5f9")
    better_color = "#dcfce7"
    worse_color = "#fee2e2"
    tie_color = "#fef9c3"

    if abs(val_a - val_b) < 0.01:
        return (tie_color, tie_color)
    if higher_is_better:
        return (better_color, worse_color) if val_a > val_b else (worse_color, better_color)
    return (worse_color, better_color) if val_a > val_b else (better_color, worse_color)


def _safe_get(m: Dict, key: str, default=None):
    """Safely get a numeric value from metrics dict."""
    v = m.get(key, default)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _comparison_matrix_html(
    team_a: str,
    team_b: str,
    ma: Dict[str, Any],
    mb: Dict[str, Any],
) -> str:
    """Build an HTML heat map comparison matrix."""
    logo_a = logo_url(team_a)
    logo_b = logo_url(team_b)

    metrics = [
        ("Points", "points", True, "plain"),
        ("Wins", "wins", True, "plain"),
        ("Goal Diff", "goalDifferential", True, "signed"),
        ("GF/Game", "gf_per_game", True, "float"),
        ("GA/Game", "ga_per_game", False, "float"),
        ("L10 GF/G", "last10_gf_per_game", True, "float"),
        ("L10 GA/G", "last10_ga_per_game", False, "float"),
        ("L10 W", "l10W", True, "plain"),
        ("Momentum", "momentum", True, "plain"),
    ]

    rows = []
    for label, key, hib, fmt in metrics:
        va = _safe_get(ma, key)
        vb = _safe_get(mb, key)
        ca, cb = _heat_color(va, vb, hib)

        if fmt == "signed" and va is not None:
            disp_a = fmt_signed_int(va)
        elif fmt == "float" and va is not None:
            disp_a = f"{va:.2f}"
        elif va is not None:
            disp_a = fmt_number(va)
        else:
            disp_a = "—"

        if fmt == "signed" and vb is not None:
            disp_b = fmt_signed_int(vb)
        elif fmt == "float" and vb is not None:
            disp_b = f"{vb:.2f}"
        elif vb is not None:
            disp_b = fmt_number(vb)
        else:
            disp_b = "—"

        rows.append(
            f"<tr>"
            f"<td style='background:{ca};padding:8px 12px;text-align:center;"
            f"font-weight:700;font-size:0.95rem;'>{disp_a}</td>"
            f"<td style='padding:8px 16px;text-align:center;font-weight:600;"
            f"font-size:0.85rem;background:#f8fafc;color:#475569;'>{label}</td>"
            f"<td style='background:{cb};padding:8px 12px;text-align:center;"
            f"font-weight:700;font-size:0.95rem;'>{disp_b}</td>"
            f"</tr>"
        )

    header = (
        f"<tr style='border-bottom:2px solid #cbd5e1;'>"
        f"<th style='padding:10px;text-align:center;'>"
        f"<img src='{logo_a}' width='40' height='40'/><br/>"
        f"<span style='font-weight:700;'>{team_a}</span></th>"
        f"<th style='padding:10px;text-align:center;font-size:0.8rem;"
        f"color:#94a3b8;'>METRIC</th>"
        f"<th style='padding:10px;text-align:center;'>"
        f"<img src='{logo_b}' width='40' height='40'/><br/>"
        f"<span style='font-weight:700;'>{team_b}</span></th>"
        f"</tr>"
    )

    return (
        f"<table style='width:100%;border-collapse:collapse;'>"
        f"<thead>{header}</thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f"</table>"
    )


# ── Public render ─────────────────────────────────────────────────────────────

def render(
    all_teams: List[str],
    standings_df: pd.DataFrame,
    team_metrics_dict: Dict[str, Dict],
    team_name_map: Dict[str, str],
    selected_team: str = "",
    **kwargs: Any,
) -> None:
    """Render the side-by-side comparison view."""
    if not all_teams or len(all_teams) < 2:
        st.warning("Not enough teams available for comparison.")
        return

    # ── Team selectors ────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    default_a = all_teams.index(selected_team) if selected_team in all_teams else 0
    default_b = min(default_a + 1, len(all_teams) - 1)

    with col_a:
        team_a = st.selectbox(
            "Team A",
            all_teams,
            index=default_a,
            format_func=lambda t: f"{t} – {team_name_map.get(t, t)}",
            key=mk_key("comparison", "selectbox", "team_a"),
        )
    with col_b:
        team_b = st.selectbox(
            "Team B",
            all_teams,
            index=default_b,
            format_func=lambda t: f"{t} – {team_name_map.get(t, t)}",
            key=mk_key("comparison", "selectbox", "team_b"),
        )

    ma = team_metrics_dict.get(team_a, {})
    mb = team_metrics_dict.get(team_b, {})

    if not ma and not mb:
        st.warning("Metrics unavailable for both teams.")
        return

    # ── Logo header ───────────────────────────────────────────────────────
    lc1, lc2 = st.columns(2)
    with lc1:
        rec_a = fmt_record(ma.get("wins", 0), ma.get("losses", 0), ma.get("otl", 0))
        st.markdown(
            logo_card_html(team_a, team_a, f"{team_name_map.get(team_a, team_a)} · {rec_a}"),
            unsafe_allow_html=True,
        )
    with lc2:
        rec_b = fmt_record(mb.get("wins", 0), mb.get("losses", 0), mb.get("otl", 0))
        st.markdown(
            logo_card_html(team_b, team_b, f"{team_name_map.get(team_b, team_b)} · {rec_b}"),
            unsafe_allow_html=True,
        )

    # ── Comparison heat map ───────────────────────────────────────────────
    st.markdown("#### Head-to-Head Comparison")
    st.markdown(
        _comparison_matrix_html(team_a, team_b, ma, mb),
        unsafe_allow_html=True,
    )

    # ── On-demand matchup simulation ──────────────────────────────────────
    st.divider()
    st.markdown("#### Matchup Simulation")
    st.caption("🔬 Simulated results — run on demand only")

    sim_col1, sim_col2, sim_col3 = st.columns([2, 2, 1])
    with sim_col1:
        home_choice = st.radio(
            "Home team",
            [team_a, team_b, "Neutral"],
            horizontal=True,
            key=mk_key("comparison", "radio", "home"),
        )
    with sim_col2:
        depth_label = st.selectbox(
            "Simulation depth",
            list(SIM_DEPTHS.keys()),
            index=list(SIM_DEPTHS.keys()).index(DEFAULT_SIM_DEPTH),
            key=mk_key("comparison", "selectbox", "depth"),
        )
    with sim_col3:
        run_sim = st.button(
            "▶ Simulate",
            key=mk_key("comparison", "button", "run_sim"),
        )

    sim_key = f"comparison_sim_{team_a}_{team_b}"
    if run_sim:
        home_flag = "A" if home_choice == team_a else "B" if home_choice == team_b else "N"
        n = SIM_DEPTHS[depth_label]
        with st.spinner(f"Running {n:,} simulations…"):
            result = run_matchup_sim(team_a, team_b, team_metrics_dict, home_team=home_flag, n_sims=n)
        st.session_state[sim_key] = result

    sim_result = st.session_state.get(sim_key)
    if sim_result:
        st.markdown("##### Simulated Win Probabilities")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.markdown(
                prob_bar_html(
                    f"{team_a} Win",
                    sim_result.get("a_win_pct", 0) * 100,
                    "#3b82f6",
                ),
                unsafe_allow_html=True,
            )
        with rc2:
            st.markdown(
                prob_bar_html(
                    f"{team_b} Win",
                    sim_result.get("b_win_pct", 0) * 100,
                    "#ef4444",
                ),
                unsafe_allow_html=True,
            )

        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            st.markdown(
                kpi_html(
                    f"{team_a} Avg Goals",
                    f"{sim_result.get('a_avg_goals', 0):.1f}",
                    "Simulated",
                ),
                unsafe_allow_html=True,
            )
        with gc2:
            st.markdown(
                kpi_html("OT Probability", fmt_pct(sim_result.get("ot_pct", 0) * 100), "Simulated"),
                unsafe_allow_html=True,
            )
        with gc3:
            st.markdown(
                kpi_html(
                    f"{team_b} Avg Goals",
                    f"{sim_result.get('b_avg_goals', 0):.1f}",
                    "Simulated",
                ),
                unsafe_allow_html=True,
            )
    else:
        st.info("Click **▶ Simulate** to run a head-to-head matchup simulation.")
