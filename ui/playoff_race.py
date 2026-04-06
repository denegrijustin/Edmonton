"""Playoff Race tab (Tab 3) — seeds, projection table, MoneyPuck odds."""

import time
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from config.settings import PLAYOFF_BRACKET_MAP
from models.projections import (
    build_playoff_projection_table,
    get_seed_prob_distribution,
)
from providers.moneypuck_provider import (
    get_all_playoff_odds,
    get_source_status,
    load_moneypuck_cached,
)
from providers.odds_provider import compute_consensus_odds
from ui.components import kpi_html, logo_card_html, prob_bar_html
from utils.formatters import fmt_number, fmt_pct, fmt_signed_int
from utils.logos import logo_url
from utils.stoplights import stoplight


def render(
    selected_team: str,
    sel_metrics: Dict[str, Any],
    sel_outlook: Dict[str, Any],
    standings_df: pd.DataFrame,
    team_name_map: Dict[str, str],
) -> None:
    """Render the Playoff Race tab content."""
    conf_name = sel_outlook.get("conference") or ""

    # ── KPI row ───────────────────────────────────────────────────────────────
    _pr1, _pr2, _pr3, _pr4 = st.columns(4)
    _conf_rank_val = sel_outlook.get("conference_rank")
    _pr1.markdown(
        kpi_html(
            "Conf. Rank",
            f"#{_conf_rank_val}" if _conf_rank_val else "—",
            f"{sel_metrics.get('points', 0)} pts",
        ),
        unsafe_allow_html=True,
    )
    _pr2.markdown(
        kpi_html("Proj. Points", str(sel_outlook.get("projected_points", "—")), "End-of-season pace"),
        unsafe_allow_html=True,
    )
    _pr3.markdown(
        kpi_html(
            "Proj. Seed",
            f"#{sel_outlook.get('projected_seed')}" if sel_outlook.get("projected_seed") else "Outside top 8",
            f"{conf_name} Conference",
        ),
        unsafe_allow_html=True,
    )
    _sl_pl = stoplight(sel_outlook.get("playoff_odds", 0), 70, 45)
    _pr4.markdown(
        kpi_html("Playoff Odds", f"{_sl_pl} {sel_outlook.get('playoff_odds', 0):.0f}%", "Internal proxy model"),
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── MoneyPuck + consensus playoff odds ────────────────────────────────────
    _render_moneypuck_section(selected_team, sel_outlook, team_name_map)

    st.markdown("---")

    pl_left, pl_right = st.columns([1, 2])
    with pl_left:
        st.markdown("**🎯 Projected First-Round Opponent**")
        _pl_opp = sel_outlook.get("projected_opponent")
        if _pl_opp:
            st.markdown(
                logo_card_html(_pl_opp, _pl_opp, team_name_map.get(_pl_opp, "")),
                unsafe_allow_html=True,
            )
            seed_probs = get_seed_prob_distribution(selected_team, standings_df)
            if seed_probs and sel_outlook.get("projected_seed"):
                cur_seed = int(sel_outlook["projected_seed"])
                alt_seed_num = PLAYOFF_BRACKET_MAP.get(max(1, cur_seed - 1) if cur_seed > 1 else cur_seed + 1)
                if alt_seed_num and not standings_df.empty:
                    mask_c = standings_df["conference"].astype(str).str.contains(conf_name, case=False, na=False)
                    cdf = standings_df[mask_c].copy()
                    cdf["points"] = pd.to_numeric(cdf["points"], errors="coerce").fillna(0)
                    cdf_sorted = cdf.sort_values("points", ascending=False).reset_index(drop=True)
                    if alt_seed_num <= len(cdf_sorted):
                        alt_opp = cdf_sorted.iloc[alt_seed_num - 1]["teamAbbrev"]
                        if alt_opp != _pl_opp:
                            st.markdown(
                                "<div style='margin-top:8px;font-size:0.82rem;color:#64748b;'>2nd most likely:</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                logo_card_html(str(alt_opp), str(alt_opp), team_name_map.get(str(alt_opp), "")),
                                unsafe_allow_html=True,
                            )
        else:
            st.markdown(
                "<span class='muted'>Not currently projected for playoffs</span>",
                unsafe_allow_html=True,
            )

    with pl_right:
        st.markdown("**📊 Seed Probability Distribution**")
        seed_probs = get_seed_prob_distribution(selected_team, standings_df)
        if seed_probs:
            seed_colors_map = {
                1: "#f59e0b", 2: "#3b82f6", 3: "#3b82f6",
                4: "#22c55e", 5: "#22c55e",
                6: "#94a3b8", 7: "#94a3b8", 8: "#ef4444",
            }
            prob_html_str = ""
            for _s in range(1, 9):
                _p = seed_probs.get(_s, 0)
                _c = seed_colors_map.get(_s, "#94a3b8")
                _label = f"Seed #{_s}"
                prob_html_str += prob_bar_html(_label, _p, _c)
            st.markdown(prob_html_str, unsafe_allow_html=True)
        else:
            st.info("Seed probability distribution unavailable.")

    st.markdown("---")
    st.markdown(f"### {conf_name} Conference Standings & Projection")

    if not standings_df.empty and conf_name:
        proj_tbl = build_playoff_projection_table(standings_df, conf_name)
        if not proj_tbl.empty:
            proj_tbl["Playoff"] = proj_tbl["in_playoffs"].map({True: "✅ IN", False: "❌ OUT"})

            def _hl_team(row: pd.Series) -> List[str]:
                if row.get("teamAbbrev") == selected_team:
                    return ["background-color:#eff6ff;font-weight:bold"] * len(row)
                if row.get("in_playoffs"):
                    return ["background-color:#f0fdf4"] * len(row)
                return [""] * len(row)

            disp_cols = ["conf_rank", "teamAbbrev", "teamName", "Record", "points", "proj_pts", "division", "Playoff"]
            st.dataframe(
                proj_tbl[disp_cols]
                .rename(
                    columns={
                        "conf_rank": "Rank",
                        "teamAbbrev": "Team",
                        "teamName": "Name",
                        "points": "Pts",
                        "proj_pts": "Proj Pts",
                        "division": "Division",
                    }
                )
                .style.apply(_hl_team, axis=1),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("Conference standings data unavailable.")


# ── MoneyPuck sub-section ─────────────────────────────────────────────────────

def _render_moneypuck_section(
    selected_team: str,
    sel_outlook: Dict[str, Any],
    team_name_map: Dict[str, str],
) -> None:
    """Show MoneyPuck playoff odds alongside internal model."""
    st.markdown("### 🏒 Playoff Odds — Source Comparison")

    # Gather MoneyPuck data
    mp_status = get_source_status()
    mp_all_odds = get_all_playoff_odds()
    mp_team_odds = mp_all_odds.get(selected_team)

    internal_odds = sel_outlook.get("playoff_odds", 0)

    # Build external sources list for consensus
    external_sources = []
    if mp_team_odds is not None:
        external_sources.append({
            "source": "MoneyPuck",
            "odds": mp_team_odds,
            "fresh": not mp_status.get("stale", False),
        })

    consensus = compute_consensus_odds(internal_odds, external_sources)

    # Render source comparison
    src_cols = st.columns(4)
    with src_cols[0]:
        sl_int = stoplight(internal_odds, 70, 45)
        st.markdown(
            kpi_html("Internal Model", f"{sl_int} {internal_odds:.0f}%", "Based on pace + GD + gap"),
            unsafe_allow_html=True,
        )
    with src_cols[1]:
        if mp_team_odds is not None:
            sl_mp = stoplight(mp_team_odds, 70, 45)
            st.markdown(
                kpi_html("MoneyPuck", f"{sl_mp} {mp_team_odds:.0f}%", "External source"),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                kpi_html("MoneyPuck", "—", "Source unavailable"),
                unsafe_allow_html=True,
            )
    with src_cols[2]:
        c_odds = consensus.get("consensus_odds")
        if c_odds is not None:
            sl_c = stoplight(c_odds, 70, 45)
            st.markdown(
                kpi_html("Consensus", f"{sl_c} {c_odds:.0f}%", f"{consensus['n_sources']} sources"),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                kpi_html("Consensus", "—", "No data"),
                unsafe_allow_html=True,
            )
    with src_cols[3]:
        spread = consensus.get("spread", 0)
        proj_seed = sel_outlook.get("projected_seed")
        seed_str = f"#{proj_seed}" if proj_seed else "—"
        st.markdown(
            kpi_html("Proj. Seed", seed_str, f"Spread: {spread:.0f}pp"),
            unsafe_allow_html=True,
        )

    # Source freshness warning
    if mp_status.get("stale"):
        ts = mp_status.get("timestamp")
        ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "unknown"
        st.warning(f"⚠️ MoneyPuck data is stale (last refresh: {ts_str}). Showing cached data.", icon="⚠️")
    elif not mp_status.get("success"):
        st.warning(
            "⚠️ MoneyPuck source unavailable — falling back to internal model only. "
            f"Error: {mp_status.get('error', 'unknown')}",
            icon="⚠️",
        )
