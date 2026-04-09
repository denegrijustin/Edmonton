"""Simulator view — single game, playoff series, and full playoff simulations."""

import streamlit as st

from services.mode_state import AppMode
from services.simulation import (
    simulate_single_game, simulate_playoff_series, simulate_full_playoffs,
    SIM_DEPTHS, get_sim_depth,
)
from ui.components import kpi_html, prob_bar_html, logo_card_html
from utils.formatters import fmt_pct, fmt_number
from utils.logos import logo_url
from utils.streamlit_keys import mk_key
from utils.validators import safe_numeric, safe_int


_PAGE = "simulator"


def _logo_img(abbrev: str, size: int = 42) -> str:
    return (
        f"<img src='{logo_url(abbrev)}' width='{size}' height='{size}' "
        f"style='object-fit:contain;vertical-align:middle;'/>"
    )


def _reason_list(metrics_a, metrics_b, name_a, name_b, team_metrics_dict):
    """Build 'why model likes' reasons for both sides."""
    ma = team_metrics_dict.get(name_a, {})
    mb = team_metrics_dict.get(name_b, {})
    reasons_a, reasons_b = [], []

    gf_a = safe_numeric(ma.get("gf_per_game"))
    gf_b = safe_numeric(mb.get("gf_per_game"))
    ga_a = safe_numeric(ma.get("ga_per_game"))
    ga_b = safe_numeric(mb.get("ga_per_game"))
    mom_a = safe_numeric(ma.get("momentum"))
    mom_b = safe_numeric(mb.get("momentum"))
    gd_a = safe_int(ma.get("goalDifferential"))
    gd_b = safe_int(mb.get("goalDifferential"))

    if gf_a > gf_b:
        reasons_a.append(f"Higher scoring ({gf_a:.2f} GF/G)")
    elif gf_b > gf_a:
        reasons_b.append(f"Higher scoring ({gf_b:.2f} GF/G)")
    if ga_a < ga_b:
        reasons_a.append(f"Better defense ({ga_a:.2f} GA/G)")
    elif ga_b < ga_a:
        reasons_b.append(f"Better defense ({ga_b:.2f} GA/G)")
    if mom_a > mom_b:
        reasons_a.append(f"Stronger momentum ({mom_a:.0f})")
    elif mom_b > mom_a:
        reasons_b.append(f"Stronger momentum ({mom_b:.0f})")
    if gd_a > gd_b:
        reasons_a.append(f"Better goal diff ({gd_a:+d})")
    elif gd_b > gd_a:
        reasons_b.append(f"Better goal diff ({gd_b:+d})")

    if not reasons_a:
        reasons_a.append("No clear statistical edge")
    if not reasons_b:
        reasons_b.append("No clear statistical edge")

    return reasons_a[:3], reasons_b[:3]


# ── Main render ───────────────────────────────────────────────────────────────

def render(all_teams, standings_df, team_metrics_dict, team_name_map,
           app_mode, playoff_series=None):
    """Render the Simulator tab."""
    try:
        _render_inner(all_teams, standings_df, team_metrics_dict,
                      team_name_map, app_mode, playoff_series)
    except Exception as exc:
        st.error(f"Simulator view could not be rendered: {exc}")


def _render_inner(all_teams, standings_df, team_metrics_dict,
                  team_name_map, app_mode, playoff_series):
    if not all_teams:
        st.info("Team data unavailable for simulation.")
        return

    sorted_teams = sorted(all_teams)

    sim_type = st.radio(
        "Simulation Type",
        ["Single Game", "Playoff Series", "Full Playoffs"],
        horizontal=True,
        key=mk_key(_PAGE, "sim_type"),
    )

    depth_choice = st.selectbox(
        "Simulation Depth",
        list(SIM_DEPTHS.keys()),
        index=1,
        key=mk_key(_PAGE, "depth"),
    )
    n_sims = get_sim_depth(depth_choice)

    if sim_type == "Single Game":
        _single_game(sorted_teams, team_name_map, team_metrics_dict, n_sims)
    elif sim_type == "Playoff Series":
        _playoff_series(sorted_teams, team_name_map, team_metrics_dict, n_sims)
    else:
        _full_playoffs(team_metrics_dict, team_name_map, n_sims,
                       app_mode, playoff_series)


# ── Single Game ───────────────────────────────────────────────────────────────

def _single_game(teams, name_map, metrics, n_sims):
    st.markdown("#### Single Game Simulation")

    tc = st.columns(3)
    with tc[0]:
        team_a = st.selectbox(
            "Team A", teams,
            format_func=lambda t: f"{t} — {name_map.get(t, t)}",
            key=mk_key(_PAGE, "sg_team_a"),
        )
    with tc[1]:
        team_b = st.selectbox(
            "Team B", teams, index=min(1, len(teams) - 1),
            format_func=lambda t: f"{t} — {name_map.get(t, t)}",
            key=mk_key(_PAGE, "sg_team_b"),
        )
    with tc[2]:
        home = st.selectbox(
            "Home Team", ["Team A", "Team B"],
            key=mk_key(_PAGE, "sg_home"),
        )

    if team_a == team_b:
        st.warning("Select two different teams.")
        return

    cache_key = f"sim_sg_{team_a}_{team_b}_{home}_{n_sims}"
    if st.button("Run Simulation", key=mk_key(_PAGE, "sg_run")):
        home_flag = "A" if home == "Team A" else "B"
        with st.spinner("Simulating…"):
            result = simulate_single_game(team_a, team_b, metrics,
                                          home=home_flag, n_sims=n_sims)
        st.session_state[cache_key] = result

    result = st.session_state.get(cache_key)
    if result:
        st.markdown("##### Results *(Simulated)*")

        # Logo + win probability
        rc = st.columns([2, 1, 2])
        a_pct = safe_numeric(result.get("a_win_pct", 0)) * 100
        b_pct = safe_numeric(result.get("b_win_pct", 0)) * 100
        rc[0].markdown(
            f"<div style='text-align:center;'>{_logo_img(team_a, 56)}<br/>"
            f"<b>{name_map.get(team_a, team_a)}</b><br/>"
            f"<span style='font-size:1.5rem;font-weight:800;'>{a_pct:.1f}%</span></div>",
            unsafe_allow_html=True,
        )
        rc[1].markdown(
            "<div style='text-align:center;padding-top:24px;font-size:1.1rem;"
            "font-weight:700;color:#64748b;'>vs</div>",
            unsafe_allow_html=True,
        )
        rc[2].markdown(
            f"<div style='text-align:center;'>{_logo_img(team_b, 56)}<br/>"
            f"<b>{name_map.get(team_b, team_b)}</b><br/>"
            f"<span style='font-size:1.5rem;font-weight:800;'>{b_pct:.1f}%</span></div>",
            unsafe_allow_html=True,
        )

        # Score distribution
        a_avg = safe_numeric(result.get("a_avg_goals", 0))
        b_avg = safe_numeric(result.get("b_avg_goals", 0))
        ot_pct = safe_numeric(result.get("ot_pct", 0)) * 100
        sc = st.columns(3)
        sc[0].markdown(kpi_html(f"{team_a} Avg Goals", f"{a_avg:.2f}"), unsafe_allow_html=True)
        sc[1].markdown(kpi_html("OT Probability", f"{ot_pct:.1f}%"), unsafe_allow_html=True)
        sc[2].markdown(kpi_html(f"{team_b} Avg Goals", f"{b_avg:.2f}"), unsafe_allow_html=True)

        # Why model likes
        reasons_a, reasons_b = _reason_list(None, None, team_a, team_b, metrics)
        wc = st.columns(2)
        with wc[0]:
            st.markdown(f"**Why Model Likes {team_a}**")
            for r in reasons_a:
                st.markdown(f"• {r}")
        with wc[1]:
            st.markdown(f"**Why Model Likes {team_b}**")
            for r in reasons_b:
                st.markdown(f"• {r}")


# ── Playoff Series ────────────────────────────────────────────────────────────

def _playoff_series(teams, name_map, metrics, n_sims):
    st.markdown("#### Playoff Series Simulation")

    tc = st.columns(2)
    with tc[0]:
        team_a = st.selectbox(
            "Higher Seed", teams,
            format_func=lambda t: f"{t} — {name_map.get(t, t)}",
            key=mk_key(_PAGE, "ps_team_a"),
        )
    with tc[1]:
        team_b = st.selectbox(
            "Lower Seed", teams, index=min(1, len(teams) - 1),
            format_func=lambda t: f"{t} — {name_map.get(t, t)}",
            key=mk_key(_PAGE, "ps_team_b"),
        )

    if team_a == team_b:
        st.warning("Select two different teams.")
        return

    sc = st.columns(2)
    with sc[0]:
        wins_a = st.number_input(
            f"{team_a} Current Wins", min_value=0, max_value=3, value=0,
            key=mk_key(_PAGE, "ps_wins_a"),
        )
    with sc[1]:
        wins_b = st.number_input(
            f"{team_b} Current Wins", min_value=0, max_value=3, value=0,
            key=mk_key(_PAGE, "ps_wins_b"),
        )

    cache_key = f"sim_ps_{team_a}_{team_b}_{wins_a}_{wins_b}_{n_sims}"
    if st.button("Run Series Simulation", key=mk_key(_PAGE, "ps_run")):
        with st.spinner("Simulating series…"):
            result = simulate_playoff_series(
                team_a, team_b, metrics,
                wins_a=wins_a, wins_b=wins_b, n_sims=n_sims,
            )
        st.session_state[cache_key] = result

    result = st.session_state.get(cache_key)
    if result:
        st.markdown("##### Series Win Probability *(Simulated)*")
        a_prob = safe_numeric(result.get("team_a_wins_prob", 0)) * 100
        b_prob = safe_numeric(result.get("team_b_wins_prob", 0)) * 100

        pc = st.columns(2)
        pc[0].markdown(
            f"<div style='text-align:center;'>{_logo_img(team_a, 48)}<br/>"
            f"<b>{name_map.get(team_a, team_a)}</b></div>",
            unsafe_allow_html=True,
        )
        pc[1].markdown(
            f"<div style='text-align:center;'>{_logo_img(team_b, 48)}<br/>"
            f"<b>{name_map.get(team_b, team_b)}</b></div>",
            unsafe_allow_html=True,
        )
        st.markdown(prob_bar_html(team_a, a_prob, "#3b82f6"), unsafe_allow_html=True)
        st.markdown(prob_bar_html(team_b, b_prob, "#ef4444"), unsafe_allow_html=True)

        length = result.get("most_likely_length", "—")
        st.markdown(f"**Most likely series length**: {length} games")

        # Why model likes
        reasons_a, reasons_b = _reason_list(None, None, team_a, team_b, metrics)
        wc = st.columns(2)
        with wc[0]:
            st.markdown(f"**Why Model Likes {team_a}**")
            for r in reasons_a:
                st.markdown(f"• {r}")
        with wc[1]:
            st.markdown(f"**Why Model Likes {team_b}**")
            for r in reasons_b:
                st.markdown(f"• {r}")


# ── Full Playoffs ─────────────────────────────────────────────────────────────

def _full_playoffs(metrics, name_map, n_sims, app_mode, playoff_series):
    st.markdown("#### Full Playoff Simulation")

    if not playoff_series:
        st.info("No active playoff series available. Full playoff simulation "
                "requires live bracket data.")
        return

    cache_key = f"sim_fp_{n_sims}"
    if st.button("Simulate Full Playoffs", key=mk_key(_PAGE, "fp_run")):
        with st.spinner("Running full playoff simulation…"):
            result = simulate_full_playoffs(playoff_series, metrics, n_sims=n_sims)
        st.session_state[cache_key] = result

    result = st.session_state.get(cache_key)
    if result:
        st.markdown("##### Advancement Probabilities *(Simulated)*")
        rows_html = (
            "<table style='width:100%;border-collapse:collapse;font-size:0.82rem;'>"
            "<tr style='border-bottom:2px solid #e2e8f0;'>"
            "<th style='padding:4px 6px;text-align:left;'>Team</th>"
            "<th style='padding:4px 6px;'>Next Rnd</th>"
            "<th style='padding:4px 6px;'>Conf Finals</th>"
            "<th style='padding:4px 6px;'>Finals</th>"
            "<th style='padding:4px 6px;'>Cup</th></tr>"
        )
        for team, odds in sorted(result.items(),
                                 key=lambda x: x[1].get("cup_odds", 0),
                                 reverse=True):
            nr = safe_numeric(odds.get("next_round_odds"))
            cf = safe_numeric(odds.get("conf_finals_odds"))
            fi = safe_numeric(odds.get("finals_odds"))
            cu = safe_numeric(odds.get("cup_odds"))
            rows_html += (
                f"<tr style='border-bottom:1px solid #f1f5f9;'>"
                f"<td style='padding:4px 6px;'>{_logo_img(team, 22)} "
                f"{name_map.get(team, team)}</td>"
                f"<td style='padding:4px 6px;text-align:center;'>{fmt_pct(nr)}</td>"
                f"<td style='padding:4px 6px;text-align:center;'>{fmt_pct(cf)}</td>"
                f"<td style='padding:4px 6px;text-align:center;'>{fmt_pct(fi)}</td>"
                f"<td style='padding:4px 6px;text-align:center;font-weight:700;'>"
                f"{fmt_pct(cu)}</td>"
                f"</tr>"
            )
        rows_html += "</table>"
        st.markdown(rows_html, unsafe_allow_html=True)
