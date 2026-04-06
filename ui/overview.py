"""Overview tab (Tab 1) — KPI cards, outlook, recent games."""

from typing import Any, Dict

import pandas as pd
import streamlit as st

from models.monte_carlo import monte_carlo_sim
from providers.metrics_provider import compute_team_metrics
from ui.charts import plot_goal_diff_trend, plot_momentum
from ui.components import (
    kpi_html,
    logo_card_html,
    result_card_html,
    safe_kpi,
)
from utils.formatters import fmt_record, fmt_signed_int
from utils.stoplights import stoplight


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
) -> None:
    """Render the Overview tab content."""

    # ── Identity row ──────────────────────────────────────────────────────────
    id_logo, id_stats = st.columns([1, 5])
    with id_logo:
        st.markdown(
            logo_card_html(
                selected_team,
                selected_team,
                f"{sel_metrics.get('gamesPlayed', 0)} GP",
            ),
            unsafe_allow_html=True,
        )
    with id_stats:
        w = sel_metrics.get("wins", 0)
        l = sel_metrics.get("losses", 0)
        otl = sel_metrics.get("otl", 0)
        pts = sel_metrics.get("points", 0)
        gd = sel_metrics.get("goalDifferential", 0)
        odds = sel_outlook.get("playoff_odds", 0)
        proj_pts = sel_outlook.get("projected_points", 0)
        mom = sel_metrics.get("momentum", 50)

        sl_odds = stoplight(odds, 70, 45)
        sl_gd = stoplight(gd, 10, -10)
        sl_mom = stoplight(mom, 55, 45)

        ov_c1, ov_c2, ov_c3, ov_c4, ov_c5 = st.columns(5)
        ov_c1.markdown(
            kpi_html("Record", fmt_record(w, l, otl), f"{pts} pts"), unsafe_allow_html=True
        )
        ov_c2.markdown(
            kpi_html("Proj. Record", sel_outlook.get("projected_record", "—"), f"~{proj_pts} pts"),
            unsafe_allow_html=True,
        )
        ov_c3.markdown(
            kpi_html("Playoff Odds", f"{sl_odds} {odds:.0f}%", "Internal model proxy"),
            unsafe_allow_html=True,
        )
        # BUG FIX: Use fmt_signed_int for safe formatting of goal differential
        # (gd may be float, int, NaN, or numpy type — :+d crashes on float)
        ov_c4.markdown(
            kpi_html("Goal Diff", f"{sl_gd} {fmt_signed_int(gd)}", "Season to date"),
            unsafe_allow_html=True,
        )
        ov_c5.markdown(
            kpi_html("Momentum", f"{sl_mom} {mom:.0f}", "Last 10 composite"),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Second row: projected opponent | next game | projected seed ────────────
    opp_col, ng_col, seed_col = st.columns(3)

    with opp_col:
        st.markdown("**🎯 Projected First-Round Opponent**")
        proj_opp = sel_outlook.get("projected_opponent")
        if proj_opp:
            opp_nm = team_name_map.get(proj_opp, proj_opp)
            st.markdown(logo_card_html(proj_opp, proj_opp, opp_nm), unsafe_allow_html=True)
        else:
            st.markdown("<span class='muted'>Outside playoff picture</span>", unsafe_allow_html=True)

    with ng_col:
        st.markdown("**📅 Next Game**")
        if not sel_schedule.empty:
            upcoming = sel_schedule[~sel_schedule["isCompleted"]].sort_values("gameDate")
            if not upcoming.empty:
                ng = upcoming.iloc[0]
                opp_ng = ng["awayTeam"] if ng["homeTeam"] == selected_team else ng["homeTeam"]
                venue_ng = "Home" if ng["homeTeam"] == selected_team else "Away"
                raw_date = ng.get("gameDate")
                date_ng = (
                    pd.to_datetime(raw_date).strftime("%b %d")
                    if raw_date is not None and pd.notna(raw_date)
                    else "TBD"
                )
                ng_m = team_metrics_dict.get(
                    opp_ng, compute_team_metrics(str(opp_ng), standings_df)
                )
                ng_sim = monte_carlo_sim(sel_metrics, ng_m, home_team="A" if venue_ng == "Home" else "B", n_sims=2000)
                proj_a = round(ng_sim["a_avg_goals"])
                proj_b = round(ng_sim["b_avg_goals"])
                st.markdown(
                    logo_card_html(str(opp_ng), f"vs {opp_ng}", f"{date_ng} · {venue_ng}"),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Projected:** `{selected_team} {proj_a} – {proj_b} {opp_ng}`"
                )
            else:
                st.markdown("<span class='muted'>No upcoming games found</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='muted'>Schedule unavailable</span>", unsafe_allow_html=True)

    with seed_col:
        st.markdown("**🏅 Projected Playoff Seed**")
        proj_seed = sel_outlook.get("projected_seed")
        conf_str = sel_outlook.get("conference", "Conference") or "Conference"
        if proj_seed:
            st.markdown(
                kpi_html(conf_str, f"#{proj_seed} Seed", "Based on current pace"),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                kpi_html("Playoff Status", "Outside Top 8", "Not currently projected in"),
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Recent 5 games row ────────────────────────────────────────────────────
    st.markdown("### Last 5 Games")
    if not sel_tg.empty:
        last5 = sel_tg.tail(5)
        rcols = st.columns(5)
        for _i, (_, _row) in enumerate(last5.iterrows()):
            opp_r = str(_row.get("opponent") or "?")
            res_r = str(_row.get("result") or "?")
            ts_r = int(_row.get("teamScore") or 0)
            os_r = int(_row.get("oppScore") or 0)
            raw_d = _row.get("gameDate")
            date_r = (
                pd.to_datetime(raw_d).strftime("%b %d")
                if raw_d is not None and pd.notna(raw_d)
                else ""
            )
            with rcols[_i]:
                st.markdown(
                    result_card_html(opp_r, res_r, f"{ts_r}–{os_r}", date_r),
                    unsafe_allow_html=True,
                )

        st.markdown("")
        ch1, ch2 = st.columns([1.35, 1])
        with ch1:
            st.plotly_chart(plot_goal_diff_trend(sel_tg), use_container_width=True)
        with ch2:
            st.plotly_chart(plot_momentum(sel_tg), use_container_width=True)
    else:
        st.info("No completed game data available yet for this team.")
